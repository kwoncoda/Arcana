"""Google Drive OAuth helper utilities."""

from __future__ import annotations

import base64
import json
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from models import DataSource, GoogleDriveOauthCredentials


DEFAULT_SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
]

_client_scopes_env = os.getenv("GOOGLE_DRIVE_SCOPES")
if _client_scopes_env:
    SCOPES = [scope.strip() for scope in _client_scopes_env.split() if scope.strip()]
else:
    SCOPES = DEFAULT_SCOPES

CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
REDIRECT_URI = os.getenv("GOOGLE_DRIVE_REDIRECT_URI")
AUTH_URI = os.getenv("GOOGLE_AUTH_URI")
TOKEN_URI = os.getenv("GOOGLE_TOKEN_URI")
USER_INFO_ENDPOINT = "https://openidconnect.googleapis.com/v1/userinfo"

if not CLIENT_ID or not CLIENT_SECRET or not REDIRECT_URI:
    raise RuntimeError(
        "GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REDIRECT_URI 환경 변수를 설정하세요."
    )

_STATE_TTL = timedelta(minutes=10)
_STATE: dict[str, datetime] = {}


class GoogleDriveCredentialError(Exception):
    """Raised when a Google Drive credential is missing or disconnected."""


def _b64e(payload: Dict[str, Any]) -> str:
    body = json.dumps(payload or {}, separators=(",", ":"), ensure_ascii=False)
    raw = base64.urlsafe_b64encode(body.encode("utf-8"))
    return raw.decode("utf-8").rstrip("=")


def _b64d(token: str) -> Dict[str, Any]:
    pad = "=" * (-len(token) % 4)
    decoded = base64.urlsafe_b64decode((token + pad).encode("utf-8"))
    if not decoded:
        return {}
    return json.loads(decoded.decode("utf-8"))


def make_state(*, cred_idx: int, user_idx: int) -> str:
    nonce = secrets.token_urlsafe(16)
    _STATE[nonce] = datetime.now(timezone.utc)
    return _b64e({"nonce": nonce, "cred_idx": cred_idx, "uid": user_idx})


def verify_state(state: str) -> Tuple[int, int]:
    try:
        payload = _b64d(state)
        nonce = payload["nonce"]
        cred_idx = int(payload["cred_idx"])
        user_idx = int(payload["uid"])
    except Exception as exc:  # pragma: no cover - 방어적 코드
        raise ValueError("손상된 state 입니다.") from exc

    issued_at = _STATE.pop(nonce, None)
    if not issued_at or datetime.now(timezone.utc) - issued_at > _STATE_TTL:
        raise ValueError("state 검증 실패 또는 만료")

    return cred_idx, user_idx


def build_authorize_url(state: str) -> str:
    from urllib.parse import urlencode

    params = {
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "include_granted_scopes": "true",
        "prompt": "consent",
        "state": state,
    }
    return f"{AUTH_URI}?{urlencode(params)}"


async def exchange_code_for_tokens(code: str) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
    data = {
        "code": code,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code",
    }

    async with httpx.AsyncClient(timeout=30) as client:
        token_response = await client.post(TOKEN_URI, data=data)

    if token_response.status_code != 200:
        raise RuntimeError(token_response.text)

    token_json: Dict[str, Any] = token_response.json()
    user_info = await _fetch_user_info(token_json.get("access_token"))
    return token_json, user_info


async def _fetch_user_info(access_token: Optional[str]) -> Optional[Dict[str, Any]]:
    if not access_token:
        return None

    headers = {"Authorization": f"Bearer {access_token}"}
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(USER_INFO_ENDPOINT, headers=headers)

    if response.status_code != 200:
        return None

    return response.json()


def _merge_payload(original: Optional[Dict[str, Any]], updates: Dict[str, Any]) -> Dict[str, Any]:
    if not original:
        return updates
    try:
        return {**original, **updates}
    except TypeError:  # pragma: no cover - defensive
        return updates


def apply_oauth_tokens(
    db: Session,
    cred: GoogleDriveOauthCredentials,
    token_payload: Dict[str, Any],
    user_info: Optional[Dict[str, Any]] = None,
    *,
    mark_connected: bool = True,
) -> GoogleDriveOauthCredentials:
    now = datetime.now(timezone.utc)

    cred.provider = "googledrive"
    cred.token_type = (token_payload.get("token_type") or cred.token_type) or "Bearer"

    access_token = token_payload.get("access_token")
    if access_token:
        cred.access_token = access_token

    refresh_token = token_payload.get("refresh_token")
    if refresh_token:
        cred.refresh_token = refresh_token

    scope_value = token_payload.get("scope")
    if isinstance(scope_value, str):
        cred.scope = scope_value
    elif isinstance(scope_value, list):
        cred.scope = " ".join(scope_value)

    id_token = token_payload.get("id_token")
    if id_token:
        cred.id_token = id_token

    expires_in = token_payload.get("expires_in")
    expires_at = token_payload.get("expires")
    if isinstance(expires_in, (int, float)):
        cred.expires = now + timedelta(seconds=int(expires_in))
    elif isinstance(expires_at, str):
        try:
            parsed = datetime.fromisoformat(expires_at)
            if parsed.tzinfo is None:
                cred.expires = parsed.replace(tzinfo=timezone.utc)
            else:
                cred.expires = parsed.astimezone(timezone.utc)
        except ValueError:
            pass

    if user_info:
        cred.google_user_id = user_info.get("sub") or user_info.get("id") or cred.google_user_id
        cred.email = user_info.get("email") or cred.email

    extra_payload = token_payload.copy()
    if user_info:
        extra_payload = {**extra_payload, "user_info": user_info}

    cred.provider_payload = _merge_payload(cred.provider_payload, extra_payload)
    cred.updated = now

    db.add(cred)

    if mark_connected:
        data_source = db.scalar(select(DataSource).where(DataSource.idx == cred.data_source_idx))
        if data_source:
            data_source.status = "connected"
            db.add(data_source)

    db.commit()
    db.refresh(cred)
    return cred


def get_connected_user_credential(
    db: Session, *, workspace_idx: int, user_idx: int
) -> GoogleDriveOauthCredentials:
    data_source = db.scalar(
        select(DataSource).where(
            DataSource.workspace_idx == workspace_idx,
            DataSource.type == "googledrive",
        )
    )

    if not data_source or data_source.status != "connected":
        raise GoogleDriveCredentialError("Google Drive 연동이 필요합니다.")

    credential = db.scalar(
        select(GoogleDriveOauthCredentials).where(
            GoogleDriveOauthCredentials.data_source_idx == data_source.idx,
            GoogleDriveOauthCredentials.user_idx == user_idx,
        )
    )

    if not credential or not credential.access_token:
        raise GoogleDriveCredentialError("Google Drive 연동 토큰을 찾을 수 없습니다.")

    return credential
