from __future__ import annotations

import base64
import hashlib
import hmac
import os
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy import select, exists
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from schema.users import LoginRequest, LoginResponse, RegisterRequest
from models import (
    Membership,
    Organization,
    Workspace,
    WorkspaceType,
    User,
)
from utils.auth import create_access_token, create_refresh_token
from utils.db import Base, get_db


PBKDF2_ITERATIONS = 390_000

router = APIRouter(prefix="/users", tags=["users"])


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



@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    responses={
        409: {"description": "ID 중복"},
        460: {"description": "이메일 중복"},
        461: {"description": "닉네임 중복"},
        462: {"description": "조직 이름 누락"},
        463: {"description": "이미 사용자가 있음"},
        464: {"description": "유효하지 않은 워크스페이스 타입"},
    })
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    """신규 사용자 정보를 검증한 후 해시된 비밀번호와 함께 저장한다."""
    
     # --- 0) 중복 체크(선제) ---
    if payload.id:
        if db.scalar(select(exists().where(User.id == payload.id))):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="이미 사용 중인 아이디입니다."
            )

    if payload.email:
        if db.scalar(select(exists().where(User.email == payload.email))):
            raise HTTPException(
                status_code=460, detail="이미 사용 중인 이메일입니다."
            )

    if payload.nickname:
        if db.scalar(select(exists().where(User.nickname == payload.nickname))):
            raise HTTPException(
                status_code=461, detail="이미 사용 중인 닉네임입니다."
            )

    # --- 1) type 검증 ---
    try:
        workspace_type = WorkspaceType(payload.type)
    except Exception:
        raise HTTPException(
            status_code=464, detail="유효하지 않은 워크스페이스 종류입니다. (personal|organization)"
        )

    if workspace_type == WorkspaceType.organization and not payload.organization_name:
        raise HTTPException(
            status_code=462, detail="조직 이름을 입력해주세요."
        )

    user = User(
        id=payload.id,
        email=payload.email,
        nickname=payload.nickname,
        password_hash=hash_password(payload.password),
        type=workspace_type,
        active=True,
    )

    db.add(user)

    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=463,
            detail="이미 사용 중인 사용자 정보가 있습니다.",
        )

    
    organization = None
    workspace = None

    if workspace_type is WorkspaceType.organization:
        # organization
        organization = db.scalar(select(Organization).where(Organization.name == payload.organization_name))
        if not organization:
            organization = Organization(name=payload.organization_name)
            db.add(organization)

            try:
                db.flush()
            except IntegrityError:
                db.rollback()
                raise HTTPException(
                    status_code=463,
                    detail="조직을 생성할 수 없습니다.",
                )

        membership = Membership(
            organization_idx=organization.idx,
            user_idx=user.idx,
            role="member", ## 일단 mvp로는 member만 할거임
        )
        db.add(membership)
        
        workspace = db.scalar(
            select(Workspace).where(
                Workspace.type == "organization",
                Workspace.organization_idx == organization.idx,
            )
        )
        
        if not workspace:
            workspace = Workspace(
                type=workspace_type.value,
                name=f"{organization.name}'s workspace",
                organization_idx=organization.idx,
            )
            db.add(workspace)
    else:
        # personal
        workspace = Workspace(
            type=workspace_type.value,
            name=f"{payload.nickname}'s workspace",
            owner_user_idx=user.idx,
        )
        db.add(workspace)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="회원가입 처리 중 오류가 발생했습니다.",
        )

    db.refresh(user)
    if organization:
        db.refresh(organization)
    if workspace:
        db.refresh(workspace)
        
    return Response(status_code=201)

_DUMMY_HASH = hash_password("haha")
@router.post(
    "/login",
    status_code=status.HTTP_200_OK,
    response_model=LoginResponse,
    responses={
        200: {"description": "로그인 성공"},
        401: {"description": "인증 실패"},
    })
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> LoginResponse:
    """사용자 인증에 성공하면 마지막 로그인 시간을 갱신하고 토큰을 발급한다."""

    # 1) 사용자 조회
    user = db.scalar(select(User).where(User.id == payload.id))

    # 2) 패스워드 검증 (사용자가 없어도 가짜 해시로 검증)
    hashed = user.password_hash if user else _DUMMY_HASH
    pwd_ok = verify_password(payload.password, hashed)

    # 3) 실패 처리
    if not user or not pwd_ok or not user.active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="아이디 또는 비밀번호가 올바르지 않습니다.",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    nick = user.nickname

    try:
        user.last_login = datetime.utcnow()
        db.commit()
    except Exception:
        db.rollback()

    access_token = create_access_token(subject=str(user.idx))
    refresh_token = create_refresh_token(subject=str(user.idx))

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        nickname=nick
    )
