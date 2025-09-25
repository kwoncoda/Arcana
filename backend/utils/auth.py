from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict


def _get_env_int(name: str) -> int:
    raw = os.getenv(name)
    try:
        return int(raw)
    except ValueError as exc:  
        raise RuntimeError(f"환경 변수 {name} 은(는) 정수여야 합니다.") from exc


JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
if not JWT_SECRET_KEY:
    raise RuntimeError("JWT_SECRET_KEY 환경 변수를 설정하세요.")

JWT_ALGORITHM = os.getenv("JWT_ALGORITHM")
if JWT_ALGORITHM != "HS256":
    raise RuntimeError("JWT_ALGORITHM 환경 변수를 설정하세요.")
ACCESS_TOKEN_EXPIRE_MINUTES = _get_env_int("JWT_ACCESS_TOKEN_EXPIRE_MINUTES")
REFRESH_TOKEN_EXPIRE_DAYS = _get_env_int("JWT_REFRESH_TOKEN_EXPIRE_DAYS")


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _create_token(*, subject: str, expires_delta: timedelta, token_type: str) -> str:
    now = datetime.now(tz=timezone.utc)
    payload: Dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "iat": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
    }

    header = {"alg": JWT_ALGORITHM, "typ": "JWT"}
    header_segment = _b64url_encode(json.dumps(header, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    payload_segment = _b64url_encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    signing_input = f"{header_segment}.{payload_segment}".encode("utf-8")

    signature = hmac.new(
        JWT_SECRET_KEY.encode("utf-8"),
        signing_input,
        hashlib.sha256,
    ).digest()
    signature_segment = _b64url_encode(signature)

    return f"{header_segment}.{payload_segment}.{signature_segment}"


def create_access_token(*, subject: str) -> str:
    """액세스 토큰을 생성합니다."""

    return _create_token(
        subject=subject,
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        token_type="access",
    )


def create_refresh_token(*, subject: str) -> str:
    """리프레시 토큰을 생성합니다."""

    return _create_token(
        subject=subject,
        expires_delta=timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        token_type="refresh",
    )
