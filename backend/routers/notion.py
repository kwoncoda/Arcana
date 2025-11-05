"""Notion 연동 관련 FastAPI 라우터."""

from __future__ import annotations

from datetime import datetime, timezone
import json  
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
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

    return RedirectResponse(url="http://localhost:5173/dashboard")


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

    rag_index = db.scalar(
        select(RagIndex).where(
            RagIndex.workspace_idx == workspace.idx,
            RagIndex.name == DEFAULT_RAG_INDEX_NAME,
        )
    )
    last_synced_at = rag_index.updated if rag_index else None

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
        
    workspace_metadata = {  # 워크스페이스 정보를 문서 메타데이터로 포함하기 위한 딕셔너리 생성 주석
        "workspace_idx": workspace.idx,  # 워크스페이스 고유 식별자 저장 주석
        "workspace_type": workspace.type,  # 워크스페이스 유형 저장 주석
        "workspace_name": workspace.name,  # 워크스페이스 이름 저장 주석
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
    rag_index.object_count = stats.page_count
    rag_index.vector_count = stats.vector_count
    rag_index.status = "ready"
    rag_index.updated = datetime.now(timezone.utc)

    try:
        db.commit()
    except Exception as exc:  # pragma: no cover - defensive clause
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="RAG 인덱스 메타데이터를 갱신하는 중 오류가 발생했습니다.",
        ) from exc

    return {  # API 응답 페이로드를 구성하는 주석
        **payload,  # 원본 Notion 수집 결과를 포함하는 주석
        "jsonl_records": jsonl_records,  # 전처리된 JSONL 레코드 리스트를 포함하는 주석
        "jsonl_text": jsonl_text,  # 직렬화된 JSONL 문자열을 포함하는 주석
        "ingested_chunks": ingested_count,  # Chroma에 적재된 청크 수를 포함하는 주석
        "last_synced_at": last_synced_at.isoformat() if last_synced_at else None,  # 직전 동기화 기준 시각 주석
    }
