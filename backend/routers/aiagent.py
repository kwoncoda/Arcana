"""AI Agent 관련 API 라우터."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from ai_module import WorkspaceRAGSearchAgent
from dependencies import get_current_user
from models import User
from schema.aiagent import SearchRequest, SearchResponse
from utils.db import get_db
from utils.workspace import WorkspaceResolutionError, get_workspace_context

router = APIRouter(prefix="/aiagent", tags=["aiagent"])

logger = logging.getLogger("arcana")
_search_agent = WorkspaceRAGSearchAgent()


@router.post(
    "/search",
    response_model=SearchResponse,
    summary="워크스페이스 RAG 검색",
)
async def search_workspace_documents(
    payload: SearchRequest,
    *,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SearchResponse:
    """사용자 워크스페이스의 RAG 인덱스를 기반으로 질의에 답변한다."""

    try:
        context = get_workspace_context(db, user)
    except WorkspaceResolutionError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    storage_uri = context.rag_index.storage_uri if context.rag_index else None

    try:
        result = await run_in_threadpool(
            _search_agent.search,
            workspace_idx=context.workspace.idx,
            workspace_name=context.workspace.name,
            query=payload.query,
            storage_uri=storage_uri,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
    except Exception as exc:  # pragma: no cover - 예기치 못한 오류 방어
        logger.exception("RAG 검색 처리 중 예외 발생")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="RAG 검색 중 오류가 발생했습니다.",
        ) from exc

    return SearchResponse.from_result(result)
