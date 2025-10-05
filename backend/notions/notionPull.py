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


def _flatten_rich_text(items: Iterable[Dict[str, Any]]) -> List[str]:
    texts: List[str] = []
    for item in items:
        plain = item.get("plain_text")
        if plain:
            stripped = plain.strip()
            if stripped:
                texts.append(stripped)
    return texts


def _extract_text_payload(block: Dict[str, Any]) -> List[str]:
    block_type = block.get("type", "")
    data = block.get(block_type) or {}
    texts: List[str] = []

    if isinstance(data, dict):
        if isinstance(data.get("rich_text"), list):
            texts.extend(_flatten_rich_text(data["rich_text"]))
        if isinstance(data.get("title"), list):
            texts.extend(_flatten_rich_text(data["title"]))
        if isinstance(data.get("caption"), list):
            texts.extend(_flatten_rich_text(data["caption"]))
        if block_type == "equation":
            expression = data.get("expression")
            if isinstance(expression, str) and expression.strip():
                texts.append(expression.strip())
        if block_type == "to_do":
            # Completed state also provides context.
            checked = data.get("checked")
            if isinstance(checked, bool):
                texts.append("[x]" if checked else "[ ]")

    if block_type == "child_page":
        title = data.get("title")
        if isinstance(title, str) and title.strip():
            texts.append(title.strip())

    return [t for t in texts if t]


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

    if block.get("has_children"):
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
                    "blocks": [block.to_dict() for block in blocks],
                }
            )

    return {
        "pages": pages,
        "count": len(pages),
    }

