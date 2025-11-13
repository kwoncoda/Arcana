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
    GoogleDriveFileSnapshot,
    GoogleDriveOauthCredentials,
    GoogleDriveSyncState,
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
from google_drive.change_stream import (
    ChangeBatch,
    collect_workspace_changes,
    get_start_page_token,
    list_workspace_files,
)
from google_drive.files import (
    GoogleDriveAPIError,
    GoogleDriveFile,
    build_documents_from_records,
    build_records_from_files,
    fetch_authorized_text_files,
)

from rag.chroma import ChromaRAGService

import json
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

import os
FRONT_MAIN_REDIRECT_URL=os.getenv("FRONT_MAIN_REDIRECT_URL")

router = APIRouter(prefix="/google-drive", tags=["google-drive"])
rag_service = ChromaRAGService()


def _resolve_root_folder_id(credential: GoogleDriveOauthCredentials) -> str:
    """워크스페이스로 지정된 Google Drive 루트 폴더 ID를 반환한다."""

    payload: Any = credential.provider_payload or {}
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            payload = {}

    if isinstance(payload, dict):
        root_id = (
            payload.get("workspace_root_id")
            or payload.get("root_folder_id")
            or payload.get("selected_folder_id")
        )
    else:
        root_id = None

    return str(root_id) if root_id else "root"


def _parse_google_datetime(value: Optional[str]) -> Optional[datetime]:
    """Google ISO8601 문자열을 UTC datetime으로 변환한다."""

    if not value:
        return None

    try:
        normalized = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _safe_int(value: Any) -> Optional[int]:
    """정수 변환 실패 시 None을 반환한다."""

    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _should_reindex(
    metadata: Dict[str, Any], snapshot: Optional[GoogleDriveFileSnapshot]
) -> bool:
    """파일 메타데이터 변화로 재색인 필요 여부를 판단한다."""

    if snapshot is None:
        return True

    checksum = metadata.get("md5Checksum") or None
    version = _safe_int(metadata.get("version"))
    modified_time = _parse_google_datetime(metadata.get("modifiedTime"))

    if checksum:
        return snapshot.md5_checksum != checksum

    if version is not None:
        if snapshot.version is None:
            return True
        return snapshot.version != version

    if snapshot.version is not None:
        return True

    if not modified_time:
        return False

    if snapshot.modified_time is None:
        return True

    return snapshot.modified_time != modified_time


def _apply_snapshot_metadata(
    snapshot: GoogleDriveFileSnapshot,
    metadata: Dict[str, Any],
    *,
    synced_at: datetime,
    update_synced: bool,
) -> None:
    """스냅샷 레코드에 최신 메타데이터를 반영한다."""

    snapshot.name = metadata.get("name") or snapshot.name
    mime_type = metadata.get("mimeType") or snapshot.mime_type
    snapshot.mime_type = mime_type
    snapshot.md5_checksum = metadata.get("md5Checksum") or None
    snapshot.version = _safe_int(metadata.get("version"))
    snapshot.modified_time = _parse_google_datetime(metadata.get("modifiedTime"))
    snapshot.web_view_link = metadata.get("webViewLink") or snapshot.web_view_link
    if update_synced:
        snapshot.last_synced = synced_at
    snapshot.updated = synced_at


