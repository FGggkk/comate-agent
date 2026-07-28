import asyncio
import hashlib
import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import text as sa_text

from app.db.session import async_session_factory
from app.models.memory import ForbiddenTopic, MemoryItem, MemoryObservation, PendingAnchor
from app.services.embedding_service import get_embedding
from app.services import reminder_service


CHAT_MEMORY_LAYERS = ("co_created", "tacit")
APP_TZ = timezone(timedelta(hours=8))
ALLOWED_MEMORY_TYPES = {
    "general",
    "preference",
    "profile",
    "event",
    "routine",
    "boundary",
    "insight",
}
STRUCTURED_MEMORY_FIELDS = {
    "event_at",
    "expires_at",
    "confidence",
    "observed_count",
    "last_observed_at",
    "dedupe_key",
    "review_after",
}


async def search(
    user_id: str,
    query: str,
    top_k: int = 5,
    db: AsyncSession = None,
) -> list[dict]:
    """语义检索 + 关键词兜底 + 禁区过滤。

    先验层由系统/管理员维护，只用于安全策略，不作为聊天记忆主动引用。
    """
    forbidden = await get_forbidden(user_id, db)
    forbidden_words = {f.topic_summary.lower() for f in forbidden}

    # 1. 尝试 pgvector 语义搜索
    query_vec = await get_embedding(query)
    if query_vec:
        from sqlalchemy import text
        vec_literal = "[" + ",".join(str(v) for v in query_vec) + "]"
        sql = text("""
            SELECT id, layer, memory_type, summary, content,
                   user_confirmed, is_inference,
                   event_at, expires_at, confidence, observed_count,
                   last_observed_at, review_after,
                   created_at,
                   1 - (embedding <=> CAST(:query_vec AS vector)) AS score
            FROM memory_items
            WHERE user_id = CAST(:user_id AS uuid)
              AND status = 'active'
              AND layer IN ('co_created', 'tacit')
              AND embedding IS NOT NULL
            ORDER BY embedding <=> CAST(:query_vec AS vector)
            LIMIT :candidate_limit
        """)
        result = await db.execute(
            sql,
            {
                "query_vec": vec_literal,
                "user_id": user_id,
                "candidate_limit": max(top_k * 4, top_k),
            },
        )
        rows = result.fetchall()
        results = []
        for row in rows:
            if not _is_available_for_chat(row.layer, row.user_confirmed, row.memory_type, row.content, row.expires_at):
                continue
            # 禁区过滤
            summary_lower = (row.summary or "").lower()
            if any(fw in summary_lower for fw in forbidden_words):
                continue
            content = row.content or {}
            results.append({
                "id": str(row.id),
                "layer": row.layer,
                "memory_type": row.memory_type or "general",
                "summary": row.summary,
                "content": content,
                "event_at": _format_optional_datetime(row.event_at or _parse_datetime(content.get("event_at"))),
                "expires_at": _format_optional_datetime(row.expires_at or _parse_datetime(content.get("expires_at"))),
                "confidence": row.confidence or 0,
                "observed_count": row.observed_count or 0,
                "last_observed_at": _format_optional_datetime(
                    row.last_observed_at or _parse_datetime(content.get("last_observed_at"))
                ),
                "review_after": _format_optional_datetime(row.review_after or _parse_datetime(content.get("review_after"))),
                "user_confirmed": row.user_confirmed,
                "is_inference": row.is_inference,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "lifecycle": _memory_lifecycle(row.memory_type, content, row.expires_at),
                "is_expired": _is_expired_memory(row.memory_type, content, row.expires_at),
                "score": float(row.score) if row.score else 0,
            })
        if results:
            return results[:top_k]

    # 2. 兜底：ILIKE 关键词模糊匹配
    result = await db.execute(
        select(MemoryItem).where(
            MemoryItem.user_id == user_id,
            MemoryItem.status == "active",
            MemoryItem.layer.in_(CHAT_MEMORY_LAYERS),
        ).order_by(MemoryItem.created_at.desc()).limit(100)
    )
    items = result.scalars().all()

    keywords = set(query.lower().split())
    scored = []
    for item in items:
        if not _is_item_available_for_chat(item):
            continue
        score = 0.0
        summary_lower = (item.summary or "").lower()
        for kw in keywords:
            if kw in summary_lower:
                score += 0.3
        if item.user_confirmed:
            score += 0.2
        if item.layer == "co_created":
            score += 0.1
        if score > 0:
            scored.append((score, item))

    scored.sort(key=lambda x: x[0], reverse=True)

    results = []
    for score, item in scored[:top_k]:
        summary_lower = (item.summary or "").lower()
        if any(fw in summary_lower for fw in forbidden_words):
            continue
        results.append(_item_to_dict(item))

    return results


