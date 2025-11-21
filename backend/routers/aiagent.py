"""AI Agent 관련 API 라우터."""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from notion_client.errors import APIResponseError

from ai_module import WorkspaceAgentOrchestrator
from notions.notionAuth import NotionCredentialError
from dependencies import get_current_user
from models import User
from schema.aiagent import SearchRequest, SearchResponse
from utils.db import get_db
from utils.workspace import WorkspaceResolutionError, get_workspace_context

router = APIRouter(prefix="/aiagent", tags=["aiagent"])

logger = logging.getLogger("arcana")
_orchestrator = WorkspaceAgentOrchestrator()


@router.post(
    "/search",
    response_model=SearchResponse,
    summary="워크스페이스 RAG 검색",
)
async def search_workspace_documents(
    payload: SearchRequest,
    *,
    request: Request,
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

    async def _wait_for_disconnect(req: Request) -> bool:
        while True:
            if await req.is_disconnected():
                return True
            await asyncio.sleep(0.1)

    orchestrator_task = asyncio.create_task(
        _orchestrator.run(
            db=db,
            user_idx=user.idx,
            workspace=context.workspace,
            storage_uri=storage_uri,
            query=payload.query,
        )
    )
    disconnect_task = asyncio.create_task(_wait_for_disconnect(request))

    done, _ = await asyncio.wait(
        {orchestrator_task, disconnect_task},
        return_when=asyncio.FIRST_COMPLETED,
    )

    if disconnect_task in done and disconnect_task.result():
        orchestrator_task.cancel()
        try:
            await orchestrator_task
        except asyncio.CancelledError:
            logger.info("검색 작업이 클라이언트 연결 종료로 취소되었습니다.")
        raise HTTPException(
            status_code=499,
            detail="클라이언트 연결이 종료되었습니다.",
        )

    disconnect_task.cancel()
    try:
        execution = orchestrator_task.result()
    except asyncio.CancelledError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="검색 작업이 취소되었습니다.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except NotionCredentialError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except APIResponseError as exc:
        status_code = exc.status or status.HTTP_502_BAD_GATEWAY
        detail = getattr(exc, "message", str(exc))
        raise HTTPException(
            status_code=status_code,
            detail=f"Notion API 호출 실패: {detail}",
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

    response = SearchResponse.from_execution(execution)

    if logger.isEnabledFor(logging.DEBUG):
        log_payload = {
            "mode": execution.mode,
            "question": execution.result.question,
            "answer": response.answer,
            "citations": [
                asdict(citation) for citation in execution.result.citations
            ],
            "notion_page_id": execution.notion_page_id,
        }
        logger.debug(
            "Agent response: %s",
            json.dumps(log_payload, ensure_ascii=False),
        )

    return response
