"""A2 LLM 语义边界裁决：对规则/语义切分的候选块做 keep / merge_with_next / split 建议。

- 输入按批送 LLM，每块只送 section_path + 首/尾片段，控制 token 成本。
- 动作：keep（保留）、merge_with_next（与下一块合并）、split（在 split_at 处按句子边界拆分）。
- LLM 失败、输出非法或决策无效时：保留原块并记录 warning，不阻塞切分流程。
"""

import json
import math

from app.plugins.company_knowledge.chunker import TextChunk, _find_breakpoint
from app.plugins.company_knowledge.prompts import (
    CHUNK_REFINE_SYSTEM_PROMPT,
    CONTEXTUALIZE_SYSTEM_PROMPT,
    build_chunk_refine_prompt,
    build_contextualize_prompt,
)
from app.services.model_gateway import gateway

MAX_HEAD_CHARS = 200
MAX_TAIL_CHARS = 100
# 合并建议的保守上限：超过 target_len * 1.2 的合并会被忽略，避免块过大
MERGE_OVERFLOW_RATIO = 1.2
# 上下文描述的最大长度，防止元数据膨胀
MAX_CONTEXT_DESCRIPTION_CHARS = 300


def _chunk_snapshot(chunk: TextChunk, index: int) -> dict:
    content = chunk.content
    return {
        "index": index,
        "section_path": chunk.section_path,
        "char_count": len(content),
        "head": content[:MAX_HEAD_CHARS],
        "tail": content[-MAX_TAIL_CHARS:] if len(content) > MAX_HEAD_CHARS else "",
    }


def _make_chunk(index: int, section_path: str, content: str) -> TextChunk:
    return TextChunk(
        chunk_index=index,
        section_path=section_path,
        content=content,
        token_count=max(1, math.ceil(len(content) / 2)),
    )


async def llm_refine_chunks(
    chunks: list[TextChunk],
    *,
    source_title: str,
    target_len: int = 500,
) -> tuple[list[TextChunk], list[str]]:
    """对候选块做 LLM 边界裁决，返回 (新块列表, 警告列表)。

    裁决不可用时原样返回 chunks（警告说明原因），调用方照常使用规则结果。
    """
    warnings: list[str] = []
    if not chunks:
        return [], warnings

    try:
        prompt = build_chunk_refine_prompt(
            source_title,
            [_chunk_snapshot(chunk, index) for index, chunk in enumerate(chunks)],
            target_len,
        )
        raw = await gateway.chat(prompt, system=CHUNK_REFINE_SYSTEM_PROMPT)
        decisions = _parse_decisions(raw, chunk_count=len(chunks))
    except Exception as exc:
        warnings.append(f"LLM 语义裁决不可用，已保留自动切分结果（{exc}）")
        return chunks, warnings

    if not decisions:
        warnings.append("LLM 语义裁决未返回有效决策，已保留自动切分结果")
        return chunks, warnings

    refined, apply_warnings = _apply_decisions(chunks, decisions, target_len=target_len)
    warnings.extend(apply_warnings)
    return refined, warnings


def _parse_decisions(raw: str, *, chunk_count: int) -> list[dict]:
    """宽松解析 LLM 返回的 JSON 数组，过滤非法条目。"""
    content = (raw or "").strip()
    if content.startswith("```"):
        content = content.split("\n", 1)[1] if "\n" in content else ""
        if content.rstrip().endswith("```"):
            content = content.rstrip()[:-3]
    start, end = content.find("["), content.rfind("]")
    if start < 0 or end <= start:
        raise ValueError("未找到 JSON 数组")
    payload = json.loads(content[start : end + 1])
    if not isinstance(payload, list):
        raise ValueError("响应不是 JSON 数组")

    decisions = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        index = item.get("chunk_index")
        action = item.get("action")
        if not isinstance(index, int) or action not in {"keep", "merge_with_next", "split"}:
            continue
        if not 0 <= index < chunk_count:
            continue
        split_at = item.get("split_at")
        decisions.append(
            {
                "chunk_index": index,
                "action": action,
                "split_at": int(split_at) if isinstance(split_at, (int, float)) and split_at > 0 else None,
                "reason": str(item.get("reason") or ""),
            }
        )
    return decisions


def _apply_decisions(
    chunks: list[TextChunk],
    decisions: list[dict],
    *,
    target_len: int,
) -> tuple[list[TextChunk], list[str]]:
    by_index = {d["chunk_index"]: d for d in decisions}
    result: list[TextChunk] = []
    warnings: list[str] = []
    count = len(chunks)
    index = 0

    while index < count:
        decision = by_index.get(index, {})
        action = decision.get("action")

        if action == "merge_with_next" and index + 1 < count:
            content = chunks[index].content
            cursor = index + 1
            # 链式合并：只要刚并入的块也要求 merge_with_next，就继续并入下一块
            while cursor < count and by_index.get(cursor - 1, {}).get("action") == "merge_with_next":
                content = f"{content}\n\n{chunks[cursor].content}"
                cursor += 1
            if len(content) <= int(target_len * MERGE_OVERFLOW_RATIO):
                result.append(_make_chunk(len(result), chunks[index].section_path, content))
                index = cursor
                continue
            warnings.append(f"分片 {index} 的合并建议因超长被忽略（{len(content)} 字符）")
            result.append(chunks[index])
            index += 1
            continue

        if action == "split" and decision.get("split_at"):
            content = chunks[index].content
            position = _find_breakpoint(content, 0, min(decision["split_at"], len(content)))
            left, right = content[:position].strip(), content[position:].strip()
            if left and right:
                result.append(_make_chunk(len(result), chunks[index].section_path, left))
                result.append(_make_chunk(len(result), chunks[index].section_path, right))
                index += 1
                continue
            warnings.append(f"分片 {index} 的拆分点无效，已保留原样")

        result.append(chunks[index])
        index += 1

    return result, warnings


async def generate_contextual_descriptions(
    chunks: list[TextChunk],
    *,
    source_title: str,
) -> list[str]:
    """逐块生成上下文描述（A3 Contextual Retrieval）。

    返回与 chunks 等长的描述列表；单块生成失败返回空字符串（调用方跳过该块），
    不因个别失败中断整体流程。
    """
    descriptions: list[str] = []
    for index, chunk in enumerate(chunks):
        prev_tail = chunks[index - 1].content[-MAX_TAIL_CHARS:] if index > 0 else ""
        next_head = chunks[index + 1].content[:MAX_HEAD_CHARS] if index + 1 < len(chunks) else ""
        try:
            prompt = build_contextualize_prompt(
                source_title,
                chunk.section_path,
                prev_tail,
                chunk.content,
                next_head,
            )
            text = (await gateway.chat(prompt, system=CONTEXTUALIZE_SYSTEM_PROMPT)).strip()
            descriptions.append(text[:MAX_CONTEXT_DESCRIPTION_CHARS])
        except Exception:
            descriptions.append("")
    return descriptions
