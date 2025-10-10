"""노션 페이지 생성 기능."""
from __future__ import annotations

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


def _rich_text(content: str, *, chunk_size: int = 1800) -> List[Dict[str, Any]]:
    """긴 문자열을 노션 rich_text 조각으로 분할한다."""

    segments: List[Dict[str, Any]] = []
    if not content:
        return [{"type": "text", "text": {"content": ""}}]

    start = 0
    length = len(content)
    while start < length:
        chunk = content[start : start + chunk_size]
        segments.append({"type": "text", "text": {"content": chunk}})
        start += chunk_size
    return segments


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
            "rich_text": _rich_text(code, chunk_size=1500),
            "language": (language or "plain text").lower(),
        },
    }


def _markdown_to_blocks(markdown: str) -> List[Dict[str, Any]]:
    """간단한 마크다운을 노션 블록 리스트로 변환한다."""

    lines = markdown.splitlines()
    blocks: List[Dict[str, Any]] = []
    in_code = False
    code_lines: List[str] = []
    code_lang: Optional[str] = None

    for raw_line in lines:
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
            continue

        if in_code:
            code_lines.append(raw_line)
            continue

        stripped = line.strip()
        if not stripped:
            continue

        if stripped.startswith("# "):
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

