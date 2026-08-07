"""公司资料分片前的数据清洗与预处理。

对应迭代文档"数据清洗与预处理"环节：
- 文本规范化：全角→半角、去 BOM/控制字符、统一换行、压缩连续空行
- 去噪：页眉/页脚/落款启发式剔除、HTML 残留标签清理、乱码字符移除
- 去重：完全重复段落/连续重复行合并（非语义相似，谨慎处理）
- 脱敏：手机号、身份证号等敏感信息替换为占位符
- 防注入：检测提示注入类文本并标记告警

停用词不主动移除（迭代文档明确提示可能损失语义）。
"""

import re
from dataclasses import dataclass, field

# 全角字符范围（FF01-FF5E → 21-7E），全角空格 U+3000 单独处理
_FULLWIDTH_RE = re.compile(r"[\uff01-\uff5e]")
_FULLWIDTH_SPACE_RE = re.compile("\u3000")
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_HTML_TAG_RE = re.compile(r"<[^>]{1,512}>")
_HTML_ENTITY_RE = re.compile(r"&(?:#\d{1,6}|#x[0-9a-fA-F]{1,6}|[a-zA-Z]{2,8});")
_GARBLED_RE = re.compile(r"[\ufffd]")
_PAGE_FOOTER_RE = re.compile(r"^\s*(?:第\s*\d+\s*页|[-\u2014]{3,}|page\s*\d+)\s*$", re.IGNORECASE)
_DATE_LINE_RE = re.compile(r"^\s*\d{4}[-/年]\d{1,2}[-/月]\d{1,2}日?\s*$")
_PHONE_RE = re.compile(r"(?<!\d)(?:\+?86[- ]?)?1[3-9]\d{9}(?!\d)")
_ID_CARD_RE = re.compile(r"(?<!\d)[1-9]\d{5}(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx](?!\d)")
_PROMPT_INJECTION_RE = re.compile(
    r"忽略(?:以上|之前|前面)?(?:的)?(?:指令|要求|提示|规则)|ignore\s+(?:all\s+)?(?:previous|above|prior)\s+(?:instructions|prompts|rules)",
    re.IGNORECASE,
)

# 脱敏占位符
PHONE_PLACEHOLDER = "【手机号已脱敏】"
ID_CARD_PLACEHOLDER = "【身份证号已脱敏】"


@dataclass(frozen=True)
class PreprocessStats:
    """清洗统计，用于前端报告展示。"""

    lines_before: int = 0
    lines_after: int = 0
    removed_blank_lines: int = 0
    removed_duplicate_lines: int = 0
    removed_header_footer_lines: int = 0
    removed_html_tags: int = 0
    replaced_phone_count: int = 0
    replaced_id_card_count: int = 0
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class PreprocessResult:
    content: str
    stats: PreprocessStats
    warnings: list[str] = field(default_factory=list)


def preprocess_markdown(text: str, *, title: str = "") -> PreprocessResult:
    """对 Markdown 正文执行数据清洗，返回清洗后内容与统计报告。"""
    if not text:
        return PreprocessResult(content="", stats=PreprocessStats(), warnings=["输入内容为空"])

    original_lines = (text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    stats = PreprocessStats(lines_before=len(original_lines))
    warnings: list[str] = []

    # 1. 文本规范化：全角→半角、去控制字符、去 BOM
    normalized_lines = []
    for line in original_lines:
        line = line.lstrip("\ufeff")
        line = _FULLWIDTH_SPACE_RE.sub(" ", line)
        line = _FULLWIDTH_RE.sub(_to_halfwidth, line)
        line = _CONTROL_CHARS_RE.sub("", line)
        normalized_lines.append(line)

    # 2. 去噪：页眉/页脚/日期行、HTML 残留、乱码字符
    cleaned_lines: list[str] = []
    for line in normalized_lines:
        stripped = line.strip()
        if _PAGE_FOOTER_RE.match(line) or _DATE_LINE_RE.match(line):
            stats = _bump(stats, removed_header_footer_lines=1)
            continue
        if _HTML_TAG_RE.search(line):
            line = _HTML_TAG_RE.sub("", line)
            stats = _bump(stats, removed_html_tags=1)
        line = _HTML_ENTITY_RE.sub("", line)
        line = _GARBLED_RE.sub("", line)
        cleaned_lines.append(line)

    # 3. 去重：完全相同的非空行只保留首次出现（保留 Markdown 标题的语义，不做语义去重）
    seen: set[str] = set()
    deduped_lines: list[str] = []
    for line in cleaned_lines:
        key = line.strip()
        if key and key in seen:
            stats = _bump(stats, removed_duplicate_lines=1)
            continue
        if key:
            seen.add(key)
        deduped_lines.append(line)

    # 4. 压缩连续空行
    compacted: list[str] = []
    blank_pending = False
    for line in deduped_lines:
        if not line.strip():
            if blank_pending:
                stats = _bump(stats, removed_blank_lines=1)
                continue
            blank_pending = True
            compacted.append("")
        else:
            blank_pending = False
            compacted.append(line)
    if compacted and not compacted[-1].strip():
        compacted.pop()

    # 5. 脱敏：手机号、身份证号
    masked_lines: list[str] = []
    for line in compacted:
        line, stats = _mask_line(line, stats)
        masked_lines.append(line)

    # 6. 防注入检测
    joined = "\n".join(masked_lines)
    if _PROMPT_INJECTION_RE.search(joined):
        warnings.append("检测到疑似提示注入文本（如\"忽略以上指令\"），请人工确认是否需要移除。")

    content = "\n".join(masked_lines).strip()
    stats = PreprocessStats(
        lines_before=stats.lines_before,
        lines_after=len(masked_lines),
        removed_blank_lines=stats.removed_blank_lines,
        removed_duplicate_lines=stats.removed_duplicate_lines,
        removed_header_footer_lines=stats.removed_header_footer_lines,
        removed_html_tags=stats.removed_html_tags,
        replaced_phone_count=stats.replaced_phone_count,
        replaced_id_card_count=stats.replaced_id_card_count,
        warnings=warnings,
    )
    return PreprocessResult(content=content, stats=stats, warnings=warnings)


def _mask_line(line: str, stats: PreprocessStats) -> tuple[str, PreprocessStats]:
    phones = _PHONE_RE.findall(line)
    if phones:
        stats = _bump(stats, replaced_phone_count=len(phones))
        line = _PHONE_RE.sub(PHONE_PLACEHOLDER, line)
    id_cards = _ID_CARD_RE.findall(line)
    if id_cards:
        stats = _bump(stats, replaced_id_card_count=len(id_cards))
        line = _ID_CARD_RE.sub(ID_CARD_PLACEHOLDER, line)
    return line, stats


def _to_halfwidth(match: "re.Match[str]") -> str:
    return chr(ord(match.group(0)) - 0xFEE0)


def _bump(stats: PreprocessStats, **kwargs: int) -> PreprocessStats:
    values = {
        "lines_before": stats.lines_before,
        "lines_after": stats.lines_after,
        "removed_blank_lines": stats.removed_blank_lines,
        "removed_duplicate_lines": stats.removed_duplicate_lines,
        "removed_header_footer_lines": stats.removed_header_footer_lines,
        "removed_html_tags": stats.removed_html_tags,
        "replaced_phone_count": stats.replaced_phone_count,
        "replaced_id_card_count": stats.replaced_id_card_count,
        "warnings": stats.warnings,
    }
    for key, delta in kwargs.items():
        values[key] = getattr(stats, key) + delta
    return PreprocessStats(**values)
