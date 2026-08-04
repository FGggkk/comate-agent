"""按 Markdown 章节和自然边界切分公司资料。"""

import math
import re
from dataclasses import dataclass


DEFAULT_CHUNK_SIZE = 650
DEFAULT_CHUNK_OVERLAP = 100
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


@dataclass(frozen=True)
class TextChunk:
    chunk_index: int
    section_path: str
    content: str
    token_count: int


def chunk_text(
    text: str,
    *,
    source_format: str,
    max_chars: int = DEFAULT_CHUNK_SIZE,
    overlap_chars: int = DEFAULT_CHUNK_OVERLAP,
) -> list[TextChunk]:
    if max_chars < 120:
        raise ValueError("切分长度不能小于 120 个字符")
    if not 0 <= overlap_chars < max_chars:
        raise ValueError("切分重叠长度必须小于切分长度")

    sections = _markdown_sections(text) if source_format == "md" else [("", text)]
    result: list[TextChunk] = []
    for section_path, section_content in sections:
        for part in _split_content(section_content, max_chars=max_chars, overlap_chars=overlap_chars):
            result.append(
                TextChunk(
                    chunk_index=len(result),
                    section_path=section_path,
                    content=part,
                    token_count=max(1, math.ceil(len(part) / 2)),
                )
            )
    return result


def _markdown_sections(text: str) -> list[tuple[str, str]]:
    headings: list[tuple[int, str]] = []
    sections: list[tuple[str, str]] = []
    buffer: list[str] = []

    def flush() -> None:
        content = "\n".join(buffer).strip()
        if content:
            sections.append((" / ".join(item[1] for item in headings), content))
        buffer.clear()

    for line in text.splitlines():
        match = _HEADING_RE.match(line)
        if not match:
            buffer.append(line)
            continue

        flush()
        level = len(match.group(1))
        title = match.group(2).strip()
        while headings and headings[-1][0] >= level:
            headings.pop()
        headings.append((level, title))

    flush()
    return sections


def _split_content(content: str, *, max_chars: int, overlap_chars: int) -> list[str]:
    normalized = content.strip()
    if not normalized:
        return []
    if len(normalized) <= max_chars:
        return [normalized]

    parts: list[str] = []
    start = 0
    while start < len(normalized):
        tentative_end = min(start + max_chars, len(normalized))
        if tentative_end == len(normalized):
            end = tentative_end
        else:
            end = _find_breakpoint(normalized, start, tentative_end)
        part = normalized[start:end].strip()
        if part:
            parts.append(part)
        if end >= len(normalized):
            break
        start = max(end - overlap_chars, start + 1)
    return parts


def _find_breakpoint(text: str, start: int, tentative_end: int) -> int:
    lower_bound = start + max(1, int((tentative_end - start) * 0.55))
    for marker in ("\n\n", "\n", "。", "！", "？", "；", " "):
        position = text.rfind(marker, lower_bound, tentative_end)
        if position >= lower_bound:
            return position + len(marker)
    return tentative_end
