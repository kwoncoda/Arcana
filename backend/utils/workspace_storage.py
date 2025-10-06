"""Utility helpers for managing workspace-specific storage directories."""

from __future__ import annotations

import re
from pathlib import Path

__all__ = [
    "slugify_workspace_name",
    "workspace_storage_path",
    "ensure_workspace_storage",
]

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_STORAGE_ROOT = (_BACKEND_ROOT / "storage" / "workspace").resolve()

_SLUG_INVALID_CHARS = re.compile(r"[^a-z0-9._-]+")
_MULTIPLE_SEPARATORS = re.compile(r"-+")


def slugify_workspace_name(name: str) -> str:
    """Return a filesystem-friendly slug derived from the workspace name."""

    normalized = name.strip().lower()
    if not normalized:
        return "workspace"

    sanitized = _SLUG_INVALID_CHARS.sub("-", normalized)
    collapsed = _MULTIPLE_SEPARATORS.sub("-", sanitized)
    slug = collapsed.strip("-._")
    return slug or "workspace"


def workspace_storage_path(workspace_name: str) -> Path:
    """Return the target storage directory for the given workspace."""

    slug = slugify_workspace_name(workspace_name)
    return _DEFAULT_STORAGE_ROOT / slug


def ensure_workspace_storage(workspace_name: str) -> Path:
    """Create and return the workspace storage directory if it does not exist."""

    path = workspace_storage_path(workspace_name)
    path.mkdir(parents=True, exist_ok=True)
    return path
