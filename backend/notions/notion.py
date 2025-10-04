# services/notion.py
"""Notion OAuth 유틸: authorize URL, state 생성/검증, code→token 교환, credential 업데이트."""

from __future__ import annotations

import os
import json
import base64
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Tuple

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

# ---- In-memory state (redis로 바꿔야함) ----
_STATE: dict[str, datetime] = {}
_STATE_TTL = timedelta(minutes=10)

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
    cred.provider_payload = data
    db.add(cred)

    if mark_connected:
        ds = db.scalar(select(DataSource).where(DataSource.idx == cred.data_source_idx))
        if ds:
            ds.status = "connected"
            db.add(ds)

    db.commit()
    db.refresh(cred)
    return cred
