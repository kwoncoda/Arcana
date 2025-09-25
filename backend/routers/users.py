from __future__ import annotations

import base64
import hashlib
import hmac
import os
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, constr
from sqlalchemy import BigInteger, Boolean, Column, DateTime, String, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from utils.db import Base, get_db


PBKDF2_ITERATIONS = 390_000


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


def _b64decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${_b64encode(salt)}${_b64encode(dk)}"


def verify_password(password: str, hashed: str) -> bool:
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


class RegisterRequest(BaseModel):
    id: constr(strip_whitespace=True, min_length=4, max_length=255)
    email: EmailStr
    password: constr(min_length=8, max_length=128)
    nickname: Optional[constr(strip_whitespace=True, max_length=100)] = None


class LoginRequest(BaseModel):
    id: constr(strip_whitespace=True, min_length=4, max_length=255)
    password: constr(min_length=8, max_length=128)


class UserResponse(BaseModel):
    idx: int
    id: str
    email: EmailStr
    nickname: Optional[str]
    active: bool
    created: datetime
    last_login: Optional[datetime]

    class Config:
        orm_mode = True


router = APIRouter(prefix="/users", tags=["users"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> UserResponse:
    existing = db.scalar(select(User).where((User.id == payload.id) | (User.email == payload.email)))
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="이미 사용 중인 아이디 또는 이메일입니다.",
        )

    if payload.nickname:
        nickname_owner = db.scalar(select(User).where(User.nickname == payload.nickname))
        if nickname_owner:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
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


@router.post("/login", response_model=UserResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> UserResponse:
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

    return user
