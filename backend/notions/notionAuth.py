# services/notion.py
"""Notion OAuth 유틸: authorize URL, state 생성/검증, code→token 교환, credential 업데이트."""

from __future__ import annotations

import os
import json
import base64
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from models import NotionOauthCredentials, DataSource

# ---- Env ----
CLIENT_ID = os.getenv("NOTION_CLIENT_ID")
CLIENT_SECRET = os.getenv("NOTION_CLIENT_SECRET")
REDIRECT_URI = os.getenv("NOTION_REDIRECT_URI")
if not CLIENT_ID or not CLIENT_SECRET or not REDIRECT_URI:
    raise RuntimeError(".env에 NOTION_CLIENT_ID/NOTION_CLIENT_SECRET/NOTION_REDIRECT_URI를 설정하세요.")

NOTION_AUTH_URL = "https://api.notion.com/v1/oauth/authorize"
NOTION_TOKEN_URL = "https://api.notion.com/v1/oauth/token"

_REFRESH_SAFETY_WINDOW = timedelta(seconds=90)

# ---- In-memory state (redis로 바꿔야함) ----
_STATE: dict[str, datetime] = {}
_STATE_TTL = timedelta(minutes=10)


class NotionCredentialError(Exception):
    """노션 자격증명이 없거나 연결되지 않았을 때 사용하는 예외."""


def _b64e(d: dict) -> str:
    raw = json.dumps(d, separators=(",", ":"), ensure_ascii=False).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")

def _b64d(s: str) -> dict:
    pad = "=" * (-len(s) % 4)
    return json.loads(base64.urlsafe_b64decode(s + pad))

def build_authorize_url(state: str) -> str:
    from urllib.parse import urlencode
    q = urlencode({
        "owner": "user",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "state": state,
    })
    return f"{NOTION_AUTH_URL}?{q}"

def make_state(cred_idx: int, user_idx: int) -> str:
    nonce = secrets.token_urlsafe(16)
    _STATE[nonce] = datetime.now(timezone.utc)
    return _b64e({"nonce": nonce, "cred_idx": cred_idx, "uid": user_idx})

def verify_state(state: str) -> Tuple[int, int]:
    try:
        p = _b64d(state)
        nonce = p["nonce"]
        cred_idx = int(p["cred_idx"])
        user_idx = int(p["uid"])
    except Exception as e:
        raise ValueError("손상된 state 입니다.") from e
    ts = _STATE.pop(nonce, None)
    if not ts or datetime.now(timezone.utc) - ts > _STATE_TTL:
        raise ValueError("state 검증 실패 또는 만료")
    return cred_idx, user_idx

async def exchange_code_for_tokens(code: str) -> Dict[str, Any]:
    auth = httpx.BasicAuth(CLIENT_ID, CLIENT_SECRET)
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            NOTION_TOKEN_URL,
            auth=auth,
            json={"grant_type": "authorization_code", "code": code, "redirect_uri": REDIRECT_URI},
        )
    if r.status_code != 200:
        raise RuntimeError(r.text)
    return r.json()

def apply_oauth_tokens(
    db: Session,
    cred: NotionOauthCredentials,
    data: Dict[str, Any],
    mark_connected: bool = True,
) -> NotionOauthCredentials:
    now = datetime.now(timezone.utc)
    cred.provider = "notion"
    cred.bot_id = data.get("bot_id") or cred.bot_id
    cred.provider_workspace_id = data.get("workspace_id") or cred.provider_workspace_id
    cred.workspace_name = data.get("workspace_name") or cred.workspace_name
    cred.workspace_icon = data.get("workspace_icon") or cred.workspace_icon
    cred.token_type = (data.get("token_type") or cred.token_type) or "bearer"
    cred.access_token = data.get("access_token") or cred.access_token
    cred.refresh_token = data.get("refresh_token") or cred.refresh_token
    if data.get("expires_in"):
        try:
            cred.expires = now + timedelta(seconds=int(data["expires_in"]))
        except Exception:
            pass
    cred.updated = now
    previous_payload = cred.provider_payload or {}
    try:
        merged_payload = {**previous_payload, **data}
    except TypeError:
        merged_payload = data
    cred.provider_payload = merged_payload
    db.add(cred)

    if mark_connected:
        ds = db.scalar(select(DataSource).where(DataSource.idx == cred.data_source_idx))
        if ds:
            ds.status = "connected"
            db.add(ds)

    db.commit()
    db.refresh(cred)
    return cred


def _normalize_expires(expires: Optional[datetime]) -> Optional[datetime]:
    """Convert naive datetimes to UTC-aware ones for safe comparisons."""

    if expires is None:
        return None
    if expires.tzinfo is None:
        return expires.replace(tzinfo=timezone.utc)
    return expires.astimezone(timezone.utc)


def should_refresh_token(cred: NotionOauthCredentials) -> bool:
    """Return True if access token is missing or near expiry."""

    if not cred.access_token:
        return True

    expires = _normalize_expires(cred.expires)
    if not expires:
        return False

    return expires <= datetime.now(timezone.utc) + _REFRESH_SAFETY_WINDOW


def get_credential_by_workspace_id(
    db: Session, *, workspace_id: str
) -> NotionOauthCredentials:
    """Fetch stored credentials for a given Notion workspace."""

    credential = db.scalar(
        select(NotionOauthCredentials).where(
            NotionOauthCredentials.provider == "notion",
            NotionOauthCredentials.provider_workspace_id == workspace_id,
        )
    )

    if not credential:
        raise LookupError("해당 workspace_id에 대한 Notion 자격증명이 없습니다.")

    return credential


def get_connected_user_credential(
    db: Session, *, workspace_idx: int, user_idx: int
) -> NotionOauthCredentials:
    """워크스페이스 소유 데이터를 기반으로 연결된 Notion 자격증명을 조회한다."""

    data_source = db.scalar(
        select(DataSource).where(
            DataSource.workspace_idx == workspace_idx,
            DataSource.type == "notion",
        )
    )

    if not data_source or data_source.status != "connected":
        raise NotionCredentialError("Notion 연동이 필요합니다.")

    credential = db.scalar(
        select(NotionOauthCredentials).where(
            NotionOauthCredentials.data_source_idx == data_source.idx,
            NotionOauthCredentials.user_idx == user_idx,
        )
    )

    if not credential or not credential.access_token:
        raise NotionCredentialError("Notion 연동 토큰을 찾을 수 없습니다.")

    return credential


async def refresh_access_token(
    db: Session, cred: NotionOauthCredentials
) -> NotionOauthCredentials:
    """Re-issue an access token using the stored refresh token."""

    if not cred.refresh_token:
        raise RuntimeError("리프레시 토큰이 없어 access_token을 재발급할 수 없습니다.")

    auth = httpx.BasicAuth(CLIENT_ID, CLIENT_SECRET)
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            NOTION_TOKEN_URL,
            auth=auth,
            json={
                "grant_type": "refresh_token",
                "refresh_token": cred.refresh_token,
            },
        )

    if resp.status_code != 200:
        raise RuntimeError(f"Notion 토큰 재발급 실패: {resp.text}")

    payload = resp.json()
    return apply_oauth_tokens(db, cred, payload, mark_connected=False)


async def ensure_valid_access_token(
    db: Session, cred: NotionOauthCredentials
) -> NotionOauthCredentials:
    """Return credentials, refreshing the access token once if needed."""

    if should_refresh_token(cred):
        cred = await refresh_access_token(db, cred)
    return cred
