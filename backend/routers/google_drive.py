"""Google Drive OAuth endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from dependencies import get_current_user
from models import (
    DEFAULT_RAG_INDEX_NAME,
    DataSource,
    GoogleDriveOauthCredentials,
    RagIndex,
    User,
    Workspace,
)
from utils.db import get_db
from utils.workspace import resolve_user_primary_workspace, WorkspaceResolutionError
from utils.workspace_storage import ensure_workspace_storage

from google_drive import (
    GoogleDriveCredentialError,
    apply_oauth_tokens,
    build_authorize_url,
    exchange_code_for_tokens,
    get_connected_user_credential,
    ensure_valid_access_token,
    make_state,
    verify_state,
)

from google_drive.files import (
    GoogleDriveAPIError,
    build_documents_from_records,
    build_records_from_files,
    fetch_authorized_text_files,
)

from rag.chroma import ChromaRAGService

import json
from datetime import datetime, timezone

router = APIRouter(prefix="/google-drive", tags=["google-drive"])
rag_service = ChromaRAGService()


def _resolve_workspace(db: Session, user: User) -> Workspace:
    try:
        return resolve_user_primary_workspace(db, user)
    except WorkspaceResolutionError as exc:  # pragma: no cover - 방어적 코드
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


def _ensure_google_resources(db: Session, *, user: User, workspace: Workspace) -> GoogleDriveOauthCredentials:
    data_source = db.scalar(
        select(DataSource).where(
            DataSource.workspace_idx == workspace.idx,
            DataSource.type == "googledrive",
        )
    )

    if not data_source:
        data_source = DataSource(
            workspace_idx=workspace.idx,
            type="googledrive",
            name="Google Drive",
            status="disconnected",
        )
        db.add(data_source)
        db.flush()

    credential = db.scalar(
        select(GoogleDriveOauthCredentials).where(
            GoogleDriveOauthCredentials.data_source_idx == data_source.idx,
            GoogleDriveOauthCredentials.user_idx == user.idx,
        )
    )

    if not credential:
        credential = GoogleDriveOauthCredentials(
            user_idx=user.idx,
            data_source_idx=data_source.idx,
            provider="googledrive",
            token_type="Bearer",
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
    summary="Google Drive 연동",
    include_in_schema=False,
)
def ensure_google_drive_connection(
    *,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Ensure Google Drive data source and return authorization URL."""

    workspace = _resolve_workspace(db, user)
    credential = _ensure_google_resources(db, user=user, workspace=workspace)

    state = make_state(cred_idx=credential.idx, user_idx=user.idx)
    url = build_authorize_url(state)
    return {"authorize_url": url}


@router.get(
    "/oauth/callback",
    summary="Google Drive OAuth 콜백",
    include_in_schema=False,
)
async def google_drive_oauth_callback(
    *,
    code: str | None = None,
    state: str | None = None,
    db: Session = Depends(get_db),
):
    if not code or not state:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="code/state 누락")

    try:
        cred_idx, _uid = verify_state(state)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    credential = db.get(GoogleDriveOauthCredentials, cred_idx)
    if not credential:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="자격증명을 찾을 수 없습니다.")

    try:
        token_payload, user_info = await exchange_code_for_tokens(code)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Google OAuth 토큰 교환 실패: {exc}",
        ) from exc

    apply_oauth_tokens(db, credential, token_payload, user_info, mark_connected=True)
    return RedirectResponse(url="http://localhost:5173/dashboard")


def get_connected_google_credential(
    db: Session, *, user: User, workspace: Workspace
) -> GoogleDriveOauthCredentials:
    try:
        return get_connected_user_credential(
            db,
            workspace_idx=workspace.idx,
            user_idx=user.idx,
        )
    except GoogleDriveCredentialError as exc:  # pragma: no cover - 방어적 코드
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@router.post(
    "/files/pull",
    summary="Google Drive 파일을 수집하고 RAG에 적재",
)
async def pull_google_drive_files(
    *,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    workspace = _resolve_workspace(db, user)
    credential = get_connected_google_credential(db, user=user, workspace=workspace)

    credential = await ensure_valid_access_token(db, credential)

    data_source = db.scalar(
        select(DataSource).where(
            DataSource.workspace_idx == workspace.idx,
            DataSource.type == "googledrive",
        )
    )
    last_synced_at = data_source.synced if data_source else None

    try:
        files, skipped = await fetch_authorized_text_files(
            credential.access_token,
            modified_after=last_synced_at,
        )
    except GoogleDriveAPIError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Google Drive API 오류: {exc}",
        ) from exc

    workspace_metadata = {
        "workspace_idx": workspace.idx,
        "workspace_type": workspace.type,
        "workspace_name": workspace.name,
        "provider": "googledrive",
    }

    records = build_records_from_files(files)
    documents = build_documents_from_records(records, workspace_metadata)

    jsonl_lines = [json.dumps(record, ensure_ascii=False) for record in records]
    jsonl_text = "\n".join(jsonl_lines)

    storage_path = ensure_workspace_storage(workspace.name)
    rag_index = db.scalar(
        select(RagIndex).where(
            RagIndex.workspace_idx == workspace.idx,
            RagIndex.name == DEFAULT_RAG_INDEX_NAME,
        )
    )

    storage_uri = rag_index.storage_uri if rag_index and rag_index.storage_uri else str(storage_path)

    try:
        if documents:
            ingested_count = rag_service.replace_documents(
                workspace.idx,
                workspace.name,
                documents,
                storage_uri=storage_uri,
            )
        else:
            ingested_count = 0
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
    except Exception as exc:  # pragma: no cover - 방어적 코드
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Google Drive 동기화 결과를 저장하는 중 오류가 발생했습니다.",
        ) from exc

    return {
        "files": [
            {
                "file_id": file.file_id,
                "name": file.name,
                "mime_type": file.mime_type,
                "modified_time": file.modified_time,
                "format": file.format,
                "text_length": len(file.text),
            }
            for file in files
        ],
        "jsonl_records": records,
        "jsonl_text": jsonl_text,
        "skipped_files": skipped,
        "ingested_chunks": ingested_count,
        "last_synced_at": last_synced_at.isoformat() if last_synced_at else None,
        "synced_at": now.isoformat(),
    }
