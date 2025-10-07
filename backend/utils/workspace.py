"""워크스페이스 관련 헬퍼."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from models import Membership, RagIndex, Workspace, WorkspaceType, DEFAULT_RAG_INDEX_NAME, User


class WorkspaceResolutionError(Exception):
    """사용자 워크스페이스를 찾지 못했을 때 발생하는 예외."""


@dataclass(slots=True)
class WorkspaceContext:
    """워크스페이스와 기본 RAG 인덱스를 묶어서 반환하기 위한 컨테이너."""

    workspace: Workspace
    rag_index: Optional[RagIndex]


def resolve_user_primary_workspace(db: Session, user: User) -> Workspace:
    """로그인한 사용자가 접근 가능한 기본 워크스페이스를 조회한다."""

    try:
        workspace_type = WorkspaceType(user.type)
    except ValueError as exc:  # pragma: no cover - 데이터 정합성 보호
        raise WorkspaceResolutionError("알 수 없는 워크스페이스 유형입니다.") from exc

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
        raise WorkspaceResolutionError("사용자 워크스페이스를 찾을 수 없습니다.")

    return workspace


def get_workspace_context(db: Session, user: User) -> WorkspaceContext:
    """워크스페이스와 기본 RAG 인덱스를 함께 조회한다."""

    workspace = resolve_user_primary_workspace(db, user)
    rag_index = db.scalar(
        select(RagIndex).where(
            RagIndex.workspace_idx == workspace.idx,
            RagIndex.name == DEFAULT_RAG_INDEX_NAME,
        )
    )
    return WorkspaceContext(workspace=workspace, rag_index=rag_index)
