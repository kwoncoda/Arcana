from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, EmailStr, StringConstraints

# 공통 문자열 정의
IdStr = Annotated[str, StringConstraints(strip_whitespace=True,max_length=255)]
PasswordStr = Annotated[str, StringConstraints(max_length=128)]
NicknameStr = Annotated[str, StringConstraints(strip_whitespace=True, max_length=100)]
WorkspaceNameStr = Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)]

class RegisterRequest(BaseModel):
    """회원 가입 시 클라이언트가 전달하는 필수 정보를 검증한다."""
    id: IdStr
    email: EmailStr
    password: PasswordStr
    nickname: NicknameStr
    type: Literal["personal", "organization"] = "personal"
    organization_name: WorkspaceNameStr | None = None

class LoginRequest(BaseModel):
    """로그인 요청으로 전달되는 아이디와 비밀번호 형식을 검증한다."""
    id: IdStr
    password: PasswordStr

class LoginResponse(BaseModel):
    """로그인 성공 시 사용자 정보와 토큰을 함께 응답한다."""
    access_token: str
    refresh_token: str
    nickname: str


class TokenRefreshRequest(BaseModel):
    """리프레시 토큰을 이용한 재발급 요청 페이로드."""

    refresh_token: str


class TokenRefreshResponse(BaseModel):
    """리프레시 토큰으로 재발급된 토큰 응답."""

    access_token: str
    refresh_token: str
