"""B2 LLM 关系抽取：从已发布资料抽取显式文档关系，结果进草稿态。

- 只抽取 cite / supersede / parent / related 四类显式关系，要求附证据原文。
- 目标文档通过标题匹配到已有已发布资料；匹配不到进 unmatched，由管理端人工指认。
- LLM 失败/输出非法：返回空结果与错误信息，不中断。
"""

import json
import re

from app.plugins.company_knowledge.prompts import (
    GRAPH_EXTRACT_SYSTEM_PROMPT,
    build_graph_extract_prompt,
)
from app.services.model_gateway import gateway

# 模糊匹配的标题最短长度，避免 "考勤" 之类过短标题误匹配
MIN_TITLE_MATCH_CHARS = 4


async def extract_relations_from_text(
    text: str,
    *,
    source_title: str,
    known_titles: list[dict],
) -> tuple[list[dict], list[dict]]:
    """对资料正文做 LLM 关系抽取。

    known_titles: [{"id": ..., "title": ...}]，目标文档候选。
    返回 (matched, unmatched)：
    - matched 项含 relation_type / target_source_id / target_title / evidence；
    - unmatched 项为 LLM 返回但无法匹配到目标文档的关系条目。
    """
    if not known_titles:
        return [], []
    prompt = build_graph_extract_prompt(source_title, text, [item["title"] for item in known_titles])
    raw = await gateway.chat(prompt, system=GRAPH_EXTRACT_SYSTEM_PROMPT)
    items = _parse_relations(raw)

    matched: list[dict] = []
    unmatched: list[dict] = []
    for item in items:
        target = _match_title(item.get("target_title"), known_titles)
        if target:
            matched.append(
                {
                    "relation_type": item["relation_type"],
                    "target_source_id": str(target["id"]),
                    "target_title": target["title"],
                    "evidence": str(item.get("evidence") or "").strip(),
                }
            )
        else:
            unmatched.append(item)
    return matched, unmatched


def _parse_relations(raw: str) -> list[dict]:
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

    valid_types = {"cite", "supersede", "parent", "related"}
    items = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        relation_type = item.get("relation_type")
        if relation_type not in valid_types:
            continue
        target_title = str(item.get("target_title") or "").strip()
        if not target_title:
            continue
        items.append(
            {
                "relation_type": relation_type,
                "target_title": target_title,
                "evidence": str(item.get("evidence") or "").strip(),
            }
        )
    return items


def _match_title(target_title: str, known_titles: list[dict]) -> dict | None:
    """标题匹配：先去书名号与空白做精确匹配，再做包含匹配（防过短误配、防版本后缀误配）。"""
    target = (target_title or "").strip().strip("《》").strip()
    if len(target) < MIN_TITLE_MATCH_CHARS:
        return None
    for known in known_titles:
        title = (known.get("title") or "").strip().strip("《》").strip()
        if len(title) < MIN_TITLE_MATCH_CHARS:
            continue
        if target == title:
            return known
        if target in title:
            if not _looks_like_version(title.replace(target, "")):
                return known
        if title in target:
            if not _looks_like_version(target.replace(title, "")):
                return known
    return None


def _looks_like_version(s: str) -> bool:
    """判断标题差异片段是否为版本标记（如（V2）、2025版、第3版），避免版本差异误配。"""
    s = (s or "").strip()
    if not s:
        return False
    return bool(
        re.fullmatch(r"[\s（(]*[Vv版第]?\d+(?:\.\d+)?\s*版?[\s）)]*", s)
    )
