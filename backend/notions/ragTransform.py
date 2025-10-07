"""Utilities for transforming Notion pages into RAG-friendly artefacts."""

from __future__ import annotations

import os
from copy import deepcopy
from typing import Any, Dict, Iterable, List, Optional

from langchain_core.documents import Document


DEFAULT_CHUNK_SIZE = 1200
_DEFAULT_CHUNK_OVERLAP_RATIO = 0.1


def _load_chunk_overlap_ratio() -> float:
    """Read the chunk overlap ratio from the environment."""

    raw_ratio = os.getenv("RAG_CHUNK_OVERLAP_RATIO")
    if raw_ratio is None:
        return _DEFAULT_CHUNK_OVERLAP_RATIO
    try:
        ratio = float(raw_ratio)
    except ValueError:
        return _DEFAULT_CHUNK_OVERLAP_RATIO
    return max(0.0, ratio)


DEFAULT_CHUNK_OVERLAP_RATIO = _load_chunk_overlap_ratio()


def _clean_text_lines(lines: Iterable[str]) -> List[str]:
    """Remove blank lines and non-string entries from the incoming iterable."""

    cleaned: List[str] = []
    for line in lines:
        if not isinstance(line, str):
            continue
        stripped = line.strip()
        if stripped:
            cleaned.append(stripped)
    return cleaned


def _gather_block_text(block: Dict[str, Any]) -> List[str]:
    """Recursively collect all text values from a Notion block tree."""

    text_lines = _clean_text_lines(block.get("text", []))
    for child in block.get("children", []):
        text_lines.extend(_gather_block_text(child))
    return text_lines


def _combine_page_text(blocks: Iterable[Dict[str, Any]]) -> List[str]:
    """Flatten the text from all blocks that belong to a page."""

    combined: List[str] = []
    for block in blocks:
        combined.extend(_gather_block_text(block))
    return combined


def _resolve_page_url(page: Dict[str, Any]) -> str:
    """Return the canonical URL for a Notion page."""

    explicit_url = page.get("url")
    if isinstance(explicit_url, str) and explicit_url.strip():
        return explicit_url.strip()

    page_id = str(page.get("page_id", "")).replace("-", "")
    return f"https://www.notion.so/{page_id}"


def _calculate_chunk_overlap(
    chunk_size: int,
    chunk_overlap: Optional[int],
    *,
    ratio: float = DEFAULT_CHUNK_OVERLAP_RATIO,
) -> int:
    """Determine the effective overlap to apply when splitting text."""

    if chunk_overlap is not None:
        return max(0, chunk_overlap)

    estimated = int(chunk_size * ratio)
    if estimated >= chunk_size:
        return max(0, chunk_size - 1)
    return max(0, estimated)


def _chunk_text(text: str, *, chunk_size: int, chunk_overlap: int) -> List[str]:
    """Split text into chunks using the provided size and overlap."""

    if chunk_size <= 0:
        return [text] if text else []

    if chunk_overlap >= chunk_size:
        chunk_overlap = max(0, chunk_size - 1)

    chunks: List[str] = []
    start = 0
    text_length = len(text)

    while start < text_length:
        end = min(start + chunk_size, text_length)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end == text_length:
            break
        start = max(end - chunk_overlap, start + 1)
    return chunks


def build_jsonl_records_from_pages(
    pages: List[Dict[str, Any]],
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: Optional[int] = None,
) -> List[Dict[str, str]]:
    """Convert Notion page payloads into JSONL ready records."""

    records: List[Dict[str, str]] = []
    effective_chunk_overlap = _calculate_chunk_overlap(chunk_size, chunk_overlap)

    for page in pages:
        page_id = str(page.get("page_id"))
        title = str(page.get("title") or "")
        last_edited_time = str(page.get("last_edited_time") or "")
        page_url = _resolve_page_url(page)

        text_lines = _combine_page_text(page.get("blocks", []))
        if not text_lines:
            record = {
                "page_id": page_id,
                "title": title,
                "last_edited_time": last_edited_time,
                "text": "",
                "page_url": page_url,
            }
            records.append(record)
            continue

        full_text = "\n".join(text_lines)
        for chunk in _chunk_text(
            full_text,
            chunk_size=chunk_size,
            chunk_overlap=effective_chunk_overlap,
        ):
            record = {
                "page_id": page_id,
                "title": title,
                "last_edited_time": last_edited_time,
                "text": chunk,
                "page_url": page_url,
            }
            records.append(record)
    return records


def build_documents_from_records(
    records: List[Dict[str, str]],
    workspace_metadata: Dict[str, Any],
) -> List[Document]:
    """Create LangChain documents from JSONL records."""

    documents: List[Document] = []
    for index, record in enumerate(records):
        text = record.get("text", "")
        if not text:
            continue

        metadata = deepcopy(workspace_metadata)
        metadata.update(
            {
                "page_id": record.get("page_id"),
                "page_title": record.get("title"),
                "page_url": record.get("page_url"),
                "last_edited_time": record.get("last_edited_time"),
                "chunk_id": f"{record.get('page_id')}:{index}",
                "chunk_index": index,
            }
        )
        document = Document(page_content=text, metadata=metadata)
        documents.append(document)
    return documents


def build_documents_from_pages(
    pages: List[Dict[str, Any]],
    workspace_metadata: Dict[str, Any],
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: Optional[int] = None,
) -> List[Document]:
    """Shortcut for creating documents directly from Notion page payloads."""

    records = build_jsonl_records_from_pages(
        pages,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    return build_documents_from_records(records, workspace_metadata)
