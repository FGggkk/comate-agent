"""按 Markdown 章节、段落与句子边界切分公司资料（语义优先 + 长度兜底）。

切分策略（对齐迭代文档"混合切分"）：
1. 章节边界：Markdown 标题（最强的语义结构边界）
2. 段落边界：空行分隔的段落是原子单元，段落不跨块
3. 句子边界：长段落内按句号/问号/感叹号/分号断句，避免句中截断
4. 长度兜底：极长句子仍超目标长度时按断点硬切（罕见）

目标长度默认 500 字符、重叠 20%（迭代文档建议 200-500 字、重叠 10%-20%）。
"""

import math
import re
from dataclasses import dataclass

from app.services.embedding_service import get_embeddings_batch

DEFAULT_CHUNK_SIZE = 500
DEFAULT_CHUNK_OVERLAP_RATIO = 0.2
# 语义突变检测：相邻段落相似度低于该阈值视为语义边界（自动模式增强）
DEFAULT_MIN_SIMILARITY = 0.75
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_SENTENCE_END_RE = re.compile(r"[。！？!?；;]")
_OVERLAP_MARKERS = ("\n", "。", "！", "？", "；", " ")


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
    overlap_chars: int | None = None,
) -> list[TextChunk]:
    if max_chars < 120:
        raise ValueError("切分长度不能小于 120 个字符")
    if overlap_chars is None:
        overlap_chars = max(1, int(max_chars * DEFAULT_CHUNK_OVERLAP_RATIO))
    if not 0 <= overlap_chars < max_chars:
        raise ValueError("切分重叠长度必须小于切分长度")

    sections = _markdown_sections(text) if source_format == "md" else [("", text)]
    result: list[TextChunk] = []
    for section_path, section_content in sections:
        for part in _split_paragraphs(section_content, max_chars=max_chars, overlap_chars=overlap_chars):
            result.append(
                TextChunk(
                    chunk_index=len(result),
                    section_path=section_path,
                    content=part,
                    token_count=max(1, math.ceil(len(part) / 2)),
                )
            )
    return result


async def chunk_text_semantic(
    text: str,
    *,
    source_format: str = "md",
    max_chars: int = DEFAULT_CHUNK_SIZE,
    min_similarity: float = DEFAULT_MIN_SIMILARITY,
) -> list[TextChunk]:
    """语义突变检测切分：在章节/段落结构之上，用相邻段落 embedding 相似度找语义边界。

    - 段落仍是原子单元（不跨块），复用章节边界与句子边界。
    - 相邻段落相似度低于 min_similarity 视为语义突变，突变处封块（新块从突变段开始）。
    - 累积块超过 max_chars 也会封块；超过 max_chars 的长段落仍按句子边界切分。
    - embedding 失败/未配置（get_embeddings_batch 返回 None/数量不符）时回退规则切分 chunk_text。
    """
    if max_chars < 120:
        raise ValueError("切分长度不能小于 120 个字符")

    sections = _markdown_sections(text) if source_format == "md" else [("", text)]
    result: list[TextChunk] = []
    for section_path, section_content in sections:
        for part in await _semantic_split_paragraphs(
            section_content, max_chars=max_chars, min_similarity=min_similarity
        ):
            result.append(
                TextChunk(
                    chunk_index=len(result),
                    section_path=section_path,
                    content=part,
                    token_count=max(1, math.ceil(len(part) / 2)),
                )
            )
    return result


async def _semantic_split_paragraphs(
    content: str, *, max_chars: int, min_similarity: float
) -> list[str]:
    normalized = content.strip()
    if not normalized:
        return []
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", normalized) if p.strip()]
    if not paragraphs:
        return []

    embeddings = await get_embeddings_batch(paragraphs)
    if embeddings is None or len(embeddings) != len(paragraphs):
        # embedding 不可用：回退规则切分（段落聚合 + 句子/硬切）
        return _split_paragraphs(
            content, max_chars=max_chars, overlap_chars=max(1, int(max_chars * DEFAULT_CHUNK_OVERLAP_RATIO))
        )

    overlap_chars = max(1, int(max_chars * DEFAULT_CHUNK_OVERLAP_RATIO))
    result: list[str] = []
    buffer: list[str] = []
    buffer_len = 0

    def flush_buffer() -> None:
        nonlocal buffer, buffer_len
        if buffer:
            text = "\n\n".join(buffer).strip()
            if text:
                result.append(text)
            buffer = []
            buffer_len = 0

    for index, paragraph in enumerate(paragraphs):
        if len(paragraph) > max_chars:
            # 长段落：先落空缓冲，再按句子边界独立切分（带重叠），并重置相似度基线
            flush_buffer()
            result.extend(_split_sentences(paragraph, max_chars=max_chars, overlap_chars=overlap_chars))
            continue

        # 语义突变：与上一段相似度过低，封块（仅当当前块非空）
        if buffer and index > 0:
            similarity = _cosine_similarity(embeddings[index - 1], embeddings[index])
            if similarity < min_similarity:
                flush_buffer()

        if buffer_len + len(paragraph) + 2 > max_chars:
            flush_buffer()

        buffer.append(paragraph)
        buffer_len += len(paragraph) + 2

    flush_buffer()
    return result


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """余弦相似度；任一向量为零向量时返回 0。"""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)



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