async def create_co_created(
    user_id: str,
    summary: str,
    memory_type: str = "general",
    content: dict | None = None,
    event_at: datetime | None = None,
    expires_at: datetime | None = None,
    confidence: float | None = None,
    observed_count: int | None = None,
    last_observed_at: datetime | None = None,
    review_after: datetime | None = None,
    db: AsyncSession = None,
) -> dict:
    summary = (summary or "").strip()
    memory_type = (memory_type or "general").strip()
    if not summary:
        return {"success": False, "message": "记忆内容不能为空"}
    if memory_type not in ALLOWED_MEMORY_TYPES:
        return {"success": False, "message": "不支持的记忆类型"}

    existing = await _get_existing_active_memory(
        user_id=user_id,
        layer="co_created",
        summary=summary,
        memory_type=memory_type,
        db=db,
    )
    if existing:
        return {"success": True, "data": _item_to_dict(existing), "message": "已存在相同记忆"}

    normalized_content = _normalize_memory_content(
        memory_type=memory_type,
        content=content or {},
        event_at=event_at,
        expires_at=expires_at,
        source="user_explicit",
    )
    structured_fields = _derive_memory_fields(
        layer="co_created",
        memory_type=memory_type,
        summary=summary,
        content=normalized_content,
        event_at=event_at,
        expires_at=expires_at,
        confidence=confidence,
        observed_count=observed_count,
        last_observed_at=last_observed_at,
        review_after=review_after,
    )
    reminder_candidate = _build_reminder_candidate(
        memory_type,
        summary,
        normalized_content,
        event_at=structured_fields.get("event_at"),
    )
    if reminder_candidate:
        normalized_content["reminder_candidate"] = reminder_candidate
        normalized_content.setdefault("reminder_status", "candidate")

    item = await add_with_embedding(
        user_id=user_id,
        layer="co_created",
        summary=summary[:500],
        content=normalized_content,
        db=db,
        memory_type=memory_type,
        source_type="user_explicit",
        user_confirmed=True,
        defer_enrichment=True,
        **structured_fields,
    )
    return {"success": True, "data": _item_to_dict(item), "message": "ok"}


