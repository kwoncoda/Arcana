"""Utilities for rendering Notion block trees into Markdown."""

from __future__ import annotations

from typing import Dict, Iterable, List

_LIST_TYPES = {"bulleted_list_item", "numbered_list_item", "to_do", "toggle"}


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


def render_blocks_to_markdown(blocks: List[Dict], depth: int = 0) -> str:
    """Render a Notion block tree (as dictionaries) into Markdown text."""

    lines: List[str] = []

    for block in blocks or []:
        block_type = block.get("type", "")
        text_lines = _sanitize_text_lines(block.get("text", []))
        children = block.get("children", []) or []

        prefix = _indent(depth) if block_type in _LIST_TYPES else ""

        for text in text_lines:
            if block_type in _LIST_TYPES:
                lines.append(f"{prefix}{text}")
            else:
                lines.append(text)

        if children:
            child_markdown = render_blocks_to_markdown(
                children,
                depth + (1 if block_type in _LIST_TYPES else 0),
            )
            if child_markdown:
                lines.append(child_markdown)

        if block_type not in _LIST_TYPES and block_type != "divider":
            lines.append("")

    output: List[str] = []
    previous_blank = False
    for line in lines:
        if not line.strip():
            if not previous_blank:
                output.append("")
                previous_blank = True
        else:
            output.append(line)
            previous_blank = False

    return "\n".join(output).strip()