def _ensure_sync_state(db: Session, data_source: DataSource) -> GoogleDriveSyncState:
    """Google Drive 동기화 상태 레코드를 조회하거나 생성한다."""

    sync_state = db.scalar(
        select(GoogleDriveSyncState).where(
            GoogleDriveSyncState.data_source_idx == data_source.idx
        )
    )

    if sync_state:
        return sync_state

    sync_state = GoogleDriveSyncState(data_source_idx=data_source.idx)
    db.add(sync_state)
    db.commit()
    db.refresh(sync_state)
    return sync_state


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
    return RedirectResponse(url=FRONT_MAIN_REDIRECT_URL)


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
    if not data_source:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Google Drive 데이터 소스를 찾을 수 없습니다.",
        )

    sync_state = _ensure_sync_state(db, data_source)
    last_synced_at = data_source.synced

    storage_path = ensure_workspace_storage(workspace.name)
    pdf_download_dir = storage_path / "googledrive" / "pdf"
    root_folder_id = _resolve_root_folder_id(credential)

    now = datetime.now(timezone.utc)
    bootstrapped = False
    skipped_files: List[Dict[str, str]] = []
    removed_file_ids: List[str] = []
    index_candidates: List[Dict[str, Any]] = []

    if not sync_state.start_page_token:
        try:
            start_token = await get_start_page_token(credential.access_token)
            raw_files, bootstrap_skipped = await list_workspace_files(
                credential.access_token,
                root_id=root_folder_id,
            )
        except GoogleDriveAPIError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Google Drive API 오류: {exc}",
            ) from exc

        skipped_files.extend(bootstrap_skipped)
        index_candidates = raw_files
        new_start_token = start_token
        bootstrapped = True
    else:
        try:
            change_batch: ChangeBatch = await collect_workspace_changes(
                credential.access_token,
                page_token=sync_state.start_page_token,
                root_id=root_folder_id,
            )
        except GoogleDriveAPIError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Google Drive Changes API 오류: {exc}",
            ) from exc

        index_candidates = change_batch.to_index
        removed_file_ids = list(dict.fromkeys(change_batch.to_remove))
        skipped_files.extend(change_batch.skipped)
        new_start_token = change_batch.new_start_page_token or sync_state.start_page_token

    candidate_ids = {meta.get("id") for meta in index_candidates if meta.get("id")}
    candidate_ids.update(removed_file_ids)
    candidate_ids.discard(None)

    snapshots: Dict[str, GoogleDriveFileSnapshot] = {}
    if candidate_ids:
        snapshot_rows = db.scalars(
            select(GoogleDriveFileSnapshot).where(
                GoogleDriveFileSnapshot.data_source_idx == data_source.idx,
                GoogleDriveFileSnapshot.file_id.in_(candidate_ids),
            )
        ).all()
        snapshots = {row.file_id: row for row in snapshot_rows}

    files_to_convert: List[Dict[str, Any]] = []
    for metadata in index_candidates:
        file_id = metadata.get("id")
        if not file_id:
            continue
        snapshot = snapshots.get(file_id)
        if _should_reindex(metadata, snapshot):
            files_to_convert.append(metadata)
        elif snapshot:
            _apply_snapshot_metadata(snapshot, metadata, synced_at=now, update_synced=False)

    converted_files: List[GoogleDriveFile] = []
    conversion_skipped: List[Dict[str, str]] = []
    if files_to_convert:
        try:
            converted_files, conversion_skipped = await fetch_authorized_text_files(
                credential.access_token,
                download_dir=pdf_download_dir,
                files_override=files_to_convert,
            )
        except GoogleDriveAPIError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Google Drive 파일 변환 오류: {exc}",
            ) from exc

    skipped_files.extend(conversion_skipped)

    meta_by_id = {metadata.get("id"): metadata for metadata in index_candidates if metadata.get("id")}

    for file in converted_files:
        file_meta = meta_by_id.get(file.file_id)
        if not file_meta:
            continue
        snapshot = snapshots.get(file.file_id)
        if not snapshot:
            snapshot = GoogleDriveFileSnapshot(
                data_source_idx=data_source.idx,
                file_id=file.file_id,
                mime_type=file.mime_type,
            )
            db.add(snapshot)
            snapshots[file.file_id] = snapshot
        _apply_snapshot_metadata(snapshot, file_meta, synced_at=now, update_synced=True)

    removed_ids_clean: List[str] = []
    for file_id in removed_file_ids:
        if not file_id:
            continue
        removed_ids_clean.append(file_id)
        snapshot = snapshots.pop(file_id, None)
        if snapshot:
            db.delete(snapshot)

    workspace_metadata = {
        "workspace_idx": workspace.idx,
        "workspace_type": workspace.type,
        "workspace_name": workspace.name,
        "provider": "googledrive",
    }

    records = build_records_from_files(converted_files)
    documents = build_documents_from_records(records, workspace_metadata)

    jsonl_lines = [json.dumps(record, ensure_ascii=False) for record in records]
    jsonl_text = "\n".join(jsonl_lines)

    rag_index = db.scalar(
        select(RagIndex).where(
            RagIndex.workspace_idx == workspace.idx,
            RagIndex.name == DEFAULT_RAG_INDEX_NAME,
        )
    )

    storage_uri = rag_index.storage_uri if rag_index and rag_index.storage_uri else str(storage_path)

    removed_pages = 0
    if removed_ids_clean:
        removed_pages = rag_service.delete_documents(
            workspace.idx,
            workspace.name,
            removed_ids_clean,
            storage_uri=storage_uri,
        )

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
    rag_index.object_count = stats.page_count
    rag_index.vector_count = stats.vector_count
    rag_index.status = "ready"
    rag_index.updated = now

    data_source.synced = now
    db.add(data_source)

    sync_state.start_page_token = new_start_token
    sync_state.last_synced = now
    if bootstrapped:
        sync_state.bootstrapped_at = now
    db.add(sync_state)

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
                "pdf_path": str(file.pdf_path),
                "text_length": len(file.text),
            }
            for file in converted_files
        ],
        "jsonl_records": records,
        "jsonl_text": jsonl_text,
        "skipped_files": skipped_files,
        "removed_files": removed_ids_clean,
        "ingested_chunks": ingested_count,
        "removed_pages": removed_pages,
        "last_synced_at": last_synced_at.isoformat() if last_synced_at else None,
        "synced_at": now.isoformat(),
        "start_page_token": new_start_token,
        "bootstrapped": bootstrapped,
    }
