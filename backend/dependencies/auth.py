"""공용 인증/인가 의존성을 정의합니다."""

from __future__ import annotations

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from models import User
from utils.auth import AuthorizationError, InvalidTokenError, get_user_from_token
from utils.db import get_db


bearer_scheme = HTTPBearer(auto_error=False, scheme_name="BearerAuth")


def get_current_user(
    *,
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
) -> User:
    """Bearer 토큰에서 현재 사용자를 조회합니다."""

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer 토큰이 필요합니다.",
        )

    authorization = f"{credentials.scheme} {credentials.credentials}"

    try:
        return get_user_from_token(db, authorization)
    except (AuthorizationError, InvalidTokenError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc
