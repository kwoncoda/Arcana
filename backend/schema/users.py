from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, EmailStr, constr


class RegisterRequest(BaseModel):
    """회원 가입 시 클라이언트가 전달하는 필수 정보를 검증한다."""

    id: constr(strip_whitespace=True, min_length=4, max_length=255)
    email: EmailStr
    password: constr(min_length=8, max_length=128)
    nickname: Optional[constr(strip_whitespace=True, max_length=100)] = None


class LoginRequest(BaseModel):
    """로그인 요청으로 전달되는 아이디와 비밀번호 형식을 검증한다."""

    id: constr(strip_whitespace=True, min_length=4, max_length=255)
    password: constr(min_length=8, max_length=128)


class UserResponse(BaseModel):
    """사용자 정보를 API 응답 형태로 직렬화한다."""

    idx: int
    id: str
    email: EmailStr
    nickname: Optional[str]
    active: bool
    created: datetime
    last_login: Optional[datetime]

    class Config:
        orm_mode = True


class LoginResponse(BaseModel):
    """로그인 성공 시 사용자 정보와 토큰을 함께 응답한다."""

    user: UserResponse
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"
