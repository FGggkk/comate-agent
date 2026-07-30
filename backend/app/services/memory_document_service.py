import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.memory_document import MemoryDocument


DOC_USER = "USER"
DOC_MEMORY = "MEMORY"
DOC_BOUNDARY = "BOUNDARY"
DOC_DELTA = "DELTA"

MEMORY_DOCUMENT_TYPES = {DOC_USER, DOC_MEMORY, DOC_BOUNDARY, DOC_DELTA}
MEMORY_DOCUMENT_STATUSES = {"active", "stale", "archived"}
MEMORY_DOCUMENT_SYNC_STATUSES = {"synced", "stale", "conflict", "import_pending", "export_pending"}
MEMORY_DOCUMENT_EDITORS = {"app", "user", "system"}

DEFAULT_FILE_NAMES = {
    DOC_USER: "USER.md",
    DOC_MEMORY: "MEMORY.md",
    DOC_BOUNDARY: "BOUNDARY.md",
    DOC_DELTA: "DELTA.md",
}

DEFAULT_CHAR_LIMITS = {
    DOC_USER: 1600,
    DOC_MEMORY: 5000,
    DOC_BOUNDARY: 1200,
    DOC_DELTA: 2400,
}

DEFAULT_ITEM_LIMITS = {
    DOC_USER: 24,
    DOC_MEMORY: 80,
    DOC_BOUNDARY: 40,
    DOC_DELTA: 40,
}


def normalize_doc_type(doc_type: str) -> str:
    normalized = (doc_type or "").strip().upper()
    if normalized not in MEMORY_DOCUMENT_TYPES:
        raise ValueError(f"unsupported memory document type: {doc_type}")
    return normalized


def normalize_sync_status(sync_status: str) -> str:
    normalized = (sync_status or "synced").strip().lower()
    if normalized not in MEMORY_DOCUMENT_SYNC_STATUSES:
        raise ValueError(f"unsupported memory document sync status: {sync_status}")
    return normalized


def normalize_editor(edited_by: str) -> str:
    normalized = (edited_by or "app").strip().lower()
    if normalized not in MEMORY_DOCUMENT_EDITORS:
        raise ValueError(f"unsupported memory document editor: {edited_by}")
    return normalized


def default_file_name(doc_type: str) -> str:
    return DEFAULT_FILE_NAMES[normalize_doc_type(doc_type)]