async def create_event_reminder(user_id: str, item_id: str, db: AsyncSession = None) -> dict:
    result = await db.execute(
        select(MemoryItem).where(
            MemoryItem.id == item_id,
            MemoryItem.user_id == user_id,
            MemoryItem.status == "active",
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        return {"success": False, "message": "记忆不存在或无权操作"}
    if item.memory_type != "event":
        return {"success": False, "message": "只有事件记忆可以创建提醒"}

    content = dict(item.content or {})
    if content.get("reminder_id"):
        return {
            "success": True,
            "data": {"memory": _item_to_dict(item), "reminder": None},
            "message": "已创建过提醒",
        }

    candidate = content.get("reminder_candidate") or _build_reminder_candidate(
        item.memory_type,
        item.summary,
        content,
        event_at=item.event_at,
    )
    if not candidate:
        return {"success": False, "message": "这条事件记忆还没有可用提醒时间"}

    remind_at = _parse_datetime(candidate.get("remind_at"))
    if not remind_at:
        return {"success": False, "message": "提醒时间格式无效"}
    if remind_at <= datetime.now(timezone.utc):
        return {"success": False, "message": "提醒时间已经过去"}

    reminder = await reminder_service.create_once(
        user_id=user_id,
        content=candidate.get("content") or f"提醒：{item.summary}",
        remind_at=remind_at,
        db=db,
    )
    content["reminder_id"] = reminder["id"]
    content["reminder_status"] = "created"
    content["reminder_candidate"] = candidate
    item.content = content
    await db.commit()
    await db.refresh(item)
    return {"success": True, "data": {"memory": _item_to_dict(item), "reminder": reminder}, "message": "ok"}


async def add_observation(
    user_id: str,
    item_id: str,
    observed_text: str,
    db: AsyncSession = None,
    source_type: str = "chat",
    source_ref: str = "",
    confidence: float = 0.0,
    metadata: dict | None = None,
) -> dict:
    result = await db.execute(
        select(MemoryItem).where(
            MemoryItem.id == item_id,
            MemoryItem.user_id == user_id,
            MemoryItem.status == "active",
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        return {"success": False, "message": "记忆不存在或无权操作"}

    now = datetime.now(timezone.utc)
    observation = MemoryObservation(
        memory_id=item.id,
        user_id=user_id,
        source_type=source_type,
        source_ref=source_ref,
        observed_text=(observed_text or "")[:2000],
        confidence=confidence,
        observation_metadata=metadata or {},
        observed_at=now,
    )
    db.add(observation)
    item.observed_count = (item.observed_count or 0) + 1
    item.last_observed_at = now
    item.confidence = max(item.confidence or 0, confidence)
    await db.commit()
    await db.refresh(item)
    return {"success": True, "data": {"memory": _item_to_dict(item), "observation_id": str(observation.id)}}


async def _get_existing_active_memory(
    user_id: str,
    layer: str,
    summary: str,
    memory_type: str,
    db: AsyncSession,
) -> MemoryItem | None:
    dedupe_key = _build_memory_dedupe_key(layer, memory_type, summary)
    result = await db.execute(
        select(MemoryItem).where(
            MemoryItem.user_id == user_id,
            MemoryItem.layer == layer,
            MemoryItem.memory_type == memory_type,
            MemoryItem.dedupe_key == dedupe_key,
            MemoryItem.status == "active",
        ).limit(1)
    )
    existing = result.scalar_one_or_none()
    if existing:
        return existing

    result = await db.execute(
        select(MemoryItem).where(
            MemoryItem.user_id == user_id,
            MemoryItem.layer == layer,
            MemoryItem.memory_type == memory_type,
            MemoryItem.summary == summary[:500],
            MemoryItem.status == "active",
        ).limit(1)
    )
    return result.scalar_one_or_none()


async def add(
    user_id: str,
    layer: str,
    summary: str,
    content: dict = None,
    db: AsyncSession = None,
    memory_type: str = "general",
    event_at: datetime | None = None,
    expires_at: datetime | None = None,
    confidence: float | None = None,
    observed_count: int | None = None,
    last_observed_at: datetime | None = None,
    dedupe_key: str | None = None,
    review_after: datetime | None = None,
) -> MemoryItem:
    memory_type = memory_type or "general"
    structured_fields = _derive_memory_fields(
        layer=layer,
        memory_type=memory_type,
        summary=summary,
        content=content or {},
        event_at=event_at,
        expires_at=expires_at,
        confidence=confidence,
        observed_count=observed_count,
        last_observed_at=last_observed_at,
        dedupe_key=dedupe_key,
        review_after=review_after,
    )
    item = MemoryItem(
        user_id=user_id,
        layer=layer,
        memory_type=memory_type,
        summary=summary,
        content=content or {},
        source_type="user_input",
        user_confirmed=(layer != "tacit"),
        is_inference=(layer == "tacit"),
        **structured_fields,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


async def update_item(user_id: str, item_id: str, data: dict, db: AsyncSession = None) -> dict:
    structured_updates = {key: data.pop(key) for key in list(data.keys()) if key in STRUCTURED_MEMORY_FIELDS}

    result = await db.execute(
        select(MemoryItem).where(
            MemoryItem.id == item_id,
            MemoryItem.user_id == user_id,
            MemoryItem.status == "active",
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        return {"success": False, "message": "记忆不存在或无权操作"}
    if item.layer == "priors":
        return {"success": False, "message": "先验层由系统维护，不能编辑"}

    if "memory_type" in data:
        memory_type = (data["memory_type"] or "general").strip()
        if memory_type not in ALLOWED_MEMORY_TYPES:
            return {"success": False, "message": "不支持的记忆类型"}
        data["memory_type"] = memory_type

    if "content" in data:
        data["content"] = _normalize_memory_content(
            memory_type=data.get("memory_type", item.memory_type or "general"),
            content=data["content"] or {},
            source=(item.content or {}).get("source", item.source_type),
        )

    if "memory_type" in data and "content" not in data:
        data["content"] = _normalize_memory_content(
            memory_type=data["memory_type"],
            content=item.content or {},
            source=(item.content or {}).get("source", item.source_type),
        )

    should_refresh_structured = bool(
        structured_updates
        or "content" in data
        or "memory_type" in data
        or "summary" in data
    )
    if should_refresh_structured:
        content_for_fields = data.get("content", item.content or {})
        structured_fields = _derive_memory_fields(
            layer=item.layer,
            memory_type=data.get("memory_type", item.memory_type or "general"),
            summary=data.get("summary", item.summary),
            content=content_for_fields,
            event_at=structured_updates.get("event_at"),
            expires_at=structured_updates.get("expires_at"),
            confidence=structured_updates.get("confidence"),
            observed_count=structured_updates.get("observed_count"),
            last_observed_at=structured_updates.get("last_observed_at"),
            dedupe_key=structured_updates.get("dedupe_key"),
            review_after=structured_updates.get("review_after"),
        )
        if "event_at" not in structured_updates and "content" not in data:
            structured_fields["event_at"] = item.event_at
        if "expires_at" not in structured_updates and "content" not in data:
            structured_fields["expires_at"] = item.expires_at
        if "confidence" not in structured_updates and "content" not in data:
            structured_fields["confidence"] = item.confidence
        if "observed_count" not in structured_updates and "content" not in data:
            structured_fields["observed_count"] = item.observed_count
        if "last_observed_at" not in structured_updates and "content" not in data:
            structured_fields["last_observed_at"] = item.last_observed_at
        if "review_after" not in structured_updates and "content" not in data:
            structured_fields["review_after"] = item.review_after
        if "summary" not in data and "memory_type" not in data and "dedupe_key" not in structured_updates:
            structured_fields["dedupe_key"] = item.dedupe_key
        for key, value in structured_fields.items():
            setattr(item, key, value)

    for key, value in data.items():
        setattr(item, key, value)
    await db.commit()
    return {"success": True}


async def delete_item(user_id: str, item_id: str, db: AsyncSession = None) -> dict:
    result = await db.execute(
        select(MemoryItem).where(
            MemoryItem.id == item_id,
            MemoryItem.user_id == user_id,
            MemoryItem.status == "active",
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        return {"success": False, "message": "记忆不存在或无权操作"}
    if item.layer == "priors":
        return {"success": False, "message": "先验层由系统维护，不能删除"}

    item.status = "deleted"
    await db.commit()
    return {"success": True}


async def get_all(user_id: str, db: AsyncSession = None) -> dict:
    result = await db.execute(
        select(MemoryItem).where(
            MemoryItem.user_id == user_id,
            MemoryItem.status == "active",
        ).order_by(MemoryItem.created_at.desc())
    )
    items = result.scalars().all()

    layers = {"priors": [], "co_created": [], "tacit": []}
    for item in items:
        layers.setdefault(item.layer, []).append(_item_to_dict(item))

    forbidden = await get_forbidden(user_id, db)
    anchors = await get_anchors(user_id, db)

    return {
        "layers": layers,
        "forbidden_topics": [{"id": str(f.id), "topic": f.topic_summary} for f in forbidden],
        "pending_anchors": [
            {"id": str(a.id), "topic": a.topic_summary, "status": a.status, "expires_at": a.expires_at.isoformat()}
            for a in anchors
        ],
    }


async def get_forbidden(user_id: str, db: AsyncSession = None) -> list[ForbiddenTopic]:
    result = await db.execute(
        select(ForbiddenTopic).where(ForbiddenTopic.user_id == user_id)
    )
    return result.scalars().all()


async def add_forbidden(user_id: str, topic: str, phrase: str = "", db: AsyncSession = None) -> dict:
    ft = ForbiddenTopic(user_id=user_id, topic_summary=topic, original_phrase=phrase)
    db.add(ft)
    await db.commit()
    return {"success": True}


async def remove_forbidden(user_id: str, topic_id: str, db: AsyncSession = None) -> dict:
    result = await db.execute(
        delete(ForbiddenTopic).where(
            ForbiddenTopic.id == topic_id,
            ForbiddenTopic.user_id == user_id,
        )
    )
    await db.commit()
    if result.rowcount == 0:
        return {"success": False, "message": "禁区话题不存在或无权操作"}
    return {"success": True}


async def get_anchors(user_id: str, db: AsyncSession = None) -> list[PendingAnchor]:
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(PendingAnchor).where(
            PendingAnchor.user_id == user_id,
            PendingAnchor.status == "pending",
            PendingAnchor.expires_at > now,
        )
    )
    return result.scalars().all()


async def fulfill_anchor(user_id: str, anchor_id: str, db: AsyncSession = None) -> dict:
    result = await db.execute(
        update(PendingAnchor).where(
            PendingAnchor.id == anchor_id,
            PendingAnchor.user_id == user_id,
            PendingAnchor.status == "pending",
        ).values(status="fulfilled")
    )
    await db.commit()
    if result.rowcount == 0:
        return {"success": False, "message": "待续话题不存在或无权操作"}
    return {"success": True}


def _item_to_dict(item: MemoryItem) -> dict:
    content = item.content or {}
    event_at = item.event_at or _parse_datetime(content.get("event_at"))
    expires_at = item.expires_at or _parse_datetime(content.get("expires_at"))
    last_observed_at = item.last_observed_at or _parse_datetime(content.get("last_observed_at"))
    review_after = item.review_after or _parse_datetime(content.get("review_after"))
    return {
        "id": str(item.id),
        "layer": item.layer,
        "memory_type": item.memory_type or "general",
        "summary": item.summary,
        "content": content,
        "event_at": _format_optional_datetime(event_at),
        "expires_at": _format_optional_datetime(expires_at),
        "confidence": item.confidence or _parse_float(content.get("confidence"), 0),
        "observed_count": item.observed_count or _parse_int(content.get("observed_count"), 0),
        "last_observed_at": _format_optional_datetime(last_observed_at),
        "review_after": _format_optional_datetime(review_after),
        "reminder_id": content.get("reminder_id"),
        "reminder_status": content.get("reminder_status"),
        "reminder_candidate": content.get("reminder_candidate"),
        "lifecycle": _memory_lifecycle(item.memory_type, content, expires_at),
        "is_expired": _is_expired_memory(item.memory_type, content, expires_at),
        "needs_cleanup": _needs_cleanup(item.memory_type, content, expires_at),
        "user_confirmed": item.user_confirmed,
        "is_inference": item.is_inference,
        "source_type": item.source_type,
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
    }


def _normalize_memory_content(
    memory_type: str,
    content: dict,
    event_at: datetime | None = None,
    expires_at: datetime | None = None,
    source: str | None = None,
) -> dict:
    normalized = dict(content or {})
    if source and not normalized.get("source"):
        normalized["source"] = source
    normalized.setdefault("lifecycle", "active")

    if event_at:
        normalized["event_at"] = _format_datetime(event_at)
    if expires_at:
        normalized["expires_at"] = _format_datetime(expires_at)

    if memory_type == "event":
        parsed_event_at = _parse_datetime(normalized.get("event_at"))
        if parsed_event_at and not normalized.get("expires_at"):
            normalized["expires_at"] = _format_datetime(parsed_event_at + timedelta(days=1))

    return normalized


def _derive_memory_fields(
    layer: str,
    memory_type: str,
    summary: str,
    content: dict | None,
    event_at: datetime | str | None = None,
    expires_at: datetime | str | None = None,
    confidence: float | str | None = None,
    observed_count: int | str | None = None,
    last_observed_at: datetime | str | None = None,
    dedupe_key: str | None = None,
    review_after: datetime | str | None = None,
) -> dict:
    content = content or {}
    parsed_event_at = _parse_datetime(event_at) or _parse_datetime(content.get("event_at"))
    parsed_expires_at = _parse_datetime(expires_at) or _parse_datetime(content.get("expires_at"))
    if memory_type == "event" and parsed_event_at and not parsed_expires_at:
        parsed_expires_at = parsed_event_at + timedelta(days=1)
    parsed_review_after = _parse_datetime(review_after) or _parse_datetime(content.get("review_after"))
    if memory_type == "event" and parsed_expires_at and not parsed_review_after:
        parsed_review_after = parsed_expires_at

    return {
        "event_at": parsed_event_at,
        "expires_at": parsed_expires_at,
        "confidence": _parse_float(confidence if confidence is not None else content.get("confidence"), 0.0),
        "observed_count": _parse_int(observed_count if observed_count is not None else content.get("observed_count"), 0),
        "last_observed_at": _parse_datetime(last_observed_at) or _parse_datetime(content.get("last_observed_at")),
        "dedupe_key": (dedupe_key or content.get("dedupe_key") or _build_memory_dedupe_key(layer, memory_type, summary))[:160],
        "review_after": parsed_review_after,
    }


def _build_memory_dedupe_key(layer: str, memory_type: str | None, summary: str) -> str:
    normalized = re.sub(r"\s+", "", (summary or "").strip().casefold())
    raw = f"{layer}|{memory_type or 'general'}|{normalized[:500]}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _format_optional_datetime(value: datetime | str | None) -> str | None:
    if not value:
        return None
    parsed = _parse_datetime(value)
    return parsed.isoformat() if parsed else str(value)


def _parse_float(value, default: float = 0.0) -> float:
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _parse_int(value, default: int = 0) -> int:
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _format_datetime(value: datetime | str) -> str:
    if isinstance(value, str):
        parsed = _parse_datetime(value)
        return parsed.isoformat() if parsed else value
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def _format_local_datetime(value: datetime) -> str:
    local = value.astimezone(APP_TZ)
    return f"{local.month}月{local.day}日 {local.hour:02d}:{local.minute:02d}"


def _parse_datetime(value) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _build_reminder_candidate(
    memory_type: str | None,
    summary: str,
    content: dict | None,
    event_at: datetime | str | None = None,
) -> dict | None:
    if memory_type != "event":
        return None
    content = content or {}
    parsed_event_at = _parse_datetime(event_at) or _parse_datetime(content.get("event_at"))
    if not parsed_event_at:
        return None

    now = datetime.now(timezone.utc)
    if parsed_event_at <= now:
        return None

    if parsed_event_at - now > timedelta(hours=36):
        local_event = parsed_event_at.astimezone(APP_TZ)
        remind_at = datetime(
            local_event.year,
            local_event.month,
            local_event.day,
            20,
            0,
            tzinfo=APP_TZ,
        ) - timedelta(days=1)
        reason = "提前一天晚上提醒"
    elif parsed_event_at - now > timedelta(hours=4):
        remind_at = parsed_event_at - timedelta(hours=2)
        reason = "提前两小时提醒"
    else:
        remind_at = parsed_event_at - timedelta(hours=1)
        reason = "提前一小时提醒"

    if remind_at <= now:
        return None

    return {
        "content": f"提醒：{summary}",
        "remind_at": _format_datetime(remind_at),
        "event_at": _format_datetime(parsed_event_at),
        "label": f"{reason}（{_format_local_datetime(remind_at)}）",
        "reason": reason,
    }


def _memory_lifecycle(memory_type: str | None, content: dict | None, expires_at: datetime | str | None = None) -> str:
    content = content or {}
    lifecycle = content.get("lifecycle") or "active"
    if memory_type == "event" and lifecycle == "active" and _is_expired_memory(memory_type, content, expires_at):
        return "expired"
    return lifecycle


def _is_expired_memory(memory_type: str | None, content: dict | None, expires_at: datetime | str | None = None) -> bool:
    if memory_type != "event":
        return False
    parsed_expires_at = _parse_datetime(expires_at) or _parse_datetime((content or {}).get("expires_at"))
    if not parsed_expires_at:
        return False
    return parsed_expires_at <= datetime.now(timezone.utc)


def _needs_cleanup(memory_type: str | None, content: dict | None, expires_at: datetime | str | None = None) -> bool:
    return memory_type == "event" and _memory_lifecycle(memory_type, content, expires_at) == "expired"


def _is_item_available_for_chat(item: MemoryItem) -> bool:
    return _is_available_for_chat(item.layer, item.user_confirmed, item.memory_type, item.content, item.expires_at)


def _is_available_for_chat(
    layer: str,
    user_confirmed: bool,
    memory_type: str | None,
    content: dict | None,
    expires_at: datetime | str | None = None,
) -> bool:
    if layer not in CHAT_MEMORY_LAYERS:
        return False
    if not user_confirmed:
        return False
    if _needs_cleanup(memory_type, content, expires_at):
        return False
    if (content or {}).get("lifecycle") in {"dismissed", "archived"}:
        return False
    return True


async def extract_candidates(user_id: str, message: str, reply: str, db: AsyncSession = None) -> list[dict]:
    """对话后用 LLM 提取记忆候选，等待用户确认后再保存。"""
    summary = await _extract_memory_summary(message, reply)
    if not summary:
        return []

    memory_type = _guess_memory_type(f"{message}\n{summary}")
    content = {
        "source_message": message[:200],
        "source_reply": reply[:200],
        "source": "model_candidate",
    }
    if memory_type == "event":
        event_meta = _extract_event_metadata(f"{message}\n{summary}")
        content.update(event_meta)

    return [{
        "summary": summary,
        "layer": "co_created",
        "memory_type": memory_type,
        "content": content,
    }]


def _guess_memory_type(summary: str) -> str:
    preference_words = ("喜欢", "讨厌", "偏好", "不喜欢", "爱吃", "不吃")
    event_words = ("面试", "考试", "会议", "截止", "ddl", "DDL", "约了", "预约")
    routine_words = ("每天", "每周", "常常", "经常", "习惯", "跑步", "健身")
    if any(word in summary for word in preference_words):
        return "preference"
    if any(word in summary for word in event_words):
        return "event"
    if any(word in summary for word in routine_words):
        return "routine"
    return "general"


def _extract_event_metadata(text: str) -> dict:
    event_at, estimated = _infer_event_datetime(text)
    if not event_at:
        return {}
    content = {
        "event_at": _format_datetime(event_at),
        "expires_at": _format_datetime(event_at + timedelta(days=1)),
        "event_time_estimated": estimated,
    }
    candidate = _build_reminder_candidate("event", _compact_text(text, 120), content)
    if candidate:
        content["reminder_candidate"] = candidate
        content["reminder_status"] = "candidate"
    return content


def _infer_event_datetime(text: str) -> tuple[datetime | None, bool]:
    now = datetime.now(APP_TZ)
    target_date = None
    estimated_time = False

    days_delta = _parse_relative_day_delta(text)
    if days_delta is not None:
        target_date = (now + timedelta(days=days_delta)).date()
    else:
        target_date = _parse_explicit_date(text, now)

    if not target_date:
        return None, False

    hour, minute, has_time = _parse_time_of_day(text)
    if not has_time:
        hour, minute = 9, 0
        estimated_time = True

    event_at = datetime(target_date.year, target_date.month, target_date.day, hour, minute, tzinfo=APP_TZ)
    if event_at <= now:
        event_at = event_at + timedelta(days=1)
    return event_at.astimezone(timezone.utc), estimated_time


def _parse_relative_day_delta(text: str) -> int | None:
    if "大后天" in text:
        return 3
    if "后天" in text:
        return 2
    if "明天" in text:
        return 1
    if "今天" in text:
        return 0

    match = re.search(r"(\d+|[一二两三四五六七八九十]+)\s*天后", text)
    if match:
        return _parse_chinese_number(match.group(1))
    return None


def _parse_explicit_date(text: str, now: datetime):
    iso_match = re.search(r"(20\d{2})[-/.年](\d{1,2})[-/.月](\d{1,2})", text)
    if iso_match:
        year, month, day = (int(part) for part in iso_match.groups())
        return datetime(year, month, day, tzinfo=APP_TZ).date()

    md_match = re.search(r"(\d{1,2})\s*月\s*(\d{1,2})\s*[日号]?", text)
    if md_match:
        month, day = (int(part) for part in md_match.groups())
        year = now.year
        candidate = datetime(year, month, day, tzinfo=APP_TZ)
        if candidate.date() < now.date():
            candidate = datetime(year + 1, month, day, tzinfo=APP_TZ)
        return candidate.date()

    weekday_match = re.search(r"下周([一二三四五六日天])", text)
    if weekday_match:
        target_weekday = "一二三四五六日天".index(weekday_match.group(1))
        if target_weekday == 7:
            target_weekday = 6
        days_until_next_week = 7 - now.weekday()
        return (now + timedelta(days=days_until_next_week + target_weekday)).date()
    return None


def _parse_time_of_day(text: str) -> tuple[int, int, bool]:
    colon_match = re.search(r"(\d{1,2})[:：](\d{2})", text)
    if colon_match:
        hour, minute = (int(part) for part in colon_match.groups())
        return _normalize_hour(hour, text), minute, True

    hour_match = re.search(r"(凌晨|早上|上午|中午|下午|晚上)?\s*(\d{1,2}|[一二两三四五六七八九十]+)\s*点半?", text)
    if hour_match:
        period, raw_hour = hour_match.groups()
        hour = _parse_chinese_number(raw_hour)
        minute = 30 if "点半" in hour_match.group(0) else 0
        return _normalize_hour(hour, period or text), minute, True
    return 9, 0, False


def _normalize_hour(hour: int, context: str) -> int:
    if any(word in context for word in ("下午", "晚上")) and hour < 12:
        return hour + 12
    if "中午" in context and hour < 11:
        return hour + 12
    if "凌晨" in context and hour == 12:
        return 0
    return hour


def _parse_chinese_number(raw: str) -> int:
    if raw.isdigit():
        return int(raw)
    mapping = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
    if raw == "十":
        return 10
    if raw.startswith("十"):
        return 10 + mapping.get(raw[-1], 0)
    if "十" in raw:
        left, _, right = raw.partition("十")
        return mapping.get(left, 0) * 10 + mapping.get(right, 0)
    return mapping.get(raw, 0)


def _compact_text(text: str, limit: int) -> str:
    compacted = " ".join((text or "").split())
    return compacted[:limit]


async def _extract_memory_summary(message: str, reply: str) -> str | None:
    """调用 LLM 从对话中提取值得记住的信息"""
    from app.services.model_gateway import gateway

    prompt = f"""从以下对话中，提取用户值得记住的个人信息。

要求：
- 如果用户提到了身份、偏好、目标、经历、习惯等信息，用一句话概括
- 如果没有值得记住的信息，输出空字符串
- 只返回一句话，不要多余内容

用户说：{message[:500]}
AI回复：{reply[:500]}
"""

    try:
        full = ""
        async for chunk in gateway.stream(prompt, system="你是一个记忆提取助手，只提取客观事实，不做主观推断。"):
            full += chunk
        full = full.strip().strip('"').strip("'").strip()
        # 过滤无意义回复
        skip_words = ["没有值得记住的信息", "无值得记住", "未发现值得记忆", "未提到任何"]
        if len(full) < 4 or any(w in full[:15] for w in skip_words):
            return None
        return full[:200]
    except Exception as e:
        print(f"[extract_candidates] LLM 调用失败: {e}")
        return None


async def add_with_embedding(
    user_id: str,
    layer: str,
    summary: str,
    content: dict = None,
    db: AsyncSession = None,
    memory_type: str = "general",
    source_type: str = "user_input",
    user_confirmed: bool | None = None,
    defer_enrichment: bool = False,
    event_at: datetime | None = None,
    expires_at: datetime | None = None,
    confidence: float | None = None,
    observed_count: int | None = None,
    last_observed_at: datetime | None = None,
    dedupe_key: str | None = None,
    review_after: datetime | None = None,
) -> MemoryItem | None:
    """保存记忆并异步生成 embedding"""
    if user_confirmed is None:
        user_confirmed = (layer != "tacit")
    structured_fields = _derive_memory_fields(
        layer=layer,
        memory_type=memory_type,
        summary=summary,
        content=content or {},
        event_at=event_at,
        expires_at=expires_at,
        confidence=confidence,
        observed_count=observed_count,
        last_observed_at=last_observed_at,
        dedupe_key=dedupe_key,
        review_after=review_after,
    )
    item = MemoryItem(
        user_id=user_id,
        layer=layer,
        memory_type=memory_type,
        summary=summary,
        content=content or {},
        source_type=source_type,
        user_confirmed=user_confirmed,
        is_inference=(layer == "tacit"),
        **structured_fields,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)

    if defer_enrichment:
        asyncio.create_task(_enrich_memory_item(user_id, item.id, summary))
        return item

    # 异步生成 embedding
    try:
        vec = await get_embedding(summary)
        if vec:
            item.embedding = vec
            await db.commit()
    except Exception as e:
        print(f"[add_with_embedding] embedding 生成失败: {e}")

    # 矛盾检测：新记忆与旧记忆冲突时清理旧记录
    try:
        await resolve_contradictions(user_id, summary, item.id, db)
    except Exception as e:
        print(f"[resolve_contradictions] 失败: {e}")

    return item


async def _enrich_memory_item(user_id: str, item_id, summary: str) -> None:
    """后台补齐 embedding 和矛盾清理，避免确认记忆时卡住聊天交互。"""
    try:
        async with async_session_factory() as db:
            result = await db.execute(
                select(MemoryItem).where(
                    MemoryItem.id == item_id,
                    MemoryItem.user_id == user_id,
                    MemoryItem.status == "active",
                )
            )
            item = result.scalar_one_or_none()
            if not item:
                return

            vec = await get_embedding(summary)
            if vec:
                item.embedding = vec
                await db.commit()

            await resolve_contradictions(user_id, summary, item_id, db)
    except Exception as e:
        print(f"[memory_enrich] 后台补齐失败: {e}")


async def resolve_contradictions(user_id: str, new_summary: str, new_item_id, db: AsyncSession):
    """检测并清理与新记忆矛盾的旧记忆"""
    # 1. 用语义搜索找到相似记忆
    vec = await get_embedding(new_summary)
    if not vec:
        return

    vec_literal = "[" + ",".join(str(v) for v in vec) + "]"
    result = await db.execute(
        sa_text("""
            SELECT id, summary FROM memory_items
            WHERE user_id = CAST(:uid AS uuid)
              AND status = 'active'
              AND id != CAST(:nid AS uuid)
              AND layer IN ('co_created', 'tacit')
              AND embedding IS NOT NULL
            ORDER BY embedding <=> CAST(:vec AS vector)
            LIMIT 5
        """),
        {"uid": user_id, "nid": str(new_item_id), "vec": vec_literal},
    )
    candidates = result.fetchall()
    if not candidates:
        return

    # 2. 用 LLM 判断是否有矛盾
    from app.services.model_gateway import gateway
    old_list = "\n".join(f"- {r.summary}" for r in candidates)
    prompt = f"""判断新旧两条记忆是否矛盾（例如一个说喜欢，一个说不喜欢同一事物）。

新记忆：{new_summary}

旧记忆列表：
{old_list}

请输出矛盾的旧记忆序号（从1开始），没有矛盾则输出0。只输出数字。
"""
    try:
        full = ""
        async for chunk in gateway.stream(prompt, system="你是一个记忆对比助手，只判断是否矛盾。"):
            full += chunk
        result_num = full.strip().strip('"').strip("'")
        idx = int(result_num)
        if 1 <= idx <= len(candidates):
            old_item = candidates[idx - 1]
            await db.execute(
                sa_text("UPDATE memory_items SET status='deleted' WHERE id = CAST(:id AS uuid)"),
                {"id": str(old_item.id)},
            )
            await db.commit()
            print(f"[resolve] 矛盾删除旧记忆: {old_item.summary[:40]}")
    except (ValueError, IndexError, Exception) as e:
        print(f"[resolve] LLM判断失败: {e}")


async def update_anchors(user_id: str, message: str, reply: str, db: AsyncSession = None) -> None:
    """识别未完待续锚点"""
    anchor_triggers = ["改天聊聊", "下次聊", "回头再说", "下次再说"]
    for trigger in anchor_triggers:
        if trigger in message:
            anchor = PendingAnchor(
                user_id=user_id,
                topic_summary=message[-100:],
                context=message,
                expires_at=datetime.now(timezone.utc) + timedelta(days=7),
            )
            db.add(anchor)
            await db.commit()
            break
