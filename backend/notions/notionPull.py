"""Utilities for pulling textual content from Notion pages."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, AsyncIterator, Dict, Iterable, List, Optional

from notion_client import AsyncClient

from models import NotionOauthCredentials
from sqlalchemy.orm import Session

from .notionAuth import ensure_valid_access_token

# Notion API requires an explicit version header for consistent payload shapes.
_NOTION_VERSION = "2022-06-28"

# Block types that should be ignored entirely because they primarily contain
# non-textual payloads (images, files, media, etc.).
_SKIP_BLOCK_TYPES: set[str] = {
    "audio",
    "file",
    "image",
    "pdf",
    "video",
    "unsupported",
}


@dataclass(slots=True)
class TextBlock:
    """Structured representation of a textual Notion block."""

    id: str
    type: str
    text: List[str]
    children: List["TextBlock"]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "text": self.text,
            "children": [child.to_dict() for child in self.children],
        }


def _apply_rich_text_annotations(plain: str, *, annotations: Optional[Dict[str, Any]], href: Optional[str]) -> str:
    """주어진 리치 텍스트 조각을 마크다운 문법으로 감싼다."""

    if not plain:
        return ""

    # 코드 블록은 다른 꾸밈보다 우선 적용한다.
    if annotations and annotations.get("code"):
        content = f"`{plain}`"
    else:
        content = plain
        if annotations:
            if annotations.get("bold"):
                content = f"**{content}**"
            if annotations.get("italic"):
                content = f"*{content}*"
            if annotations.get("strikethrough"):
                content = f"~~{content}~~"
            if annotations.get("underline"):
                # 마크다운에 기본 밑줄 문법이 없어 HTML 태그로 감싼다.
                content = f"<u>{content}</u>"

    if href:
        return f"[{content}]({href})"
    return content


def _render_rich_text(items: Iterable[Dict[str, Any]]) -> tuple[str, str]:
    """리치 텍스트 배열을 마크다운/평문 문자열로 동시에 반환한다."""

    markdown_parts: List[str] = []
    plain_parts: List[str] = []

    for item in items:
        plain = item.get("plain_text")
        if not plain:
            continue
        markdown_parts.append(
            _apply_rich_text_annotations(
                plain,
                annotations=item.get("annotations"),
                href=item.get("href"),
            )
        )
        plain_parts.append(plain)

    return "".join(markdown_parts), "".join(plain_parts)


def _extract_text_payload(block: Dict[str, Any]) -> List[str]:
    block_type = block.get("type", "")
    data = block.get(block_type) or {}

    markdown_fragments: List[str] = []
    plain_fragments: List[str] = []

    if isinstance(data, dict):
        if isinstance(data.get("rich_text"), list):
            markdown, plain = _render_rich_text(data["rich_text"])
            if markdown:
                markdown_fragments.append(markdown)
            if plain:
                plain_fragments.append(plain)
        if isinstance(data.get("title"), list):
            markdown, plain = _render_rich_text(data["title"])
            if markdown:
                markdown_fragments.append(markdown)
            if plain:
                plain_fragments.append(plain)
        if isinstance(data.get("caption"), list):
            markdown, plain = _render_rich_text(data["caption"])
            if markdown:
                markdown_fragments.append(markdown)
            if plain:
                plain_fragments.append(plain)

    markdown_text_raw = "".join(markdown_fragments)
    markdown_text = markdown_text_raw.strip()
    plain_text_raw = "".join(plain_fragments)

    lines: List[str] = []

    if block_type == "heading_1":
        if markdown_text:
            lines.append(f"# {markdown_text}")
    elif block_type == "heading_2":
        if markdown_text:
            lines.append(f"## {markdown_text}")
    elif block_type == "heading_3":
        if markdown_text:
            lines.append(f"### {markdown_text}")
    elif block_type == "bulleted_list_item":
        if markdown_text:
            lines.append(f"- {markdown_text}")
    elif block_type == "numbered_list_item":
        if markdown_text:
            lines.append(f"1. {markdown_text}")
    elif block_type == "to_do":
        checked = False
        if isinstance(data, dict):
            checked = bool(data.get("checked"))
        box = "x" if checked else " "
        content = markdown_text
        if content:
            lines.append(f"- [{box}] {content}")
        else:
            lines.append(f"- [{box}]")
    elif block_type == "quote":
        if markdown_text:
            lines.append(f"> {markdown_text}")
    elif block_type == "callout":
        emoji = ""
        icon = data.get("icon") if isinstance(data, dict) else None
        if isinstance(icon, dict):
            emoji_value = icon.get("emoji")
            if isinstance(emoji_value, str) and emoji_value.strip():
                emoji = f"{emoji_value.strip()} "
        if markdown_text or emoji:
            lines.append(f"> {emoji}{markdown_text}".rstrip())
    elif block_type == "code":
        language = ""
        if isinstance(data, dict):
            language = str(data.get("language") or "").strip()
        fence = f"```{language}" if language else "```"
        lines.append(fence)
        code_body = plain_text_raw.rstrip("\n")
        if code_body:
            lines.extend(code_body.splitlines())
        lines.append("```")
    elif block_type == "equation":
        expression = ""
        if isinstance(data, dict):
            expression = str(data.get("expression") or "").strip()
        if expression:
            lines.append(f"$$ {expression} $$")
    elif block_type == "divider":
        lines.append("---")
    elif block_type == "toggle":
        if markdown_text:
            lines.append(f"- {markdown_text}")
    elif block_type == "child_page":
        title = data.get("title") if isinstance(data, dict) else None
        if isinstance(title, str) and title.strip():
            lines.append(f"## {title.strip()}")
    else:
        if markdown_text:
            lines.append(markdown_text)

    return [line for line in lines if isinstance(line, str) and line]


async def _collect_children(client: AsyncClient, block_id: str) -> List[Dict[str, Any]]:
    """Iterate through children blocks handling pagination."""

    start_cursor: Optional[str] = None
    results: List[Dict[str, Any]] = []

    while True:
        response = await client.blocks.children.list(
            block_id=block_id,
            start_cursor=start_cursor,
            page_size=100,
        )
        batch = response.get("results", [])
        results.extend(batch)
        if not response.get("has_more"):
            break
        start_cursor = response.get("next_cursor")

    return results


async def _build_text_block_tree(client: AsyncClient, block: Dict[str, Any]) -> Optional[TextBlock]:
    block_type = block.get("type", "")
    if block_type in _SKIP_BLOCK_TYPES:
        return None

    texts = _extract_text_payload(block)
    children: List[TextBlock] = []

    if block.get("has_children") and block_type != "child_page":
        child_blocks = await _collect_children(client, block.get("id"))
        for child in child_blocks:
            child_text_block = await _build_text_block_tree(client, child)
            if child_text_block:
                children.append(child_text_block)

    if not texts and not children:
        return None

    return TextBlock(
        id=str(block.get("id")),
        type=block_type,
        text=texts,
        children=children,
    )


async def _fetch_page_blocks(client: AsyncClient, page_id: str) -> List[TextBlock]:
    """Fetch blocks for a page and convert them into `TextBlock` instances."""

    blocks = await _collect_children(client, page_id)
    results: List[TextBlock] = []
    for block in blocks:
        text_block = await _build_text_block_tree(client, block)
        if text_block:
            results.append(text_block)
    return results


async def pull_page_text(
    db: Session,
    cred: NotionOauthCredentials,
    page_id: str,
) -> Dict[str, Any]:
    """Return textual content for the given Notion page.

    The credential is refreshed if necessary and the resulting payload contains
    blocks with textual data only (media blocks are skipped).
    """

    refreshed = await ensure_valid_access_token(db, cred)

    async with AsyncClient(auth=refreshed.access_token, notion_version=_NOTION_VERSION) as client:
        blocks = await _fetch_page_blocks(client, page_id)

    return {
        "page_id": page_id,
        "blocks": [block.to_dict() for block in blocks],
    }


async def _iter_shared_pages(client: AsyncClient) -> AsyncIterator[Dict[str, Any]]:
    """Yield every Notion page shared with the integration."""

    start_cursor: Optional[str] = None

    while True:
        response = await client.search(
            filter={"property": "object", "value": "page"},
            sort={"direction": "descending", "timestamp": "last_edited_time"},
            start_cursor=start_cursor,
            page_size=100,
        )
        for item in response.get("results", []):
            if item.get("object") == "page":
                yield item

        if not response.get("has_more"):
            break

        start_cursor = response.get("next_cursor")


def _extract_page_title(page: Dict[str, Any]) -> str:
    """Return a best-effort page title from the search payload."""

    # Root pages expose title within the `properties` payload.
    properties = page.get("properties")
    if isinstance(properties, dict):
        title_prop = properties.get("title")
        if isinstance(title_prop, dict):
            title = _flatten_rich_text(title_prop.get("title", []))
            if title:
                return " ".join(title)

    # As a fallback, check the top-level `title` key (databases use this shape).
    title_items = page.get("title")
    if isinstance(title_items, list):
        title = _flatten_rich_text(title_items)
        if title:
            return " ".join(title)

    # Finally, rely on the page ID.
    return str(page.get("id", ""))


async def pull_all_shared_page_text(
    db: Session,
    cred: NotionOauthCredentials,
) -> Dict[str, Any]:
    """Return textual content for every page shared with the integration."""

    refreshed = await ensure_valid_access_token(db, cred)

    async with AsyncClient(auth=refreshed.access_token, notion_version=_NOTION_VERSION) as client:
        pages: List[Dict[str, Any]] = []

        async for page in _iter_shared_pages(client):
            page_id = str(page.get("id"))
            blocks = await _fetch_page_blocks(client, page_id)
            pages.append(
                {
                    "page_id": page_id,
                    "title": _extract_page_title(page),
                    "last_edited_time": page.get("last_edited_time"),
                    "url": page.get("url"),  # 페이지 URL을 포함하여 후속 단계에서 근거 링크로 활용하는 주석
                    "blocks": [block.to_dict() for block in blocks],
                }
            )

    return {
        "pages": pages,
        "count": len(pages),
    }