def build_source_hash(payload: Any) -> str:
    raw = json.dumps(payload or {}, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def build_file_hash(content: str) -> str:
    return hashlib.sha256((content or "").encode("utf-8")).hexdigest()


def enforce_char_limit(content: str, char_limit: int | None) -> tuple[str, dict]:
    text = content or ""
    limit = int(char_limit or 0)
    metadata = {
        "char_count": len(text),
        "char_limit": limit,
        "trimmed": False,
    }
    if limit <= 0 or len(text) <= limit:
        return text, metadata

    suffix = "\n\n<!-- trimmed: memory document exceeded char_limit -->"
    if limit <= len(suffix):
        suffix = ""
    available = max(0, limit - len(suffix))
    metadata["trimmed"] = True
    metadata["original_char_count"] = len(text)
    metadata["final_char_count"] = min(limit, len(text[:available].rstrip()) + len(suffix))
    metadata["trimmed_reason"] = "char_limit"
    return f"{text[:available].rstrip()}{suffix}", metadata


async def get_active_document(
    user_id: str,
    doc_type: str,
    db: AsyncSession,
) -> MemoryDocument | None:
    normalized_type = normalize_doc_type(doc_type)
    result = await db.execute(
        select(MemoryDocument).where(
            MemoryDocument.user_id == user_id,
            MemoryDocument.doc_type == normalized_type,
            MemoryDocument.status == "active",
        )
    )
    return result.scalar_one_or_none()


async def get_document_snapshot(
    user_id: str,
    doc_type: str,
    db: AsyncSession,
) -> dict | None:
    document = await get_active_document(user_id, doc_type, db)
    return document_to_dict(document) if document else None


async def list_active_documents(user_id: str, db: AsyncSession) -> list[dict]:
    result = await db.execute(
        select(MemoryDocument)
        .where(MemoryDocument.user_id == user_id, MemoryDocument.status == "active")
        .order_by(MemoryDocument.doc_type.asc())
    )
    return [document_to_dict(item) for item in result.scalars().all()]


async def mark_document_stale(
    user_id: str,
    doc_type: str,
    db: AsyncSession,
    reason: str = "",
    metadata: dict | None = None,
) -> dict:
    document = await get_active_document(user_id, doc_type, db)
    if not document:
        return {"success": True, "changed": False}

    now = datetime.now(timezone.utc)
    document.status = "stale"
    document.sync_status = "stale"
    document.document_metadata = {
        **(document.document_metadata or {}),
        "stale_reason": reason or "source_changed",
        "stale_at": now.isoformat(),
        **(metadata or {}),
    }
    await db.commit()
    await db.refresh(document)
    return {"success": True, "changed": True, "document": document_to_dict(document)}


async def mark_document_sync_status(
    user_id: str,
    doc_type: str,
    db: AsyncSession,
    sync_status: str,
    *,
    reason: str = "",
    edited_by: str = "app",
    file_path: str | None = None,
    file_hash: str | None = None,
    metadata: dict | None = None,
) -> dict:
    document = await get_active_document(user_id, doc_type, db)
    if not document:
        return {"success": True, "changed": False}

    now = datetime.now(timezone.utc)
    normalized_status = normalize_sync_status(sync_status)
    document.sync_status = normalized_status
    document.edited_by = normalize_editor(edited_by)
    if file_path is not None:
        document.file_path = file_path
    if file_hash is not None:
        document.file_hash = file_hash
    if normalized_status == "import_pending":
        document.last_imported_at = None
    elif normalized_status == "export_pending":
        document.last_exported_at = None
    elif normalized_status == "synced":
        if document.edited_by == "user":
            document.last_imported_at = now
        else:
            document.last_exported_at = now
    document.document_metadata = {
        **(document.document_metadata or {}),
        "sync_reason": reason or normalized_status,
        "sync_updated_at": now.isoformat(),
        **(metadata or {}),
    }
    await db.commit()
    await db.refresh(document)
    return {"success": True, "changed": True, "document": document_to_dict(document)}


async def mark_stale_if_source_changed(
    user_id: str,
    doc_type: str,
    source_hash: str,
    db: AsyncSession,
    reason: str = "source_changed",
) -> dict:
    document = await get_active_document(user_id, doc_type, db)
    if not document or (document.source_hash or "") == (source_hash or ""):
        return {"success": True, "changed": False}
    return await mark_document_stale(
        user_id,
        doc_type,
        db,
        reason=reason,
        metadata={"previous_source_hash": document.source_hash, "next_source_hash": source_hash},
    )


async def save_document_version(
    user_id: str,
    doc_type: str,
    content: str,
    db: AsyncSession,
    *,
    source_hash: str = "",
    char_limit: int | None = None,
    item_limit: int | None = None,
    status: str = "active",
    sync_status: str = "synced",
    edited_by: str = "app",
    file_path: str = "",
    file_hash: str = "",
    metadata: dict | None = None,
    last_imported_at=None,
    last_exported_at=None,
    expires_at=None,
    next_review_at=None,
) -> dict:
    normalized_type = normalize_doc_type(doc_type)
    normalized_status = (status or "active").strip().lower()
    if normalized_status not in MEMORY_DOCUMENT_STATUSES:
        raise ValueError(f"unsupported memory document status: {status}")
    normalized_sync_status = normalize_sync_status(sync_status)
    normalized_editor = normalize_editor(edited_by)

    resolved_char_limit = int(char_limit or DEFAULT_CHAR_LIMITS[normalized_type])
    resolved_item_limit = int(item_limit or DEFAULT_ITEM_LIMITS[normalized_type])
    limited_content, limit_metadata = enforce_char_limit(content, resolved_char_limit)
    resolved_file_path = file_path or default_file_name(normalized_type)
    resolved_file_hash = file_hash or build_file_hash(limited_content)

    if normalized_status == "active":
        active_result = await db.execute(
            select(MemoryDocument).where(
                MemoryDocument.user_id == user_id,
                MemoryDocument.doc_type == normalized_type,
                MemoryDocument.status == "active",
            )
        )
        for active in active_result.scalars().all():
            active.status = "archived"

    latest_result = await db.execute(
        select(MemoryDocument)
        .where(MemoryDocument.user_id == user_id, MemoryDocument.doc_type == normalized_type)
        .order_by(MemoryDocument.version_no.desc())
        .limit(1)
    )
    latest = latest_result.scalar_one_or_none()
    version_no = (latest.version_no if latest else 0) + 1

    now = datetime.now(timezone.utc)
    document = MemoryDocument(
        user_id=user_id,
        doc_type=normalized_type,
        content=limited_content,
        version_no=version_no,
        char_limit=resolved_char_limit,
        item_limit=resolved_item_limit,
        source_hash=source_hash or build_source_hash(limited_content),
        file_path=resolved_file_path,
        file_hash=resolved_file_hash,
        status=normalized_status,
        sync_status=normalized_sync_status,
        edited_by=normalized_editor,
        document_metadata={**(metadata or {}), **limit_metadata},
        generated_at=now,
        last_imported_at=(
            last_imported_at
            if last_imported_at is not None
            else (now if normalized_editor == "user" and normalized_sync_status == "synced" else None)
        ),
        last_exported_at=(
            last_exported_at
            if last_exported_at is not None
            else (now if normalized_editor == "app" and normalized_sync_status == "synced" else None)
        ),
        expires_at=expires_at,
        next_review_at=next_review_at,
    )
    db.add(document)
    await db.commit()
    await db.refresh(document)
    return {"success": True, "document": document_to_dict(document)}


def document_to_dict(document: MemoryDocument | None) -> dict:
    if not document:
        return {}
    return {
        "id": str(document.id),
        "user_id": str(document.user_id),
        "doc_type": document.doc_type,
        "content": document.content or "",
        "version_no": document.version_no or 0,
        "char_limit": document.char_limit or 0,
        "item_limit": document.item_limit or 0,
        "source_hash": document.source_hash or "",
        "file_path": document.file_path or "",
        "file_hash": document.file_hash or "",
        "status": document.status,
        "sync_status": document.sync_status or "synced",
        "edited_by": document.edited_by or "app",
        "metadata": document.document_metadata or {},
        "generated_at": document.generated_at.isoformat() if document.generated_at else None,
        "last_imported_at": document.last_imported_at.isoformat() if document.last_imported_at else None,
        "last_exported_at": document.last_exported_at.isoformat() if document.last_exported_at else None,
        "expires_at": document.expires_at.isoformat() if document.expires_at else None,
        "next_review_at": document.next_review_at.isoformat() if document.next_review_at else None,
        "created_at": document.created_at.isoformat() if document.created_at else None,
        "updated_at": document.updated_at.isoformat() if document.updated_at else None,
    }
