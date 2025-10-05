"""Utilities for converting Notion pull payloads into JSONL-ready records."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
from typing import Any, Dict, Iterable, List, Optional, Sequence


def _normalize_text(values: Iterable[str]) -> List[str]:
    """Return trimmed text fragments, dropping empties."""

    normalized: List[str] = []
    for value in values:
        if not isinstance(value, str):
            continue
        stripped = value.strip()
        if stripped:
            normalized.append(stripped)
    return normalized


def _block_label(block_type: str) -> str:
    """Readable fallback label for empty blocks."""

    if not block_type:
        return "Block"
    return block_type.replace("_", " ").title()


def _compose_url(page_id: str, base_url: str) -> str:
    """Construct a canonical Notion page URL without requiring the slug."""

    clean_id = page_id.replace("-", "")
    return f"{base_url.rstrip('/')}/{clean_id}"


@dataclass(slots=True)
class BlockRecord:
    """Flattened representation of a Notion block ready for indexing."""

    workspace: str
    page_id: str
    page_title: str
    page_url: str
    block_id: str
    block_type: str
    content: str
    breadcrumbs: List[str]
    last_edited_time: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "workspace": self.workspace,
            "page_id": self.page_id,
            "page_title": self.page_title,
            "page_url": self.page_url,
            "block_id": self.block_id,
            "block_type": self.block_type,
            "content": self.content,
            "breadcrumbs": self.breadcrumbs,
        }
        if self.last_edited_time is not None:
            payload["last_edited_time"] = self.last_edited_time
        return payload


def _summarize_block_text(block: Dict[str, Any]) -> List[str]:
    return _normalize_text(block.get("text", []))


def _collect_descendant_text(block: Dict[str, Any]) -> List[str]:
    lines: List[str] = []
    lines.extend(_summarize_block_text(block))
    for child in block.get("children", []) or []:
        if isinstance(child, dict):
            lines.extend(_collect_descendant_text(child))
    return lines


def _flatten_block(
    block: Dict[str, Any],
    *,
    workspace: str,
    page_id: str,
    page_title: str,
    page_url: str,
    last_edited_time: Optional[str],
    parent_breadcrumbs: Sequence[str],
) -> List[BlockRecord]:
    block_id = str(block.get("id"))
    block_type = str(block.get("type", ""))
    text_fragments = _summarize_block_text(block)

    if text_fragments:
        label = " ".join(text_fragments)
        breadcrumbs = list(parent_breadcrumbs) + [label]
    else:
        breadcrumbs = list(parent_breadcrumbs) + [_block_label(block_type)]

    content_lines = _collect_descendant_text(block)
    content = "\n".join(content_lines)

    record = BlockRecord(
        workspace=workspace,
        page_id=page_id,
        page_title=page_title,
        page_url=page_url,
        block_id=block_id,
        block_type=block_type,
        content=content,
        breadcrumbs=list(parent_breadcrumbs),
        last_edited_time=last_edited_time,
    )

    records: List[BlockRecord] = [record]

    for child in block.get("children", []) or []:
        if not isinstance(child, dict):
            continue
        child_records = _flatten_block(
            child,
            workspace=workspace,
            page_id=page_id,
            page_title=page_title,
            page_url=page_url,
            last_edited_time=last_edited_time,
            parent_breadcrumbs=breadcrumbs,
        )
        records.extend(child_records)

    return records


def build_block_records(
    payload: Dict[str, Any],
    *,
    workspace: str,
    base_url: str = "https://www.notion.so",
) -> List[Dict[str, Any]]:
    """Convert the Notion pull payload into flat JSON-serializable records."""

    pages = payload.get("pages") or []
    records: List[Dict[str, Any]] = []

    for page in pages:
        if not isinstance(page, dict):
            continue
        page_id = str(page.get("page_id") or page.get("id"))
        if not page_id:
            continue
        page_title = str(page.get("title") or "")
        page_url = _compose_url(page_id, base_url)
        last_edited_time = page.get("last_edited_time")
        blocks = page.get("blocks") or []

        for block in blocks:
            if not isinstance(block, dict):
                continue
            block_records = _flatten_block(
                block,
                workspace=workspace,
                page_id=page_id,
                page_title=page_title,
                page_url=page_url,
                last_edited_time=last_edited_time if isinstance(last_edited_time, str) else None,
                parent_breadcrumbs=[page_title] if page_title else [page_id],
            )
            records.extend(record.to_dict() for record in block_records)

    return records


def write_jsonl(records: Iterable[Dict[str, Any]], destination: Path) -> None:
    """Persist the records to a UTF-8 JSONL file."""

    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8") as fp:
        for record in records:
            fp.write(json.dumps(record, ensure_ascii=False))
            fp.write("\n")


def preprocess_to_jsonl(
    payload: Dict[str, Any],
    *,
    workspace: str,
    output_path: Path,
    base_url: str = "https://www.notion.so",
) -> List[Dict[str, Any]]:
    """End-to-end helper that builds records and writes them to disk."""

    records = build_block_records(payload, workspace=workspace, base_url=base_url)
    write_jsonl(records, output_path)
    return records

