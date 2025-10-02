from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, EmailStr, StringConstraints, ConfigDict

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
    nickname: NicknameStr | None = None
    type: Literal["personal", "organization"] = "personal"
    organization_name: WorkspaceNameStr | None = None
    workspace_name: WorkspaceNameStr | None = None

class LoginRequest(BaseModel):
    """로그인 요청으로 전달되는 아이디와 비밀번호 형식을 검증한다."""
    id: IdStr
    password: PasswordStr

class UserResponse(BaseModel):
    """사용자 정보를 API 응답 형태로 직렬화한다."""
    idx: int
    id: str
    email: EmailStr
    nickname: str | None = None
    active: bool
    created: datetime
    last_login: datetime | None = None

    # pydantic v2 방식 (orm_mode 대체)
    model_config = ConfigDict(from_attributes=True)

class LoginResponse(BaseModel):
    """로그인 성공 시 사용자 정보와 토큰을 함께 응답한다."""
    access_token: str
    refresh_token: str
