from __future__ import annotations

import base64
import hashlib
import hmac
import os
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import BigInteger, Boolean, Column, DateTime, String, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from schema.users import LoginRequest, LoginResponse, RegisterRequest, UserResponse
from utils.auth import create_access_token, create_refresh_token
from utils.db import Base, get_db


PBKDF2_ITERATIONS = 390_000


def _b64encode(raw: bytes) -> str:
    """PBKDF2 결과에서 생성된 바이트 데이터를 URL-safe Base64 문자열로 변환한다."""

    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


def _b64decode(data: str) -> bytes:
    """Base64 패딩을 보정한 뒤 원래의 바이트 데이터로 복원한다."""

    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def hash_password(password: str) -> str:
    """랜덤 솔트를 사용해 PBKDF2-SHA256 알고리즘으로 비밀번호 해시를 생성한다."""

    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${_b64encode(salt)}${_b64encode(dk)}"


def verify_password(password: str, hashed: str) -> bool:
    """저장된 해시 문자열을 파싱해 입력 비밀번호와 동일한지 비교한다."""

    try:
        algorithm, iterations, salt_b64, hash_b64 = hashed.split("$")
    except ValueError:
        return False

    if algorithm != "pbkdf2_sha256":
        return False

    try:
        iterations_int = int(iterations)
    except ValueError:
        return False

    salt = _b64decode(salt_b64)
    expected_hash = _b64decode(hash_b64)
    test_hash = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations_int)
    return hmac.compare_digest(expected_hash, test_hash)


class User(Base):
    __tablename__ = "users"

    idx = Column(BigInteger, primary_key=True, autoincrement=True)
    id = Column(String(255), nullable=False, unique=True)
    email = Column(String(255), nullable=False, unique=True)
    nickname = Column(String(100), unique=True)
    password_hash = Column(String(255), nullable=False)
    active = Column(Boolean, nullable=False, default=True)
    created = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_login = Column(DateTime)


router = APIRouter(prefix="/users", tags=["users"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> UserResponse:
    """신규 사용자 정보를 검증한 후 해시된 비밀번호와 함께 저장한다."""
    
    if payload.id:
        id_owner = db.scalar(select(User).where(User.id == payload.id))
        if id_owner:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="이미 사용 중인 아이디입니다.",
            )

    if payload.email:
        email_owner = db.scalar(select(User).where(User.email == payload.email))
        if email_owner:
            raise HTTPException(
                status_code=460,
                detail="이미 사용 중인 이메일입니다.",
            )
            
    if payload.nickname:
        nickname_owner = db.scalar(select(User).where(User.nickname == payload.nickname))
        if nickname_owner:
            raise HTTPException(
                status_code=461,
                detail="이미 사용 중인 닉네임입니다.",
            )

    user = User(
        id=payload.id,
        email=payload.email,
        nickname=payload.nickname,
        password_hash=hash_password(payload.password),
        active=True,
    )

    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="이미 사용 중인 사용자 정보가 있습니다.",
        )

    db.refresh(user)
    return user


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> LoginResponse:
    """사용자 인증에 성공하면 마지막 로그인 시간을 갱신하고 토큰을 발급한다."""

    user = db.scalar(select(User).where(User.id == payload.id))

    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="아이디 또는 비밀번호가 올바르지 않습니다.",
        )

    if not user.active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="비활성화된 계정입니다.",
        )

    user.last_login = datetime.utcnow()
    db.add(user)
    db.commit()
    db.refresh(user)

    access_token = create_access_token(subject=str(user.idx))
    refresh_token = create_refresh_token(subject=str(user.idx))

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
    )
