"""Notion 연동 관련 FastAPI 라우터."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse, JSONResponse
from notion_client.errors import APIResponseError
from sqlalchemy import select
from sqlalchemy.orm import Session

from dependencies import get_current_user
from models import (
    DEFAULT_RAG_INDEX_NAME,
    DataSource,
    NotionOauthCredentials,
    RagIndex,
    User,
    Workspace,
)
from utils.db import get_db
from utils.workspace_storage import ensure_workspace_storage
from utils.workspace import resolve_user_primary_workspace, WorkspaceResolutionError

from notions.notionAuth import (
    build_authorize_url,
    make_state,
    verify_state,
    exchange_code_for_tokens,
    apply_oauth_tokens,
    get_connected_user_credential,
    NotionCredentialError,
)

from notions.notionPull import (
    pull_all_shared_page_text,  # 노션 페이지 원본 텍스트를 수집하는 헬퍼 임포트 주석
)

from notions.ragTransform import (
    build_jsonl_records_from_pages,  # 페이지 데이터를 JSONL 레코드로 변환하는 헬퍼 임포트 주석
    build_documents_from_records,  # JSONL 레코드를 LangChain 문서로 변환하는 헬퍼 임포트 주석
)

from rag.chroma import ChromaRAGService  # Chroma 기반 RAG 서비스를 임포트하는 주석

import os
from urllib.parse import urlencode, urlparse, urlunparse, parse_qsl
FRONT_MAIN_REDIRECT_URL=os.getenv("FRONT_MAIN_REDIRECT_URL")

import logging
logger = logging.getLogger("arcana") 

router = APIRouter(prefix="/notion", tags=["notion"])
rag_service = ChromaRAGService()  # 노션 데이터를 RAG 인덱스에 적재하기 위한 서비스 인스턴스 생성 주석


def _resolve_workspace(db: Session, user: User) -> Workspace:
    try:
        return resolve_user_primary_workspace(db, user)
    except WorkspaceResolutionError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


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


def _append_query_params(base_url: str, params: dict[str, str | None]) -> str:
    parsed = urlparse(base_url)
    current = dict(parse_qsl(parsed.query))
    current.update({k: v for k, v in params.items() if v is not None})
    new_query = urlencode(current)
    return urlunparse(parsed._replace(query=new_query))


async def _sync_notion_workspace(
    db: Session,
    *,
    credential: NotionOauthCredentials,
    workspace: Workspace,
    data_source: DataSource,
):
    rag_index = db.scalar(
        select(RagIndex).where(
            RagIndex.workspace_idx == workspace.idx,
            RagIndex.name == DEFAULT_RAG_INDEX_NAME,
        )
    )
    last_synced_at = data_source.synced if data_source else None

    payload = await pull_all_shared_page_text(
        db,
        credential,
        updated_after=last_synced_at,
    )

    workspace_metadata = {
        "workspace_idx": workspace.idx,
        "workspace_type": workspace.type,
        "workspace_name": workspace.name,
    }
    jsonl_records = build_jsonl_records_from_pages(payload.get("pages", []))
    documents = build_documents_from_records(jsonl_records, workspace_metadata)
    jsonl_lines = [json.dumps(record, ensure_ascii=False) for record in jsonl_records]
    jsonl_text = "\n".join(jsonl_lines)

    storage_path = ensure_workspace_storage(workspace.name)
    storage_uri = rag_index.storage_uri if rag_index and rag_index.storage_uri else str(storage_path)

    try:
        ingested_count = rag_service.replace_documents(
            workspace.idx,
            workspace.name,
            documents,
            storage_uri=storage_uri,
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"RAG 적재 실패: {exc}",
        ) from exc

    if not rag_index:
        rag_index = RagIndex(
            workspace_idx=workspace.idx,
            name=DEFAULT_RAG_INDEX_NAME,
            index_type="chroma",
            storage_uri=str(storage_path),
            status="ready",
        )
        db.add(rag_index)
    else:
        rag_index.storage_uri = storage_uri
        rag_index.index_type = "chroma"

    stats = rag_service.collection_stats(
        workspace.idx,
        workspace.name,
        storage_uri=rag_index.storage_uri,
    )
    rag_index.object_count = stats.page_count
    rag_index.vector_count = stats.vector_count
    rag_index.status = "ready"
    rag_index.updated = datetime.now(timezone.utc)

    data_source.synced = datetime.now(timezone.utc)
    db.add(data_source)
    db.add(rag_index)

    db.commit()

    return {
        "jsonl_records": jsonl_records,
        "jsonl_text": jsonl_text,
        "ingested_pages": ingested_count,
        "last_synced_at": last_synced_at.isoformat() if last_synced_at else None,
        "synced_at": data_source.synced.isoformat() if data_source.synced else None,
    }


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


@router.get(
    "/status",
    summary="Notion 연동 상태 조회",
    include_in_schema=False,
)
def notion_connection_status(
    *,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """현재 워크스페이스의 Notion 연동 상태를 반환한다."""

    workspace = _resolve_workspace(db, user)
    data_source = db.scalar(
        select(DataSource).where(
            DataSource.workspace_idx == workspace.idx,
            DataSource.type == "notion",
        )
    )

    credential = None
    if data_source:
        credential = db.scalar(
            select(NotionOauthCredentials).where(
                NotionOauthCredentials.data_source_idx == data_source.idx,
                NotionOauthCredentials.user_idx == user.idx,
            )
        )

    connected = bool(
        data_source
        and credential
        and data_source.status == "connected"
        and credential.access_token
    )

    return {
        "connected": connected,
        "status": data_source.status if data_source else "disconnected",
        "synced_at": data_source.synced.isoformat() if data_source and data_source.synced else None,
    }


@router.get("/oauth/callback", summary="Notion OAuth 콜백", include_in_schema=False)
async def notion_oauth_callback(
    *,
    request: Request,
    code: Optional[str] = None,
    state: Optional[str] = None,
    db: Session = Depends(get_db),
):
    if not code or not state:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="code/state 누락")

    try:
        cred_idx, user_idx = verify_state(state)
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
    sync_failed = False
    sync_result = None

    user = db.get(User, user_idx) if user_idx else None
    if user:
        try:
            workspace = _resolve_workspace(db, user)
            data_source = db.scalar(
                select(DataSource).where(
                    DataSource.workspace_idx == workspace.idx,
                    DataSource.type == "notion",
                )
            )
            if data_source:
                sync_result = await _sync_notion_workspace(
                    db,
                    credential=cred,
                    workspace=workspace,
                    data_source=data_source,
                )
            else:
                sync_failed = True
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Notion sync after OAuth failed: %s", exc)
            sync_failed = True

    if "application/json" in request.headers.get("accept", "").lower():
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "connected": True,
                "sync_failed": sync_failed,
                "sync_result": sync_result,
            },
        )

    if not FRONT_MAIN_REDIRECT_URL:
        return {"connected": True, "sync_failed": sync_failed, "sync_result": sync_result}

    redirect_url = _append_query_params(
        FRONT_MAIN_REDIRECT_URL,
        {
            "source": "notion",
            "connected": "1",
            "syncFailed": "1" if sync_failed else "0",
        },
    )

    return RedirectResponse(url=redirect_url)


@router.post(
    "/disconnect",
    summary="Notion 연동 해제",
)
def disconnect_notion(
    *,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """현재 워크스페이스에서 Notion 연동과 RAG 데이터를 제거한다."""

    workspace = _resolve_workspace(db, user)
    data_source = db.scalar(
        select(DataSource).where(
            DataSource.workspace_idx == workspace.idx,
            DataSource.type == "notion",
        )
    )

    if not data_source or data_source.status != "connected":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Notion 데이터 소스가 연결되어 있지 않습니다.",
        )

    rag_index = db.scalar(
        select(RagIndex).where(
            RagIndex.workspace_idx == workspace.idx,
            RagIndex.name == DEFAULT_RAG_INDEX_NAME,
        )
    )

    storage_path = ensure_workspace_storage(workspace.name)
    storage_uri = rag_index.storage_uri if rag_index and rag_index.storage_uri else str(storage_path)

    before_stats = rag_service.collection_stats(
        workspace.idx,
        workspace.name,
        storage_uri=storage_uri,
    )

    try:
        rag_service.delete_where(
            workspace.idx,
            workspace.name,
            storage_uri=storage_uri,
            where={"provider": "notion"},
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"RAG 문서를 정리하는 중 오류가 발생했습니다: {exc}",
        ) from exc

    after_stats = rag_service.collection_stats(
        workspace.idx,
        workspace.name,
        storage_uri=storage_uri,
    )

    removed_vectors = max(0, before_stats.vector_count - after_stats.vector_count)
    removed_pages = max(0, before_stats.page_count - after_stats.page_count)
    now = datetime.now(timezone.utc)

    if rag_index:
        rag_index.object_count = after_stats.page_count
        rag_index.vector_count = after_stats.vector_count
        rag_index.status = "ready"
        rag_index.updated = now
        db.add(rag_index)

    credentials = list(
        db.scalars(
            select(NotionOauthCredentials).where(
                NotionOauthCredentials.data_source_idx == data_source.idx
            )
        )
    )
    for credential in credentials:
        db.delete(credential)

    data_source.status = "disconnected"
    data_source.synced = None
    db.add(data_source)

    try:
        db.commit()
    except Exception as exc:  # pragma: no cover - 트랜잭션 방어
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Notion 연동을 해제하는 중 데이터베이스 오류가 발생했습니다.",
        ) from exc

    return {
        "status": "disconnected",
        "removed_pages": removed_pages,
        "removed_vectors": removed_vectors,
        "remaining_vectors": after_stats.vector_count,
    }


def _get_connected_credential(
    db: Session, *, user: User, workspace: Workspace
) -> NotionOauthCredentials:
    try:
        return get_connected_user_credential(
            db,
            workspace_idx=workspace.idx,
            user_idx=user.idx,
        )
    except NotionCredentialError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


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

    data_source = db.scalar(
        select(DataSource).where(
            DataSource.workspace_idx == workspace.idx,
            DataSource.type == "notion",
        )
    )

    rag_index = db.scalar(
        select(RagIndex).where(
            RagIndex.workspace_idx == workspace.idx,
            RagIndex.name == DEFAULT_RAG_INDEX_NAME,
        )
    )
    last_synced_at = data_source.synced if data_source else None

    try:
        payload = await pull_all_shared_page_text(
            db,
            credential,
            updated_after=last_synced_at,
        )
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
        
    workspace_metadata = { 
        "workspace_idx": workspace.idx,
        "workspace_type": workspace.type,
        "workspace_name": workspace.name,
    }
    jsonl_records = build_jsonl_records_from_pages(payload.get("pages", []))  # 수집된 페이지를 JSONL 레코드로 전처리하는 주석
    documents = build_documents_from_records(jsonl_records, workspace_metadata)  # 전처리된 레코드를 LangChain 문서로 변환하는 주석
    jsonl_lines = [json.dumps(record, ensure_ascii=False) for record in jsonl_records]  # 레코드를 JSON 문자열로 직렬화하는 주석
    jsonl_text = "\n".join(jsonl_lines)  # JSONL 텍스트를 생성하기 위해 줄바꿈으로 결합하는 주석

    if logger.isEnabledFor(logging.DEBUG):  # 디버그 레벨에서만 전처리 결과를 기록하도록 조건을 설정하는 주석
        logger.debug("Processed Notion JSONL payload: %s", jsonl_text)  # 최종 JSONL 텍스트를 디버그 로그로 출력하는 주석

    storage_path = ensure_workspace_storage(workspace.name)
    storage_uri = str(storage_path)
    if rag_index and rag_index.storage_uri:
        storage_uri = rag_index.storage_uri

    try:
        if documents:
            ingested_count = rag_service.replace_documents(
                workspace.idx,
                workspace.name,
                documents,
                storage_uri=storage_uri,
            )  # 변환된 문서를 Chroma에 적재하고 개수 반환 주석
        else:
            ingested_count = 0
    except RuntimeError as exc:  # Azure OpenAI 구성 누락 등 구성 오류 처리 주석
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,  # 내부 서버 오류 응답 코드 지정 주석
            detail=f"RAG 적재 실패: {exc}",  # 실패 사유를 상세 메시지로 전달 주석
        ) from exc

    if not rag_index:
        rag_index = RagIndex(
            workspace_idx=workspace.idx,
            name=DEFAULT_RAG_INDEX_NAME,
            index_type="chroma",
            storage_uri=str(storage_path),
            status="ready",
        )
        db.add(rag_index)
    else:
        rag_index.storage_uri = storage_uri
        rag_index.index_type = "chroma"

    stats = rag_service.collection_stats(
        workspace.idx,
        workspace.name,
        storage_uri=rag_index.storage_uri,
    )
    now = datetime.now(timezone.utc)
    rag_index.object_count = stats.page_count
    rag_index.vector_count = stats.vector_count
    rag_index.status = "ready"
    rag_index.updated = now

    if data_source:
        data_source.synced = now
        db.add(data_source)

    try:
        db.commit()
    except Exception as exc:  # pragma: no cover - defensive clause
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="RAG 인덱스 메타데이터를 갱신하는 중 오류가 발생했습니다.",
        ) from exc

    return {
        **payload,  # 원본 Notion 수집 결과를 포함하는 주석
        "jsonl_records": jsonl_records,
        "jsonl_text": jsonl_text, 
        "ingested_chunks": ingested_count,  # Chroma에 적재된 청크 수를 포함
        "last_synced_at": last_synced_at.isoformat() if last_synced_at else None,
    }
