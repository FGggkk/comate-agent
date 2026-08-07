"""电子版公司资料的格式校验与文本读取。

支持格式：UTF-8 TXT / Markdown、PDF（PyMuPDF）、Word .docx（python-docx）。
非文本格式经解析适配器转为 Markdown 后进入与文本相同的后续流程。
"""

import hashlib
from dataclasses import dataclass
from pathlib import Path

from app.plugins.company_knowledge.parsers import DocumentParseError, parse_document


MAX_SOURCE_BYTES = 10 * 1024 * 1024
SUPPORTED_SOURCE_FORMATS = {"txt", "md", "markdown", "pdf", "docx"}
TEXT_FORMATS = {"txt", "md", "markdown"}
DOC_FORMATS = {"pdf", "docx"}


class SourceImportError(ValueError):
    pass


@dataclass(frozen=True)
class ImportedText:
    source_format: str
    file_name: str
    content: str
    content_hash: str
    warnings: list[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.warnings is None:
            object.__setattr__(self, "warnings", [])


def read_text_source(file_name: str, content: bytes) -> ImportedText:
    normalized_name = (file_name or "").strip()
    suffix = Path(normalized_name).suffix.lower().lstrip(".")
    if suffix not in SUPPORTED_SOURCE_FORMATS:
        raise SourceImportError(
            "支持的格式：TXT、Markdown、PDF、Word（.docx）"
        )
    if not content:
        raise SourceImportError("上传文件为空")
    if len(content) > MAX_SOURCE_BYTES:
        raise SourceImportError("文件不能超过 10MB")

    if suffix in TEXT_FORMATS:
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise SourceImportError("TXT/Markdown 文件必须使用 UTF-8 编码") from exc

        normalized = _normalize_text(text)
        if not normalized:
            raise SourceImportError("文件不包含可索引的正文")

        source_format = "md" if suffix in {"md", "markdown"} else "txt"
        return ImportedText(
            source_format=source_format,
            file_name=normalized_name,
            content=normalized,
            content_hash=hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
            warnings=[],
        )

    # PDF / Word：解析为 Markdown 正文
    try:
        parsed = parse_document(normalized_name, content)
    except DocumentParseError as exc:
        raise SourceImportError(str(exc)) from exc

    if not parsed.content.strip():
        raise SourceImportError("文件不包含可索引的正文")

    return ImportedText(
        source_format=parsed.source_format,
        file_name=normalized_name,
        content=_normalize_text(parsed.content),
        content_hash=hashlib.sha256(parsed.content.encode("utf-8")).hexdigest(),
        warnings=list(parsed.warnings),
    )


def to_markdown(imported: ImportedText, title: str) -> tuple[str, list[str]]:
    """将资料规范为可审阅的 Markdown 正文。"""
    content = imported.content.strip()
    warnings: list[str] = list(getattr(imported, "warnings", None) or [])
    if imported.source_format == "md":
        markdown = content
    elif imported.source_format == "txt":
        markdown = f"# {title.strip()}\n\n{content}"
        warnings.append("TXT 已按原文转换为 Markdown；请在切分前确认标题和段落边界。")
    else:
        # PDF / Word 解析结果：加标题，转换告警来自解析适配器
        markdown = f"# {title.strip()}\n\n{content}"
        if not warnings:
            warnings.append("文档已由解析工具转换为 Markdown，请在切分前确认内容完整性。")
    return _normalize_text(markdown), warnings


def content_hash(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def _normalize_text(text: str) -> str:
    normalized = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in normalized.split("\n")]
    compacted = "\n".join(lines)
    while "\n\n\n" in compacted:
        compacted = compacted.replace("\n\n\n", "\n\n")
    return compacted.strip()
