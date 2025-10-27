"""노션 페이지를 RAG로 변환하기 위한 유틸리티"""

from __future__ import annotations

import os
import re
from copy import deepcopy
from typing import Any, Dict, Iterable, List, Optional

import tiktoken
from langchain_core.documents import Document

from .renderer import render_blocks_to_markdown

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

_SECTION_SPLIT_RE = re.compile(r"^(#{1,6}\s)|^(---)$", re.MULTILINE)


def count_tokens(text: str) -> int:
    """Return the number of tokens for the given string."""

    if not text:
        return 0
    return len(_ENC.encode(text))


def split_markdown_sections(markdown: str) -> List[str]:
    """Split markdown text into sections around headings and dividers."""

    if not markdown:
        return []

    parts: List[str] = []
    last_index = 0
    for match in _SECTION_SPLIT_RE.finditer(markdown):
        start = match.start()
        if start > last_index:
            parts.append(markdown[last_index:start].strip())
        last_index = start
    if last_index < len(markdown):
        parts.append(markdown[last_index:].strip())

    return [section for section in parts if section]


def _update_fence_state(text: str, fence_open: bool) -> bool:
    """Track fenced code block boundaries while scanning text."""

    for line in text.splitlines():
        if line.strip().startswith("```"):
            fence_open = not fence_open
    return fence_open


def _compute_fence_state(paragraphs: Iterable[str]) -> bool:
    """Recompute code fence state for a list of paragraphs."""

    fence_open = False
    for paragraph in paragraphs:
        fence_open = _update_fence_state(paragraph, fence_open)
    return fence_open


def iter_markdown_chunks(
    markdown: str,
    *,
    max_tokens: int = DEFAULT_CHUNK_SIZE,
    overlap: int = 80,
) -> Iterable[str]:
    """Yield markdown-friendly chunks respecting section boundaries."""

    if not markdown:
        return []

    sections = split_markdown_sections(markdown)
    chunks: List[str] = []

    for section in sections:
        paragraphs = [
            part.strip("\n")
            for part in re.split(r"\n\s*\n", section.strip())
            if part.strip()
        ]
        if not paragraphs:
            continue

        current: List[str] = []
        current_tokens = 0
        fence_open = False
        index = 0

        while index < len(paragraphs):
            paragraph = paragraphs[index]
            paragraph_tokens = count_tokens(paragraph)

            if (
                current
                and not fence_open
                and current_tokens + paragraph_tokens > max_tokens
            ):
                chunk = "\n\n".join(current).strip()
                if chunk:
                    chunks.append(chunk)
                if overlap > 0:
                    retained: List[str] = []
                    retained_tokens = 0
                    for previous in reversed(current):
                        tokens = count_tokens(previous)
                        if retained_tokens + tokens > overlap:
                            break
                        retained.append(previous)
                        retained_tokens += tokens
                    retained.reverse()
                    current = retained
                    current_tokens = sum(count_tokens(item) for item in current)
                else:
                    current = []
                    current_tokens = 0
                fence_open = _compute_fence_state(current)
                continue

            current.append(paragraph)
            current_tokens += paragraph_tokens
            fence_open = _update_fence_state(paragraph, fence_open)
            index += 1

        if current:
            chunk = "\n\n".join(current).strip()
            if chunk:
                chunks.append(chunk)

    return chunks


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

        markdown = render_blocks_to_markdown(page.get("blocks", []))
        if not markdown:
            records.append(
                {
                    "page_id": page_id,
                    "title": title,
                    "last_edited_time": last_edited_time,
                    "page_url": page_url,
                    "text": "",
                    "format": "markdown",
                }
            )
            continue

        for chunk in iter_markdown_chunks(
            markdown,
            max_tokens=chunk_size,
            overlap=effective_overlap,
        ):
            records.append(
                {
                    "page_id": page_id,
                    "title": title,
                    "last_edited_time": last_edited_time,
                    "page_url": page_url,
                    "text": chunk,
                    "format": "markdown",
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
