"""Google Drive OAuth endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from dependencies import get_current_user
from models import DataSource, GoogleDriveOauthCredentials, User, Workspace
from utils.db import get_db
from utils.workspace import resolve_user_primary_workspace, WorkspaceResolutionError

from google_drive import (
    GoogleDriveCredentialError,
    apply_oauth_tokens,
    build_authorize_url,
    exchange_code_for_tokens,
    get_connected_user_credential,
    make_state,
    verify_state,
)

router = APIRouter(prefix="/google-drive", tags=["google-drive"])


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
