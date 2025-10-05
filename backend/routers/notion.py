"""Notion 연동 관련 FastAPI 라우터."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response, status
from notion_client.errors import APIResponseError
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

from backend.notions.notionAuth import (
    build_authorize_url,
    make_state,
    verify_state,
    exchange_code_for_tokens,
    apply_oauth_tokens,
)
from backend.notions import pull_all_shared_page_text


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
    include_in_schema=False
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


@router.get("/oauth/callback", summary="Notion OAuth 콜백", include_in_schema=False)
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

    return Response(status_code=200)


def _get_connected_credential(
    db: Session, *, user: User, workspace: Workspace
) -> NotionOauthCredentials:
    data_source = db.scalar(
        select(DataSource).where(
            DataSource.workspace_idx == workspace.idx,
            DataSource.type == "notion",
        )
    )

    if not data_source or data_source.status != "connected":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Notion 연동이 필요합니다.",
        )

    credential = db.scalar(
        select(NotionOauthCredentials).where(
            NotionOauthCredentials.data_source_idx == data_source.idx,
            NotionOauthCredentials.user_idx == user.idx,
        )
    )

    if not credential or not credential.access_token:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Notion 연동 토큰을 찾을 수 없습니다.",
        )

    return credential


@router.post(
    "/pages/pull",
    summary="Notion 공유 페이지 전체 텍스트 수집",
)
async def pull_all_pages(
    *,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    workspace = _resolve_workspace(db, user)
    credential = _get_connected_credential(db, user=user, workspace=workspace)

    try:
        payload = await pull_all_shared_page_text(db, credential)
    except APIResponseError as exc:
        status_code = exc.status or status.HTTP_502_BAD_GATEWAY
        detail = getattr(exc, "message", str(exc))
        raise HTTPException(
            status_code=status_code,
            detail=f"Notion API 호출 실패: {detail}",
        ) from exc
    except Exception as exc:  # pragma: no cover - defensive clause
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Notion 데이터 수집 중 오류가 발생했습니다: {exc}",
        ) from exc

    return payload