def _split_paragraphs(content: str, *, max_chars: int, overlap_chars: int) -> list[str]:
    """按段落聚合切分：段落为原子单元，聚合到目标长度；长段落内按句子切。

    重叠说明：段落聚合路径为保证段落完整性不做跨块重叠（同一段不会被重复切进两个块）；
    重叠仅用于长段落/极长句子的句子边界切分与硬切路径。
    """
    normalized = content.strip()
    if not normalized:
        return []

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", normalized) if p.strip()]
    if not paragraphs:
        return []

    result: list[str] = []
    buffer: list[str] = []
    buffer_len = 0

    def flush_buffer() -> None:
        nonlocal buffer, buffer_len
        if buffer:
            text = "\n\n".join(buffer).strip()
            if text:
                result.append(text)
            buffer = []
            buffer_len = 0

    for paragraph in paragraphs:
        if len(paragraph) > max_chars:
            # 长段落：先落空缓冲，再按句子边界独立切分（带重叠）
            flush_buffer()
            result.extend(
                _split_sentences(paragraph, max_chars=max_chars, overlap_chars=overlap_chars)
            )
            continue

        if buffer_len + len(paragraph) + 2 <= max_chars:
            buffer.append(paragraph)
            buffer_len += len(paragraph) + 2
        else:
            flush_buffer()
            buffer.append(paragraph)
            buffer_len = len(paragraph) + 2

    flush_buffer()
    return result


def _split_sentences(paragraph: str, *, max_chars: int, overlap_chars: int) -> list[str]:
    """长段落内按句子边界切分，保证句子不跨块；超长句子再按断点硬切。"""
    sentences = _break_sentences(paragraph)
    if not sentences:
        return []

    result: list[str] = []
    buffer: list[str] = []
    buffer_len = 0

    def flush_buffer() -> None:
        nonlocal buffer, buffer_len
        if buffer:
            text = "".join(buffer).strip()
            if text:
                result.append(text)
            buffer = []
            buffer_len = 0

    for sentence in sentences:
        if len(sentence) > max_chars:
            # 极长句子：按断点硬切，保留重叠
            flush_buffer()
            result.extend(_hard_split(sentence, max_chars=max_chars, overlap_chars=overlap_chars))
            continue

        if buffer_len + len(sentence) <= max_chars:
            buffer.append(sentence)
            buffer_len += len(sentence)
        else:
            flush_buffer()
            buffer.append(sentence)
            buffer_len = len(sentence)

    flush_buffer()
    return result


def _break_sentences(paragraph: str) -> list[str]:
    """按句号/问号/感叹号/分号把段落切成句子（保留标点与句间空格）。"""
    parts: list[str] = []
    start = 0
    for match in _SENTENCE_END_RE.finditer(paragraph):
        end = match.end()
        parts.append(paragraph[start:end])
        start = end
    tail = paragraph[start:]
    if tail.strip():
        parts.append(tail)
    # 保留句子间的原始空白，避免 "Hello. World." 被拼成 "Hello.World."
    return [part for part in parts if part.strip()]


def _hard_split(text: str, *, max_chars: int, overlap_chars: int) -> list[str]:
    """长度兜底：对单个超长句子按断点硬切，支持重叠。"""
    normalized = text.strip()
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
    for marker in _OVERLAP_MARKERS:
        position = text.rfind(marker, lower_bound, tentative_end)
        if position >= lower_bound:
            return position + len(marker)
    return tentative_end
