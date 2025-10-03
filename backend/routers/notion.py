"""Notion 연동 관련 FastAPI 라우터."""

from __future__ import annotations

from typing import Tuple

from fastapi import APIRouter, Depends, Header, HTTPException, status, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from models import (
    DataSource,
    Membership,
    NotionOauthCredentials,
    User,
    Workspace,
    WorkspaceType,
)
from utils.auth import AuthorizationError, InvalidTokenError, get_user_from_token
from utils.db import get_db


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


@router.post(
    "/connect/ensure",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Notion 연동을 위한 데이터 소스를 준비합니다.",
)
def ensure_notion_connection(
    *,
    db: Session = Depends(get_db),
    authorization: str = Header(..., alias="Authorization"),
):
    """로그인한 사용자의 워크스페이스에 Notion 데이터 소스와 자격 증명을 보장한다."""

    try:
        user = get_user_from_token(db, authorization)
    except AuthorizationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc
    workspace = _resolve_workspace(db, user)
    _ensure_notion_resources(db, user=user, workspace=workspace)

    return Response(status_code=204)
