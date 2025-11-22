"""노션 페이지 생성 기능."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from notion_client import AsyncClient
from sqlalchemy.orm import Session

from models import NotionOauthCredentials

from .notionAuth import ensure_valid_access_token

_NOTION_VERSION = "2022-06-28"


@dataclass(slots=True)
class NotionPageReference:
    """생성된 노션 페이지의 기본 정보를 담는 자료 구조."""

    page_id: str
    url: str
    title: str


_LINK_PATTERN = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_BOLD_PATTERN = re.compile(r"\*\*(.+?)\*\*")


def _build_rich_text_chunk(text: str, *, bold: bool = False, link: Optional[str] = None) -> Dict[str, Any]:
    """Create a Notion rich text object with optional annotations."""

    chunk: Dict[str, Any] = {"type": "text", "text": {"content": text}}
    if link:
        chunk["text"]["link"] = {"url": link}
    chunk["annotations"] = {
        "bold": bool(bold),
        "italic": False,
        "strikethrough": False,
        "underline": False,
        "code": False,
        "color": "default",
    }
    return chunk


def _parse_bold_segments(text: str, *, link: Optional[str]) -> List[Dict[str, Any]]:
    """Split text into bold and normal segments preserving order."""

    segments: List[Dict[str, Any]] = []
    last_index = 0
    for match in _BOLD_PATTERN.finditer(text):
        start, end = match.span()
        if start > last_index:
            prefix = text[last_index:start]
            if prefix:
                segments.append({"text": prefix, "bold": False, "link": link})
        bold_text = match.group(1)
        if bold_text:
            segments.append({"text": bold_text, "bold": True, "link": link})
        last_index = end
    if last_index < len(text):
        tail = text[last_index:]
        if tail:
            segments.append({"text": tail, "bold": False, "link": link})
    return segments


def _parse_inline_markdown(content: str) -> List[Dict[str, Any]]:
    """Convert simple inline markdown to annotated rich text tokens."""

    tokens: List[Dict[str, Any]] = []
    last_index = 0
    for match in _LINK_PATTERN.finditer(content):
        start, end = match.span()
        if start > last_index:
            prefix = content[last_index:start]
            tokens.extend(_parse_bold_segments(prefix, link=None))
        link_text = match.group(1)
        link_url = match.group(2).strip()
        tokens.extend(_parse_bold_segments(link_text, link=link_url))
        last_index = end
    if last_index < len(content):
        tokens.extend(_parse_bold_segments(content[last_index:], link=None))
    return tokens or [{"text": content, "bold": False, "link": None}]


def _rich_text(
    content: str,
    *,
    chunk_size: int = 1800,
    parse_inline: bool = True,
) -> List[Dict[str, Any]]:
    """긴 문자열을 노션 rich_text 조각으로 분할한다."""

    if not content:
        return [_build_rich_text_chunk("")]

    tokens = (
        _parse_inline_markdown(content)
        if parse_inline
        else [{"text": content, "bold": False, "link": None}]
    )

    segments: List[Dict[str, Any]] = []
    for token in tokens:
        text = token["text"]
        bold = token.get("bold", False)
        link = token.get("link")
        start = 0
        while start < len(text):
            chunk = text[start : start + chunk_size]
            segments.append(
                _build_rich_text_chunk(chunk, bold=bold, link=link)
            )
            start += chunk_size
    return segments or [_build_rich_text_chunk("")]


def _paragraph_block(text: str) -> Dict[str, Any]:
    return {
        "object": "block",
        "type": "paragraph",
        "paragraph": {"rich_text": _rich_text(text)},
    }


def _heading_block(text: str, level: int) -> Dict[str, Any]:
    level = max(1, min(level, 3))
    key = f"heading_{level}"
    return {
        "object": "block",
        "type": key,
        key: {"rich_text": _rich_text(text)},
    }


def _bulleted_block(text: str) -> Dict[str, Any]:
    return {
        "object": "block",
        "type": "bulleted_list_item",
        "bulleted_list_item": {"rich_text": _rich_text(text)},
    }


def _numbered_block(text: str) -> Dict[str, Any]:
    return {
        "object": "block",
        "type": "numbered_list_item",
        "numbered_list_item": {"rich_text": _rich_text(text)},
    }


def _code_block(code: str, language: Optional[str]) -> Dict[str, Any]:
    return {
        "object": "block",
        "type": "code",
        "code": {
            "rich_text": _rich_text(code, chunk_size=1500, parse_inline=False),
            "language": (language or "plain text").lower(),
        },
    }


def _divider_block() -> Dict[str, Any]:
    return {"object": "block", "type": "divider", "divider": {}}


def _split_table_cells(line: str) -> List[str]:
    """테이블 한 줄을 셀 단위로 분할한다."""

    content = line.strip()
    if content.startswith("|"):
        content = content[1:]
    if content.endswith("|"):
        content = content[:-1]
    return [cell.strip() for cell in content.split("|")]


def _table_row_block(cells: List[str], *, width: int) -> Dict[str, Any]:
    """Notion table_row 블록을 생성한다."""

    padded = cells + [""] * (max(0, width - len(cells)))
    return {
        "object": "block",
        "type": "table_row",
        "table_row": {
            "cells": [[*_rich_text(cell)] for cell in padded],
        },
    }


def _table_block(header: List[str], rows: List[List[str]]) -> Dict[str, Any]:
    """Notion table 블록을 생성한다."""

    width = max([len(header), *[len(row) for row in rows]] or [0])
    children = [_table_row_block(header, width=width)]
    for row in rows:
        children.append(_table_row_block(row, width=width))
    return {
        "object": "block",
        "type": "table",
        "table": {
            "table_width": width,
            "has_column_header": True,
            "has_row_header": False,
            "children": children,
        },
    }


def _is_table_divider(line: str) -> bool:
    """마크다운 테이블 구분 라인인지 확인한다."""

    stripped = line.strip()
    return bool(stripped and "|" in stripped and re.fullmatch(r"\|?\s*:?[-]+.*", stripped))


def _markdown_to_blocks(markdown: str) -> List[Dict[str, Any]]:
    """간단한 마크다운을 노션 블록 리스트로 변환한다."""

    lines = markdown.splitlines()
    blocks: List[Dict[str, Any]] = []
    in_code = False
    code_lines: List[str] = []
    code_lang: Optional[str] = None
    index = 0

    while index < len(lines):
        raw_line = lines[index]
        line = raw_line.rstrip()
        if line.strip().startswith("```"):
            fence_lang = line.strip()[3:].strip() or None
            if not in_code:
                in_code = True
                code_lines = []
                code_lang = fence_lang
            else:
                blocks.append(_code_block("\n".join(code_lines), code_lang))
                in_code = False
                code_lines = []
                code_lang = None
            index += 1
            continue

        if in_code:
            code_lines.append(raw_line)
            index += 1
            continue

        stripped = line.strip()
        if not stripped:
            index += 1
            continue

        if (index + 1) < len(lines) and "|" in stripped and _is_table_divider(lines[index + 1]):
            header_cells = _split_table_cells(stripped)
            index += 2
            body_rows: List[List[str]] = []
            while index < len(lines):
                body_line = lines[index]
                if "|" not in body_line:
                    break
                body_rows.append(_split_table_cells(body_line))
                index += 1
            blocks.append(_table_block(header_cells, body_rows))
            continue

        if stripped in {"---", "***", "___"} or set(stripped) == {"-"}:
            blocks.append(_divider_block())
        elif stripped.startswith("# "):
            blocks.append(_heading_block(stripped[2:].strip(), 1))
        elif stripped.startswith("## "):
            blocks.append(_heading_block(stripped[3:].strip(), 2))
        elif stripped.startswith("### "):
            blocks.append(_heading_block(stripped[4:].strip(), 3))
        elif stripped.startswith("- "):
            blocks.append(_bulleted_block(stripped[2:].strip()))
        elif stripped[0].isdigit() and ". " in stripped:
            prefix, _, remainder = stripped.partition(". ")
            if prefix.isdigit():
                blocks.append(_numbered_block(remainder.strip()))
            else:
                blocks.append(_paragraph_block(stripped))
        else:
            blocks.append(_paragraph_block(stripped))

        index += 1

    if in_code:
        blocks.append(_code_block("\n".join(code_lines), code_lang))

    if not blocks:
        blocks.append(_paragraph_block(markdown.strip() or "내용이 없습니다."))

    return blocks


async def create_page_from_markdown(
    db: Session,
    cred: NotionOauthCredentials,
    *,
    title: str,
    markdown: str,
) -> NotionPageReference:
    """마크다운 콘텐츠를 기반으로 노션 페이지를 생성한다."""

    refreshed = await ensure_valid_access_token(db, cred)
    client = AsyncClient(auth=refreshed.access_token, notion_version=_NOTION_VERSION)
    try:
        response = await client.pages.create(
            parent={"type": "workspace", "workspace": True},
            properties={
                "title": {
                    "title": _rich_text(title if title else "제목 없음", chunk_size=400),
                }
            },
            children=_markdown_to_blocks(markdown),
        )
    finally:
        await client.aclose()

    page_id = response.get("id") or ""
    url = response.get("url") or ""
    return NotionPageReference(page_id=page_id, url=url, title=title or "제목 없음")

