from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, Dict

from sqlalchemy import select

if TYPE_CHECKING:  # pragma: no cover - 순환 참조 방지용 타입 힌트
    from sqlalchemy.orm import Session
    from models import User


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


def _b64url_decode(segment: str) -> bytes:
    padding = "=" * (-len(segment) % 4)
    return base64.urlsafe_b64decode(segment + padding)


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


class InvalidTokenError(Exception):
    """JWT 디코딩 및 검증 과정에서 발생한 오류."""


class AuthorizationError(Exception):
    """Authorization 헤더 처리 중 발생한 오류."""


def _decode_token(token: str) -> Dict[str, Any]:
    try:
        header_segment, payload_segment, signature_segment = token.split(".")
    except ValueError as exc:
        raise InvalidTokenError("토큰 형식이 올바르지 않습니다.") from exc

    signing_input = f"{header_segment}.{payload_segment}".encode("utf-8")
    try:
        signature = _b64url_decode(signature_segment)
    except Exception as exc:  # noqa: BLE001 - base64 예외 메시지를 감추기 위해
        raise InvalidTokenError("토큰 서명 디코딩에 실패했습니다.") from exc

    expected_signature = hmac.new(
        JWT_SECRET_KEY.encode("utf-8"),
        signing_input,
        hashlib.sha256,
    ).digest()

    if not hmac.compare_digest(signature, expected_signature):
        raise InvalidTokenError("토큰 서명이 유효하지 않습니다.")

    try:
        payload_raw = _b64url_decode(payload_segment)
        payload: Dict[str, Any] = json.loads(payload_raw)
    except Exception as exc:  # noqa: BLE001 - JSON 에러 상세 노출 방지
        raise InvalidTokenError("토큰 페이로드를 읽을 수 없습니다.") from exc

    exp = payload.get("exp")
    if exp is not None:
        expire_at = datetime.fromtimestamp(int(exp), tz=timezone.utc)
        if expire_at < datetime.now(tz=timezone.utc):
            raise InvalidTokenError("토큰이 만료되었습니다.")

    return payload


def decode_access_token(token: str) -> Dict[str, Any]:
    """액세스 토큰을 검증하고 페이로드를 반환합니다."""

    payload = _decode_token(token)
    token_type = payload.get("type")
    if token_type != "access":
        raise InvalidTokenError("액세스 토큰이 필요합니다.")
    return payload


def get_user_from_token(db: "Session", authorization: str) -> "User":
    """Authorization 헤더에서 사용자 객체를 조회합니다."""

    from models import User  # 지연 로딩으로 순환 참조 방지

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise AuthorizationError("Bearer 토큰이 필요합니다.")

    payload = decode_access_token(token)

    subject = payload.get("sub")
    if subject is None:
        raise AuthorizationError("토큰에 사용자 정보가 없습니다.")

    try:
        user_idx = int(subject)
    except (TypeError, ValueError) as exc:  # pragma: no cover - 방어적 코드
        raise AuthorizationError("유효하지 않은 사용자 식별자입니다.") from exc

    user = db.scalar(select(User).where(User.idx == user_idx))
    if not user:
        raise AuthorizationError("사용자를 찾을 수 없습니다.")

    return user
