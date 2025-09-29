"""Notion OAuth 및 페이지 조회 라우터."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from notions import (
    PagesResponse,
    api_refresh_token,
    get_page_content,
    get_workspace_id_dep,
    list_my_pages,
    login as notion_login,
    oauth_callback as notion_oauth_callback,
)
from utils.db import get_db


router = APIRouter(tags=["notion"])


@router.get("/login", include_in_schema=False)
async def login_route():
    """Notion 동의 화면으로 리다이렉트한다."""

    return await notion_login()


@router.get("/oauth/callback", include_in_schema=False)
async def oauth_callback_route(
    code: Optional[str] = None,
    state: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Notion OAuth 콜백을 처리해 액세스 토큰을 저장한다."""

    return await notion_oauth_callback(code, state, db)


@router.get("/me/pages", response_model=PagesResponse)
async def list_my_pages_route(
    full: bool = Query(
        False,
        description="True면 각 페이지의 콘텐츠 트리까지 포함(부하 큼)",
    ),
    limit: Optional[int] = Query(
        None,
        ge=1,
        le=1000,
        description="가져올 최대 페이지 수(없으면 모두)",
    ),
    workspace_id: str = Depends(get_workspace_id_dep),
    db: Session = Depends(get_db),
):
    """현재 워크스페이스의 Notion 페이지 목록을 조회한다."""

    return await list_my_pages(full, limit, workspace_id, db)


@router.get("/me/pages/{page_id}/content")
async def get_page_content_route(
    page_id: str,
    workspace_id: str = Depends(get_workspace_id_dep),
    db: Session = Depends(get_db),
):
    """특정 페이지의 블록 콘텐츠 트리를 반환한다."""

    return await get_page_content(page_id, workspace_id, db)


@router.post("/me/token/refresh")
async def api_refresh_token_route(
    workspace_id: str = Depends(get_workspace_id_dep),
    db: Session = Depends(get_db),
):
    """저장된 리프레시 토큰으로 새 액세스 토큰을 발급받는다."""

    return await api_refresh_token(workspace_id, db)

