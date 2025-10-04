"""Notion 연동 관련 FastAPI 라우터."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from dependencies import get_current_user
from models import (
    DataSource,
    Membership,
    NotionOauthCredentials,
    User,
    Workspace,
    WorkspaceType,
)
from utils.db import get_db

from fastapi.responses import RedirectResponse
from typing import Optional
from notions.notion import (
    build_authorize_url,
    make_state,
    verify_state,
    exchange_code_for_tokens,
    apply_oauth_tokens,
)


router = APIRouter(prefix="/notion", tags=["notion"])


def _resolve_workspace(db: Session, user: User) -> Workspace:
    try:
        workspace_type = WorkspaceType(user.type)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="알 수 없는 워크스페이스 유형입니다.",
        ) from exc

    if workspace_type is WorkspaceType.personal:
        workspace = db.scalar(
            select(Workspace).where(
                Workspace.type == WorkspaceType.personal.value,
                Workspace.owner_user_idx == user.idx,
            )
        )
    else:
        membership = db.scalar(
            select(Membership)
            .where(Membership.user_idx == user.idx)
            .order_by(Membership.idx)
            .limit(1)
        )
        workspace = None
        if membership:
            workspace = db.scalar(
                select(Workspace).where(
                    Workspace.type == WorkspaceType.organization.value,
                    Workspace.organization_idx == membership.organization_idx,
                )
            )

    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="사용자 워크스페이스를 찾을 수 없습니다.",
        )

    return workspace


def _ensure_notion_resources(
    db: Session, *, user: User, workspace: Workspace
):
    data_source = db.scalar(
        select(DataSource).where(
            DataSource.workspace_idx == workspace.idx,
            DataSource.type == "notion",
        )
    )

    if not data_source:
        data_source = DataSource(
            workspace_idx=workspace.idx,
            type="notion",
            name="Notion",
            status="disconnected",
        )
        db.add(data_source)
        db.flush()

    credential = db.scalar(
        select(NotionOauthCredentials).where(
            NotionOauthCredentials.data_source_idx == data_source.idx,
            NotionOauthCredentials.user_idx == user.idx,
        )
    )

    if not credential:
        credential = NotionOauthCredentials(
            user_idx=user.idx,
            data_source_idx=data_source.idx,
            provider="notion",
            bot_id=f"pending-{data_source.idx}-{user.idx}",
            token_type="bearer",
            access_token="",
        )
        db.add(credential)
        db.flush()

    db.commit()
    db.refresh(data_source)
    db.refresh(credential)
    
    return credential


@router.post(
    "/connect",
    status_code=status.HTTP_200_OK,
    summary="Notion 연동",
)
def ensure_notion_connection(
    *,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """로그인한 사용자의 워크스페이스에 Notion 데이터 소스와 자격 증명을 보장한다."""
    workspace = _resolve_workspace(db, user)
    credential = _ensure_notion_resources(db, user=user, workspace=workspace)
    
    # state 생성 후 Notion 동의 화면으로 리디렉션
    state = make_state(cred_idx=credential.idx, user_idx=user.idx)
    url = build_authorize_url(state)
    
    return {"authorize_url": url}


@router.get("/oauth/callback", summary="Notion OAuth 콜백")
async def notion_oauth_callback(
    *,
    code: Optional[str] = None,
    state: Optional[str] = None,
    db: Session = Depends(get_db),
):
    if not code or not state:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="code/state 누락")

    # state 검증 → cred 식별
    try:
        cred_idx, _uid = verify_state(state)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    cred = db.get(NotionOauthCredentials, cred_idx)
    if not cred:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="자격증명을 찾을 수 없습니다.")

    # 토큰 교환 → credential 업데이트
    try:
        token_json = await exchange_code_for_tokens(code)
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Notion 토큰 교환 실패: {e}")

    cred = apply_oauth_tokens(db, cred, token_json, mark_connected=True)

    # 프론트랑 연동시 RedirectResponse를 사용해야함
    return {
        "message": "Notion 연동이 완료되었습니다.",
    }