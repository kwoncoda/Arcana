"""Utilities for rendering Notion block trees into Markdown."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List

_LIST_TYPES = {"bulleted_list_item", "numbered_list_item", "to_do", "toggle"}


@dataclass(frozen=True)
class RenderedBlock:
    """A single rendered Notion block with structural hints."""

    type: str
    depth: int
    text: str
    trailing_blank: bool


def _sanitize_text_lines(lines: Iterable[str]) -> List[str]:
    """Return a list of valid text lines while preserving order."""

    out: List[str] = []
    for line in lines or []:
        if isinstance(line, str):
            cleaned = line.rstrip("\n")
            if cleaned:
                out.append(cleaned)
    return out


def _indent(depth: int) -> str:
    """Return Markdown indentation for nested list items."""

    return "  " * max(depth, 0)


def collect_rendered_blocks(blocks: List[Dict], depth: int = 0) -> List[RenderedBlock]:
    """Flatten a Notion block tree into rendered block descriptors."""

    rendered: List[RenderedBlock] = []
    for block in blocks or []:
        block_type = str(block.get("type") or "")
        text_lines = _sanitize_text_lines(block.get("text", []))
        children = block.get("children", []) or []

        prefix = _indent(depth) if block_type in _LIST_TYPES else ""
        block_lines: List[str] = []
        for text in text_lines:
            block_lines.append(f"{prefix}{text}" if block_type in _LIST_TYPES else text)

        block_text = "\n".join(block_lines).strip("\n")
        trailing_blank = block_type not in _LIST_TYPES and block_type != "divider"

        if block_type and (block_text or not children):
            rendered.append(
                RenderedBlock(
                    type=block_type,
                    depth=depth,
                    text=block_text,
                    trailing_blank=trailing_blank,
                )
            )

        child_depth = depth + (1 if block_type in _LIST_TYPES else 0)
        if children:
            rendered.extend(collect_rendered_blocks(children, depth=child_depth))

    return rendered


def render_blocks_to_markdown(blocks: List[Dict], depth: int = 0) -> str:
    """Render a Notion block tree (as dictionaries) into Markdown text."""

    rendered_blocks = collect_rendered_blocks(blocks, depth)
    lines: List[str] = []
    previous_blank = False

    for block in rendered_blocks:
        if not block.text:
            continue
        lines.append(block.text)
        previous_blank = False

        if block.trailing_blank and not previous_blank:
            lines.append("")
            previous_blank = True

    return "\n".join(lines).strip()
