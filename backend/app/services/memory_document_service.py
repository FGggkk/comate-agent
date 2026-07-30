import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.memory import ForbiddenTopic, MemoryItem
from app.models.memory_document import MemoryDocument
from app.models.tacit import TacitProfile, TacitProfileVersion


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

DOC_HEADER_NOTE = "<!-- This file is managed by Comate. You can edit it; the app will detect changes and sync. -->"

MEMORY_SECTION_LABELS = {
    "preference": "长期偏好",
    "routine": "习惯与节奏",
    "current": "当前阶段",
    "fact": "重要事实",
    "recent": "最近更新",
}

MEMORY_TYPE_SECTION = {
    "preference": "preference",
    "routine": "routine",
    "event": "current",
    "profile": "fact",
    "insight": "fact",
    "general": "fact",
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


async def rebuild_user_doc(user_id: str, db: AsyncSession) -> dict:
    profile = await _load_active_tacit_profile(user_id, db)
    source_payload = {
        "profile_id": str(profile.id) if profile else "",
        "version_no": profile.version_no if profile else 0,
        "summary": profile.summary if profile else "",
        "profile": profile.profile if profile else {},
        "updated_at": profile.updated_at.isoformat() if profile and profile.updated_at else "",
    }
    content, metadata = render_user_doc(profile)
    return await save_document_version(
        user_id,
        DOC_USER,
        content,
        db,
        source_hash=build_source_hash(source_payload),
        metadata=metadata,
        next_review_at=profile.next_review_at if profile else None,
    )


async def rebuild_memory_doc(user_id: str, db: AsyncSession) -> dict:
    now = datetime.now(timezone.utc)
    memories = await _load_memory_doc_items(user_id, db)
    content, metadata = render_memory_doc(memories, now=now)
    source_payload = [
        _memory_source_payload(item)
        for item in memories
    ]
    return await save_document_version(
        user_id,
        DOC_MEMORY,
        content,
        db,
        source_hash=build_source_hash(source_payload),
        char_limit=DEFAULT_CHAR_LIMITS[DOC_MEMORY],
        item_limit=DEFAULT_ITEM_LIMITS[DOC_MEMORY],
        metadata=metadata,
    )


async def rebuild_boundary_doc(user_id: str, db: AsyncSession) -> dict:
    topics = await _load_forbidden_topics(user_id, db)
    content, metadata = render_boundary_doc(topics)
    source_payload = [
        {
            "id": str(topic.id),
            "topic": topic.topic_summary,
            "phrase": topic.original_phrase,
            "created_at": topic.created_at.isoformat() if topic.created_at else "",
        }
        for topic in topics
    ]
    return await save_document_version(
        user_id,
        DOC_BOUNDARY,
        content,
        db,
        source_hash=build_source_hash(source_payload),
        metadata=metadata,
    )


async def rebuild_delta_doc(
    user_id: str,
    db: AsyncSession,
    *,
    version: TacitProfileVersion | None = None,
) -> dict:
    if version is None:
        version = await _load_latest_tacit_version(user_id, db)
    content, metadata = render_delta_doc(version)
    source_payload = {
        "version_id": str(version.id) if version else "",
        "version_no": version.version_no if version else 0,
        "delta": version.delta if version else {},
        "decay_applied": version.decay_applied if version else {},
        "created_at": version.created_at.isoformat() if version and version.created_at else "",
    }
    return await save_document_version(
        user_id,
        DOC_DELTA,
        content,
        db,
        source_hash=build_source_hash(source_payload),
        metadata=metadata,
    )


async def rebuild_all_memory_documents(user_id: str, db: AsyncSession) -> dict:
    results = {}
    for doc_type, rebuild in (
        (DOC_USER, rebuild_user_doc),
        (DOC_MEMORY, rebuild_memory_doc),
        (DOC_BOUNDARY, rebuild_boundary_doc),
        (DOC_DELTA, rebuild_delta_doc),
    ):
        try:
            results[doc_type] = await rebuild(user_id, db)
        except Exception as e:
            results[doc_type] = {"success": False, "message": str(e)}
    return {"success": True, "documents": results}


def render_user_doc(profile: TacitProfile | None) -> tuple[str, dict]:
    profile_data = profile.profile if profile and isinstance(profile.profile, dict) else {}
    summary = _compact_line(profile.summary if profile else "", 600)
    lines = [
        "---",
        "doc_type: USER",
        f"version: {profile.version_no if profile else 0}",
        f"char_limit: {DEFAULT_CHAR_LIMITS[DOC_USER]}",
        f"updated_at: {_isoformat(profile.updated_at if profile else None)}",
        "managed_by: comate",
        "---",
        "",
        DOC_HEADER_NOTE,
        "",
        "# USER.md",
        "",
        "## 画像摘要",
        summary or "伴行正在形成对你的长期理解。",
        "",
    ]

    sections = (
        ("life_stage", "当前阶段"),
        ("long_term_goals", "长期目标"),
        ("routines", "习惯与节奏"),
        ("decision_style", "处事风格"),
        ("emotional_patterns", "情绪模式"),
        ("communication_style", "沟通偏好"),
        ("support_preferences", "伴行支持方式"),
    )
    retained_count = 0
    for key, label in sections:
        claims = _active_claims(profile_data.get(key, []), threshold=0.35)[:4]
        lines.extend([f"## {label}"])
        if not claims:
            lines.extend(["- 暂无稳定记录。", ""])
            continue
        for claim in claims:
            claim_text = _compact_line(claim.get("claim") or "", 140)
            if not claim_text:
                continue
            retained_count += 1
            lines.append(f"- {claim_text}")
        lines.append("")

    content = "\n".join(lines).strip() + "\n"
    return content, {
        "retained_count": retained_count,
        "source": "tacit_profile",
    }


def render_memory_doc(memories: list[MemoryItem], now: datetime | None = None) -> tuple[str, dict]:
    now = now or datetime.now(timezone.utc)
    candidates = []
    archived_count = 0
    skipped_count = 0
    seen: set[str] = set()
    for item in memories:
        lifecycle = (item.content or {}).get("lifecycle") if isinstance(item.content, dict) else None
        if lifecycle in {"dismissed", "archived", "superseded"}:
            archived_count += 1
            continue
        if item.memory_type == "event" and item.expires_at and _ensure_aware(item.expires_at) < now:
            archived_count += 1
            continue
        summary = _compact_line(item.summary or "", 160)
        if not summary:
            skipped_count += 1
            continue
        dedupe_key = _normalize_doc_text(summary)
        if dedupe_key in seen:
            skipped_count += 1
            continue
        seen.add(dedupe_key)
        score = _memory_doc_importance(item, now)
        section = _memory_doc_section(item)
        candidates.append({
            "item": item,
            "summary": summary,
            "score": score,
            "section": section,
            "updated_at": item.updated_at or item.created_at,
        })

    candidates.sort(
        key=lambda row: (
            row["score"],
            row["updated_at"] or datetime.min.replace(tzinfo=timezone.utc),
        ),
        reverse=True,
    )
    retained = candidates[:DEFAULT_ITEM_LIMITS[DOC_MEMORY]]
    trimmed_count = max(0, len(candidates) - len(retained))

    grouped = {key: [] for key in MEMORY_SECTION_LABELS}
    for row in retained:
        grouped[row["section"]].append(row)

    lines = [
        "---",
        "doc_type: MEMORY",
        "version: 1",
        f"char_limit: {DEFAULT_CHAR_LIMITS[DOC_MEMORY]}",
        f"item_limit: {DEFAULT_ITEM_LIMITS[DOC_MEMORY]}",
        f"updated_at: {_isoformat(now)}",
        "managed_by: comate",
        "---",
        "",
        DOC_HEADER_NOTE,
        "",
        "# MEMORY.md",
        "",
        "> 这是有限容量的关键记忆文档，不是聊天流水，也不是全部数据库备份。伴行会保留高价值、仍有用、未过期的信息，并逐步归档过期或重复内容。",
        "",
    ]
    for section_key, label in MEMORY_SECTION_LABELS.items():
        rows = grouped.get(section_key, [])
        lines.extend([f"## {label}"])
        if not rows:
            lines.extend(["- 暂无。", ""])
            continue
        for row in rows:
            item = row["item"]
            tags = _format_tags(item.topic_tags or [])
            time_note = _memory_time_note(item, now)
            suffix = " ".join(part for part in (tags, time_note) if part)
            lines.append(f"- {row['summary']}{(' ' + suffix) if suffix else ''}")
        lines.append("")

    content = "\n".join(lines).strip() + "\n"
    return content, {
        "source": "co_created_memory",
        "retained_count": len(retained),
        "candidate_count": len(candidates),
        "archived_count": archived_count,
        "skipped_count": skipped_count,
        "trimmed_count": trimmed_count,
        "trimmed_reason": "item_limit" if trimmed_count else "",
        "retention_policy": "key_memory_time_aware_bounded",
    }


def render_boundary_doc(topics: list[ForbiddenTopic]) -> tuple[str, dict]:
    lines = [
        "---",
        "doc_type: BOUNDARY",
        "version: 1",
        f"char_limit: {DEFAULT_CHAR_LIMITS[DOC_BOUNDARY]}",
        f"updated_at: {_isoformat(datetime.now(timezone.utc))}",
        "managed_by: comate",
        "---",
        "",
        DOC_HEADER_NOTE,
        "",
        "# BOUNDARY.md",
        "",
        "> 这些是伴行不应主动触碰、展开、联想或追问的边界。",
        "",
        "## 禁区话题",
    ]
    if not topics:
        lines.append("- 暂无。")
    else:
        for topic in topics[:DEFAULT_ITEM_LIMITS[DOC_BOUNDARY]]:
            lines.append(f"- {_compact_line(topic.topic_summary or '', 120)}")
    lines.append("")
    return "\n".join(lines).strip() + "\n", {
        "retained_count": min(len(topics), DEFAULT_ITEM_LIMITS[DOC_BOUNDARY]),
        "source": "forbidden_topics",
    }


def render_delta_doc(version: TacitProfileVersion | None) -> tuple[str, dict]:
    lines = [
        "---",
        "doc_type: DELTA",
        f"version: {version.version_no if version else 0}",
        f"char_limit: {DEFAULT_CHAR_LIMITS[DOC_DELTA]}",
        f"updated_at: {_isoformat(version.created_at if version else None)}",
        "managed_by: comate",
        "---",
        "",
        DOC_HEADER_NOTE,
        "",
        "# DELTA.md",
        "",
        "## 本次画像变化",
    ]
    retained_count = 0
    if not version:
        lines.append("- 暂无画像版本变化。")
    else:
        delta = version.delta or {}
        for dimension, items in delta.items():
            if not isinstance(items, list) or not items:
                continue
            lines.append(f"### {dimension}")
            for item in items[:6]:
                claim = _compact_line(str(item.get("claim") or ""), 140)
                change = item.get("change") or "updated"
                confidence = item.get("confidence")
                if not claim:
                    continue
                retained_count += 1
                confidence_part = f"，置信度 {confidence}" if confidence is not None else ""
                lines.append(f"- {change}: {claim}{confidence_part}")
        if retained_count == 0:
            lines.append("- 本次没有明显可展示的画像变化。")
    lines.append("")
    return "\n".join(lines).strip() + "\n", {
        "retained_count": retained_count,
        "source": "tacit_profile_version",
    }


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


async def _load_active_tacit_profile(user_id: str, db: AsyncSession) -> TacitProfile | None:
    result = await db.execute(
        select(TacitProfile).where(TacitProfile.user_id == user_id, TacitProfile.status == "active")
    )
    return result.scalar_one_or_none()


async def _load_latest_tacit_version(user_id: str, db: AsyncSession) -> TacitProfileVersion | None:
    result = await db.execute(
        select(TacitProfileVersion)
        .where(TacitProfileVersion.user_id == user_id)
        .order_by(TacitProfileVersion.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _load_memory_doc_items(user_id: str, db: AsyncSession) -> list[MemoryItem]:
    result = await db.execute(
        select(MemoryItem)
        .where(
            MemoryItem.user_id == user_id,
            MemoryItem.layer == "co_created",
            MemoryItem.status == "active",
            MemoryItem.user_confirmed.is_(True),
        )
        .order_by(MemoryItem.updated_at.desc())
        .limit(240)
    )
    return list(result.scalars().all())


async def _load_forbidden_topics(user_id: str, db: AsyncSession) -> list[ForbiddenTopic]:
    result = await db.execute(
        select(ForbiddenTopic).where(ForbiddenTopic.user_id == user_id).order_by(ForbiddenTopic.created_at.desc())
    )
    return list(result.scalars().all())


def _memory_source_payload(item: MemoryItem) -> dict:
    return {
        "id": str(item.id),
        "summary": item.summary,
        "memory_type": item.memory_type,
        "scope": item.scope,
        "topic_tags": item.topic_tags,
        "status": item.status,
        "content": item.content,
        "updated_at": item.updated_at.isoformat() if item.updated_at else "",
        "expires_at": item.expires_at.isoformat() if item.expires_at else "",
    }


def _memory_doc_section(item: MemoryItem) -> str:
    if item.memory_type == "event":
        return "current"
    if item.updated_at:
        age_days = max(0, (datetime.now(timezone.utc) - _ensure_aware(item.updated_at)).days)
        if age_days <= 3 and item.memory_type not in {"preference", "routine"}:
            return "recent"
    return MEMORY_TYPE_SECTION.get(item.memory_type or "general", "fact")


def _memory_doc_importance(item: MemoryItem, now: datetime) -> float:
    memory_type = item.memory_type or "general"
    score = {
        "preference": 90,
        "routine": 82,
        "profile": 76,
        "insight": 74,
        "event": 68,
        "general": 55,
    }.get(memory_type, 50)
    if item.user_confirmed:
        score += 18
    if item.scope in {"global", "topic"}:
        score += 6
    if item.topic_tags:
        score += min(8, len(item.topic_tags) * 2)
    score += min(10, float(item.confidence or 0) * 10)
    score += min(8, int(item.observed_count or 0) * 1.5)

    updated_at = _ensure_aware(item.updated_at or item.created_at or now)
    age_days = max(0, (now - updated_at).days)
    if age_days <= 7:
        score += 8
    elif age_days <= 30:
        score += 3
    elif memory_type not in {"preference", "routine", "profile"}:
        score -= min(20, (age_days - 30) / 3)

    if item.expires_at:
        expires_at = _ensure_aware(item.expires_at)
        if expires_at < now:
            score -= 100
        elif expires_at - now <= timedelta(days=7):
            score += 5
    return score


def _memory_time_note(item: MemoryItem, now: datetime) -> str:
    if item.expires_at:
        expires_at = _ensure_aware(item.expires_at)
        if expires_at < now:
            return "（已过期）"
        days = max(0, (expires_at - now).days)
        if days <= 7:
            return f"（约 {days} 天内到期）"
    if item.updated_at:
        age_days = max(0, (now - _ensure_aware(item.updated_at)).days)
        if age_days <= 3:
            return "（最近更新）"
    return ""


def _active_claims(claims: list[dict], threshold: float) -> list[dict]:
    return [
        c for c in sorted(claims or [], key=lambda x: (x.get("confidence") or 0, x.get("evidence_count") or 0), reverse=True)
        if c.get("status", "active") in {"active", "cooling"} and (c.get("confidence") or 0) >= threshold
    ]


def _format_tags(tags: list[str]) -> str:
    clean = [str(tag).strip() for tag in tags if str(tag or "").strip()]
    if not clean:
        return ""
    return f"（标签：{', '.join(clean[:4])}）"


def _compact_line(text: str, limit: int) -> str:
    return " ".join((text or "").split())[:limit].strip()


def _normalize_doc_text(text: str) -> str:
    return "".join((text or "").split()).casefold()


def _isoformat(value) -> str:
    if not value:
        return ""
    if isinstance(value, datetime):
        return _ensure_aware(value).isoformat()
    return str(value)


def _ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value
