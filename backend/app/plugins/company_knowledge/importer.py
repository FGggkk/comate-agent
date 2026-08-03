"""电子版公司资料的格式校验与文本读取。"""

import hashlib
from dataclasses import dataclass
from pathlib import Path


MAX_SOURCE_BYTES = 2 * 1024 * 1024
SUPPORTED_SOURCE_FORMATS = {"txt", "md", "markdown"}


class SourceImportError(ValueError):
    pass


@dataclass(frozen=True)
class ImportedText:
    source_format: str
    file_name: str
    content: str
    content_hash: str


def read_text_source(file_name: str, content: bytes) -> ImportedText:
    normalized_name = (file_name or "").strip()
    suffix = Path(normalized_name).suffix.lower().lstrip(".")
    if suffix not in SUPPORTED_SOURCE_FORMATS:
        raise SourceImportError("第一版仅支持 UTF-8 编码的 TXT 或 Markdown 文件")
    if not content:
        raise SourceImportError("上传文件为空")
    if len(content) > MAX_SOURCE_BYTES:
        raise SourceImportError("文件不能超过 2MB")

    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise SourceImportError("文件必须使用 UTF-8 编码") from exc

    normalized = _normalize_text(text)
    if not normalized:
        raise SourceImportError("文件不包含可索引的正文")

    source_format = "md" if suffix in {"md", "markdown"} else "txt"
    return ImportedText(
        source_format=source_format,
        file_name=normalized_name,
        content=normalized,
        content_hash=hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
    )


def _normalize_text(text: str) -> str:
    normalized = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in normalized.split("\n")]
    compacted = "\n".join(lines)
    while "\n\n\n" in compacted:
        compacted = compacted.replace("\n\n\n", "\n\n")
    return compacted.strip()
