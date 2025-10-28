"""노션 페이지를 RAG로 변환하기 위한 유틸리티"""

from __future__ import annotations

import os
import re
import json
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

import tiktoken
from langchain_core.documents import Document

from .renderer import RenderedBlock, collect_rendered_blocks

DEFAULT_CHUNK_SIZE = 800
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


def _get_token_encoder() -> tiktoken.Encoding:
    """Return a cached token encoder for counting tokens."""

    return tiktoken.get_encoding("cl100k_base")


_ENC = _get_token_encoder()

def count_tokens(text: str) -> int:
    """Return the number of tokens for the given string."""

    if not text:
        return 0
    return len(_ENC.encode(text))


_BLOCK_TYPE_MARKERS: Dict[str, str] = {
    "heading_1": "H1",
    "heading_2": "H2",
    "heading_3": "H3",
    "paragraph": "P",
    "bulleted_list_item": "BULLET",
    "numbered_list_item": "NUMBERED",
    "to_do": "TODO",
    "toggle": "TOGGLE",
    "divider": "DIV",
    "quote": "QUOTE",
    "code": "CODE",
    "callout": "CALLOUT",
    "child_page": "CHILD_PAGE",
    "child_database": "CHILD_DB",
    "synced_block": "SYNC",
    "table": "TABLE",
    "table_row": "ROW",
    "column_list": "COLUMN_LIST",
    "column": "COLUMN",
    "equation": "EQUATION",
    "bookmark": "BOOKMARK",
    "image": "IMAGE",
    "video": "VIDEO",
    "pdf": "PDF",
    "file": "FILE",
    "audio": "AUDIO",
    "embed": "EMBED",
    "link_preview": "LINK_PREVIEW",
    "table_of_contents": "TOC",
    "breadcrumb": "BREADCRUMB",
}


def _marker_for_type(block_type: str) -> str:
    """Map a Notion block type to a stable marker token."""

    if not block_type:
        return "BLOCK"

    base = _BLOCK_TYPE_MARKERS.get(block_type)
    if base:
        return base

    sanitized = re.sub(r"[^A-Za-z0-9]+", "_", block_type).strip("_")
    return sanitized.upper() or "BLOCK"


@dataclass(frozen=True)
class AnnotatedSegment:
    """A rendered Markdown block annotated with structural metadata."""

    type: str
    depth: int
    marker: str
    body: str
    separator: str
    token_length: int


def _build_annotated_segments(blocks: Sequence[RenderedBlock]) -> List[AnnotatedSegment]:
    """Convert rendered blocks into annotated Markdown segments."""

    segments: List[AnnotatedSegment] = []
    total = len(blocks)

    for index, block in enumerate(blocks):
        if not block.text:
            continue

        marker = _marker_for_type(block.type)
        if "\n" in block.text:
            body = f"[[{marker}]]\n{block.text}\n[[/{marker}]]"
        else:
            body = f"[[{marker}]] {block.text} [[/{marker}]]"

        if index == total - 1:
            separator = ""
        elif block.trailing_blank:
            separator = "\n\n"
        else:
            separator = "\n"

        token_length = count_tokens(body + separator)
        segments.append(
            AnnotatedSegment(
                type=block.type,
                depth=block.depth,
                marker=marker,
                body=body,
                separator=separator,
                token_length=token_length,
            )
        )

    return segments


def _chunk_segments(
    segments: Sequence[AnnotatedSegment],
    *,
    max_tokens: int,
    overlap: int,
) -> List[List[AnnotatedSegment]]:
    """Split annotated segments into token-aware chunks."""

    if not segments:
        return []

    if max_tokens <= 0:
        return [list(segments)]

    chunks: List[List[AnnotatedSegment]] = []
    current: List[AnnotatedSegment] = []
    current_tokens = 0

    for segment in segments:
        if current and current_tokens + segment.token_length > max_tokens:
            chunks.append(current)

            if overlap > 0:
                retained: List[AnnotatedSegment] = []
                retained_tokens = 0
                for previous in reversed(current):
                    if retained_tokens + previous.token_length > overlap:
                        break
                    retained.insert(0, previous)
                    retained_tokens += previous.token_length
                current = retained
                current_tokens = retained_tokens
            else:
                current = []
                current_tokens = 0

        current.append(segment)
        current_tokens += segment.token_length

    if current:
        chunks.append(current)

    return chunks


def _build_chunk_payload(
    segments: Sequence[AnnotatedSegment],
) -> Dict[str, Any]:
    """Assemble text and structural metadata for a chunk."""

    if not segments:
        return {"text": "", "block_types": [], "block_starts": []}

    parts: List[str] = []
    block_types: List[str] = []
    block_starts: List[int] = []
    offset = 0

    for segment in segments:
        block_types.append(f"{segment.marker}:{segment.type}:{segment.depth}")
        block_starts.append(offset)

        parts.append(segment.body)
        offset += len(segment.body)

        if segment.separator:
            parts.append(segment.separator)
            offset += len(segment.separator)

    text = "".join(parts).rstrip()

    return {
        "text": text,
        "block_types": block_types,
        "block_starts": block_starts,
    }


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


def build_jsonl_records_from_pages(
    pages: List[Dict[str, Any]],
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Convert Notion page payloads into JSONL ready records."""

    records: List[Dict[str, Any]] = []
    effective_overlap = _calculate_chunk_overlap(chunk_size, chunk_overlap)

    for page in pages:
        page_id = str(page.get("page_id"))
        title = str(page.get("title") or "")
        last_edited_time = str(page.get("last_edited_time") or "")
        page_url = str(page.get("url") or "")
        blocks = page.get("blocks", []) or []

        rendered_blocks = collect_rendered_blocks(blocks)
        annotated_segments = _build_annotated_segments(rendered_blocks)

        if not annotated_segments:
            records.append(
                {
                    "page_id": page_id,
                    "title": title,
                    "last_edited_time": last_edited_time,
                    "page_url": page_url,
                    "text": "",
                    "format": "markdown",
                    "block_types": [],
                    "block_starts": [],
                }
            )
            continue

        segment_chunks = _chunk_segments(
            annotated_segments,
            max_tokens=chunk_size,
            overlap=effective_overlap,
        )

        for chunk_segments in segment_chunks:
            payload = _build_chunk_payload(chunk_segments)
            records.append(
                {
                    "page_id": page_id,
                    "title": title,
                    "last_edited_time": last_edited_time,
                    "page_url": page_url,
                    "text": payload["text"],
                    "format": "markdown",
                    "block_types": payload["block_types"],
                    "block_starts": payload["block_starts"],
                }
            )

    return records


def build_documents_from_records(
    records: List[Dict[str, Any]],
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
                "format": record.get("format", "markdown"),
                "block_types": json.dumps(record.get("block_types") or []),
                "block_starts": json.dumps(record.get("block_starts") or []),
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
