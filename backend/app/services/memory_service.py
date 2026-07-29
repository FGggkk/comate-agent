import asyncio
import hashlib
import json
import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import text as sa_text

from app.db.session import async_session_factory
from app.models.memory import ForbiddenTopic, MemoryItem, MemoryObservation, PendingAnchor
from app.services.embedding_service import get_embedding
from app.services import reminder_service
from app.services.memory_gate_service import append_gate_trace


CHAT_MEMORY_LAYERS = ("co_created",)
APP_TZ = timezone(timedelta(hours=8))
MEMORY_SCOPES = {"global", "topic", "session", "ephemeral"}
DEFAULT_MEMORY_SCOPE = "global"
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
    "scope",
    "topic_tags",
}

TOPIC_KEYWORDS = {
    "fitness": ("健身", "跑步", "运动", "训练", "锻炼", "公里", "肌肉", "体能", "力量", "瑜伽"),
    "food": ("水果", "橘子", "香蕉", "苹果", "葡萄", "猕猴桃", "超市", "饮食", "吃", "补充", "维生素"),
    "interview": ("面试", "求职", "简历", "offer", "岗位", "招聘", "hr", "HR", "技术岗"),
    "work": ("项目", "代码", "分支", "提交", "pr", "PR", "bug", "需求", "上线", "开发"),
    "emotion": ("焦虑", "压力", "烦", "累", "紧张", "情绪", "崩", "难受", "开心", "低落"),
    "finance": ("记账", "账单", "预算", "消费", "花销", "收入", "支出", "省钱"),
    "travel": ("旅游", "旅行", "行程", "酒店", "机票", "路线", "景点"),
    "study": ("学习", "考试", "备考", "刷题", "课程", "复习", "论文"),
    "sleep": ("睡眠", "作息", "早睡", "熬夜", "失眠", "起床"),
    "boundary": ("禁区", "不要提", "别提", "不想聊", "不主动", "避开"),
}

FORBIDDEN_ADD_PATTERNS = (
    r"(?:以后|之后|后面|接下来|以后都|以后也)?(?:不要|别|别再|不要再|别总是|不要总是|不想|不愿意|不希望)(?:主动)?(?:再)?(?:提起|提到|提及|提(?!醒)|说|聊|谈|讨论|展开|碰|触碰)(?:到|起|及)?(?P<topic>[^，。！？；\n]{1,40})",
    r"(?:把|将)?(?P<topic>[^，。！？；\n]{1,40}?)(?:设为|列为|加入|放进|当成)(?:禁区|边界|避雷)",
    r"(?P<topic>[^，。！？；\n]{1,40}?)(?:是|属于|算是)(?:我的)?(?:禁区|边界|避雷)",
    r"(?P<topic>[^，。！？；\n]{1,40}?)(?:以后|之后|后面)?(?:不要|别|别再|不要再)(?:主动)?(?:再)?(?:提起|提到|提及|提(?!醒)|说|聊|谈|讨论|展开|碰|触碰)(?:了|啦)?",
)

FORBIDDEN_REMOVE_PATTERNS = (
    r"(?:可以|能|允许|愿意)(?:重新|继续|再)?(?:提起|提到|提及|提(?!醒)|说|聊|谈|讨论|展开)(?:到|起|及)?(?P<topic>[^，。！？；\n]{1,40})",
    r"(?:解除|取消|移除|删除|去掉)(?:关于|对)?(?P<topic>[^，。！？；\n]{1,40}?)(?:的)?(?:禁区|边界|避开|避雷)",
    r"(?P<topic>[^，。！？；\n]{1,40}?)(?:不用|不需要)(?:再)?(?:避开|回避)",
    r"(?P<topic>[^，。！？；\n]{1,40}?)(?:不再是|不是)(?:禁区|边界|避雷)",
)

VAGUE_FORBIDDEN_TERMS = {
    "这个",
    "那个",
    "这件事",
    "那件事",
    "这事",
    "那事",
    "这个话题",
    "那个话题",
    "刚才那个",
    "它",
}


async def search(
    user_id: str,
    query: str,
    top_k: int = 5,
    db: AsyncSession = None,
    layers: tuple[str, ...] | None = None,
    gate_trace: list[dict] | None = None,
) -> list[dict]:
    """检索可用于当前问题的共建记忆。

    先验层由系统/管理员维护，只用于安全策略，不作为聊天记忆主动引用。
    默契层画像由 tacit_profile_service 单独读取，避免和零散事实混在一起。
    """
    target_layers = tuple(layer for layer in (layers or CHAT_MEMORY_LAYERS) if layer in CHAT_MEMORY_LAYERS)
    if not target_layers:
        return []

    forbidden = await get_forbidden(user_id, db)
    query_topics = classify_query_topics(query)

    # 1. 尝试 pgvector 语义搜索
    query_vec = await get_embedding(query)
    if query_vec:
        from sqlalchemy import text
        vec_literal = "[" + ",".join(str(v) for v in query_vec) + "]"
        layer_clause = ", ".join(f"'{layer}'" for layer in target_layers)
        sql = text("""
            SELECT id, layer, memory_type, summary, content,
                   user_confirmed, is_inference,
                   scope, topic_tags,
                   event_at, expires_at, confidence, observed_count,
                   last_observed_at, review_after,
                   created_at,
                   1 - (embedding <=> CAST(:query_vec AS vector)) AS score
            FROM memory_items
            WHERE user_id = CAST(:user_id AS uuid)
              AND status = 'active'
              AND layer IN ({layer_clause})
              AND embedding IS NOT NULL
            ORDER BY embedding <=> CAST(:query_vec AS vector)
            LIMIT :candidate_limit
        """.format(layer_clause=layer_clause))
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
                append_gate_trace(
                    gate_trace,
                    source="co_created",
                    kept=False,
                    reason="unavailable_for_chat",
                    item_id=str(row.id),
                    text=row.summary or "",
                    metadata={
                        "path": "vector",
                        "layer": row.layer,
                        "memory_type": row.memory_type,
                        "user_confirmed": row.user_confirmed,
                    },
                )
                continue
            item_data = _row_to_memory_dict(row)
            if is_forbidden_text(_memory_dict_text(item_data), forbidden):
                append_gate_trace(
                    gate_trace,
                    source="co_created",
                    kept=False,
                    reason="forbidden",
                    item_id=item_data["id"],
                    text=item_data.get("summary") or "",
                    metadata={"path": "vector"},
                )
                continue
            semantic_score = float(row.score) if row.score else 0
            relevance = explain_memory_relevance(item_data, query, query_topics, semantic_score)
            if not relevance["kept"]:
                append_gate_trace(
                    gate_trace,
                    source="co_created",
                    kept=False,
                    reason=relevance["reason"],
                    item_id=item_data["id"],
                    text=item_data.get("summary") or "",
                    metadata={**relevance["metadata"], "path": "vector"},
                )
                continue
            item_data["score"] = _memory_relevance_score(item_data, query, query_topics, semantic_score)
            append_gate_trace(
                gate_trace,
                source="co_created",
                kept=True,
                reason=relevance["reason"],
                item_id=item_data["id"],
                text=item_data.get("summary") or "",
                metadata={**relevance["metadata"], "path": "vector", "score": item_data["score"]},
            )
            results.append(item_data)
        if results:
            results.sort(key=lambda item: item.get("score", 0), reverse=True)
            return results[:top_k]

    # 2. 兜底：结构化主题和关键词匹配
    result = await db.execute(
        select(MemoryItem).where(
            MemoryItem.user_id == user_id,
            MemoryItem.status == "active",
            MemoryItem.layer.in_(target_layers),
        ).order_by(MemoryItem.created_at.desc()).limit(100)
    )
    items = result.scalars().all()

    scored = []
    for item in items:
        if not _is_item_available_for_chat(item):
            append_gate_trace(
                gate_trace,
                source="co_created",
                kept=False,
                reason="unavailable_for_chat",
                item_id=str(item.id),
                text=item.summary or "",
                metadata={
                    "path": "fallback",
                    "layer": item.layer,
                    "memory_type": item.memory_type,
                    "user_confirmed": item.user_confirmed,
                },
            )
            continue
        data = _item_to_dict(item)
        if is_forbidden_text(_memory_dict_text(data), forbidden):
            append_gate_trace(
                gate_trace,
                source="co_created",
                kept=False,
                reason="forbidden",
                item_id=data["id"],
                text=data.get("summary") or "",
                metadata={"path": "fallback"},
            )
            continue
        relevance = explain_memory_relevance(data, query, query_topics)
        if not relevance["kept"]:
            append_gate_trace(
                gate_trace,
                source="co_created",
                kept=False,
                reason=relevance["reason"],
                item_id=data["id"],
                text=data.get("summary") or "",
                metadata={**relevance["metadata"], "path": "fallback"},
            )
            continue
        score = _memory_relevance_score(data, query, query_topics)
        append_gate_trace(
            gate_trace,
            source="co_created",
            kept=True,
            reason=relevance["reason"],
            item_id=data["id"],
            text=data.get("summary") or "",
            metadata={**relevance["metadata"], "path": "fallback", "score": score},
        )
        scored.append((score, data))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [dict(item, score=score) for score, item in scored[:top_k]]


async def create_co_created(
    user_id: str,
    summary: str,
    memory_type: str = "general",
    content: dict | None = None,
    scope: str | None = None,
    topic_tags: list[str] | None = None,
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
        scope=scope,
        topic_tags=topic_tags,
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
        scope=scope,
        topic_tags=topic_tags,
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
    superseded_count = await _resolve_explicit_memory_replacements(user_id, item, db)
    if superseded_count:
        try:
            from app.services.tacit_profile_service import update_tacit_profile
            await update_tacit_profile(user_id, db)
        except Exception as e:
            print(f"[memory] 更新默契画像失败: {e}")
    data = _item_to_dict(item)
    data["superseded_count"] = superseded_count
    return {"success": True, "data": data, "message": "ok"}


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
    scope: str | None = None,
    topic_tags: list[str] | None = None,
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
        scope=scope,
        topic_tags=topic_tags,
    )
    content = _sync_memory_metadata(content or {}, structured_fields)
    item = MemoryItem(
        user_id=user_id,
        layer=layer,
        memory_type=memory_type,
        summary=summary,
        content=content,
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
            scope=structured_updates.get("scope"),
            topic_tags=structured_updates.get("topic_tags"),
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
        if "scope" not in structured_updates and "content" not in data and "summary" not in data and "memory_type" not in data:
            structured_fields["scope"] = item.scope
        if "topic_tags" not in structured_updates and "content" not in data and "summary" not in data and "memory_type" not in data:
            structured_fields["topic_tags"] = item.topic_tags or []
        if "summary" not in data and "memory_type" not in data and "dedupe_key" not in structured_updates:
            structured_fields["dedupe_key"] = item.dedupe_key
        if (
            "content" in data
            or "summary" in data
            or "memory_type" in data
            or "scope" in structured_updates
            or "topic_tags" in structured_updates
        ):
            data["content"] = _sync_memory_metadata(data.get("content", item.content or {}), structured_fields)
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
    tacit_profile = {}
    try:
        from app.services.tacit_profile_service import get_profile_snapshot
        tacit_profile = await get_profile_snapshot(user_id, db)
    except Exception as e:
        print(f"[memory] 默契画像读取失败: {e}")

    return {
        "layers": layers,
        "tacit_profile": tacit_profile,
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
    terms = _extract_forbidden_terms(topic)
    normalized_topic = next(iter(terms), _compact_forbidden_text(topic))
    if not normalized_topic:
        return {"success": False, "message": "禁区话题不能为空"}

    existing = await get_forbidden(user_id, db)
    for item in existing:
        if _forbidden_item_matches_terms(item, {normalized_topic}):
            return {"success": True, "id": str(item.id), "created": False}

    ft = ForbiddenTopic(user_id=user_id, topic_summary=normalized_topic, original_phrase=phrase)
    db.add(ft)
    await db.commit()
    await db.refresh(ft)
    return {"success": True, "id": str(ft.id), "created": True}


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


async def sync_forbidden_topics_from_message(user_id: str, message: str, db: AsyncSession = None) -> dict:
    """根据用户明示边界更新禁区话题，用于模型回复前立即生效。"""
    add_terms = extract_forbidden_add_terms(message)
    remove_terms = extract_forbidden_remove_terms(message)
    changed = {"added": [], "removed": []}

    if remove_terms:
        changed["removed"] = await remove_forbidden_by_terms(user_id, remove_terms, db)

    if add_terms:
        for term in sorted(add_terms):
            result = await add_forbidden(user_id, term, message, db)
            if result.get("success") and result.get("created", True):
                changed["added"].append(term)

    return changed


async def remove_forbidden_by_terms(user_id: str, terms: set[str], db: AsyncSession = None) -> list[str]:
    flattened_terms: set[str] = set()
    for term in terms:
        flattened_terms.update(_extract_forbidden_terms(term))
    if not flattened_terms:
        return []

    existing = await get_forbidden(user_id, db)
    targets = [item for item in existing if _forbidden_item_matches_terms(item, flattened_terms)]
    if not targets:
        return []

    await db.execute(
        delete(ForbiddenTopic).where(
            ForbiddenTopic.user_id == user_id,
            ForbiddenTopic.id.in_([item.id for item in targets]),
        )
    )
    await db.commit()
    return [item.topic_summary for item in targets]


def extract_forbidden_add_terms(text: str) -> set[str]:
    return _extract_forbidden_request_terms(text, FORBIDDEN_ADD_PATTERNS)


def extract_forbidden_remove_terms(text: str) -> set[str]:
    return _extract_forbidden_request_terms(text, FORBIDDEN_REMOVE_PATTERNS)


def forbidden_topics_to_terms(forbidden_topics: list[ForbiddenTopic | dict | str] | None) -> set[str]:
    terms: set[str] = set()
    for item in forbidden_topics or []:
        if isinstance(item, str):
            pieces = [item]
        elif isinstance(item, dict):
            pieces = [str(item.get("topic") or item.get("topic_summary") or ""), str(item.get("original_phrase") or "")]
        else:
            pieces = [str(getattr(item, "topic_summary", "") or ""), str(getattr(item, "original_phrase", "") or "")]
        for piece in pieces:
            terms.update(_extract_forbidden_terms(piece))
    return terms


def is_forbidden_text(text: str | dict | None, forbidden_topics: list[ForbiddenTopic | dict | str] | None) -> bool:
    terms = forbidden_topics_to_terms(forbidden_topics)
    if not terms:
        return False
    normalized_text = _normalize_match_text(_stringify_forbidden_text(text))
    return any(term and _normalize_match_text(term) in normalized_text for term in terms)


def filter_forbidden_lines(text: str, forbidden_topics: list[ForbiddenTopic | dict | str] | None) -> str:
    if not text or not forbidden_topics:
        return text or ""
    kept = [line for line in text.splitlines() if not is_forbidden_text(line, forbidden_topics)]
    return "\n".join(line for line in kept if line.strip()).strip()


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
    topic_tags = _normalize_topic_tags(item.topic_tags or content.get("topic_tags"), item.summary or "")
    scope = _normalize_scope(
        item.scope or content.get("scope"),
        item.memory_type or "general",
        content,
        item.summary or "",
        event_at,
        expires_at,
        topic_tags,
    )
    return {
        "id": str(item.id),
        "layer": item.layer,
        "memory_type": item.memory_type or "general",
        "summary": item.summary,
        "content": content,
        "scope": scope,
        "topic_tags": topic_tags,
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


def _row_to_memory_dict(row) -> dict:
    content = row.content or {}
    event_at = row.event_at or _parse_datetime(content.get("event_at"))
    expires_at = row.expires_at or _parse_datetime(content.get("expires_at"))
    last_observed_at = row.last_observed_at or _parse_datetime(content.get("last_observed_at"))
    review_after = row.review_after or _parse_datetime(content.get("review_after"))
    topic_tags = _normalize_topic_tags(row.topic_tags or content.get("topic_tags"), row.summary or "")
    scope = _normalize_scope(
        row.scope or content.get("scope"),
        row.memory_type or "general",
        content,
        row.summary or "",
        event_at,
        expires_at,
        topic_tags,
    )
    return {
        "id": str(row.id),
        "layer": row.layer,
        "memory_type": row.memory_type or "general",
        "summary": row.summary,
        "content": content,
        "scope": scope,
        "topic_tags": topic_tags,
        "event_at": _format_optional_datetime(event_at),
        "expires_at": _format_optional_datetime(expires_at),
        "confidence": row.confidence or 0,
        "observed_count": row.observed_count or 0,
        "last_observed_at": _format_optional_datetime(last_observed_at),
        "review_after": _format_optional_datetime(review_after),
        "user_confirmed": row.user_confirmed,
        "is_inference": row.is_inference,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "lifecycle": _memory_lifecycle(row.memory_type, content, expires_at),
        "is_expired": _is_expired_memory(row.memory_type, content, expires_at),
    }


def _sync_memory_metadata(content: dict, structured_fields: dict) -> dict:
    synced = dict(content or {})
    synced["scope"] = structured_fields.get("scope", DEFAULT_MEMORY_SCOPE)
    synced["topic_tags"] = structured_fields.get("topic_tags") or []
    return synced


def _normalize_memory_content(
    memory_type: str,
    content: dict,
    event_at: datetime | None = None,
    expires_at: datetime | None = None,
    source: str | None = None,
    scope: str | None = None,
    topic_tags: list[str] | None = None,
) -> dict:
    normalized = dict(content or {})
    if source and not normalized.get("source"):
        normalized["source"] = source
    normalized.setdefault("lifecycle", "active")

    if event_at:
        normalized["event_at"] = _format_datetime(event_at)
    if expires_at:
        normalized["expires_at"] = _format_datetime(expires_at)
    if scope:
        normalized["scope"] = scope
    if topic_tags is not None:
        normalized["topic_tags"] = topic_tags

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
    scope: str | None = None,
    topic_tags: list[str] | None = None,
) -> dict:
    content = content or {}
    parsed_event_at = _parse_datetime(event_at) or _parse_datetime(content.get("event_at"))
    parsed_expires_at = _parse_datetime(expires_at) or _parse_datetime(content.get("expires_at"))
    if memory_type == "event" and parsed_event_at and not parsed_expires_at:
        parsed_expires_at = parsed_event_at + timedelta(days=1)
    parsed_review_after = _parse_datetime(review_after) or _parse_datetime(content.get("review_after"))
    if memory_type == "event" and parsed_expires_at and not parsed_review_after:
        parsed_review_after = parsed_expires_at
    normalized_tags = _normalize_topic_tags(
        topic_tags if topic_tags is not None else content.get("topic_tags"),
        f"{summary}\n{json.dumps(content, ensure_ascii=False, default=str)}",
    )
    normalized_scope = _normalize_scope(
        scope or content.get("scope"),
        memory_type,
        content,
        summary,
        parsed_event_at,
        parsed_expires_at,
        normalized_tags,
    )

    return {
        "event_at": parsed_event_at,
        "expires_at": parsed_expires_at,
        "confidence": _parse_float(confidence if confidence is not None else content.get("confidence"), 0.0),
        "observed_count": _parse_int(observed_count if observed_count is not None else content.get("observed_count"), 0),
        "last_observed_at": _parse_datetime(last_observed_at) or _parse_datetime(content.get("last_observed_at")),
        "dedupe_key": (dedupe_key or content.get("dedupe_key") or _build_memory_dedupe_key(layer, memory_type, summary))[:160],
        "review_after": parsed_review_after,
        "scope": normalized_scope,
        "topic_tags": normalized_tags,
    }


def classify_query_topics(text: str) -> list[str]:
    return _infer_topic_tags(text or "")


def is_memory_relevant_to_query(
    memory: dict,
    query: str,
    query_topics: list[str] | None = None,
    semantic_score: float = 0.0,
) -> bool:
    return explain_memory_relevance(memory, query, query_topics, semantic_score)["kept"]


def explain_memory_relevance(
    memory: dict,
    query: str,
    query_topics: list[str] | None = None,
    semantic_score: float = 0.0,
) -> dict:
    if not (query or "").strip():
        return _memory_gate_decision(False, "empty_query")

    memory_type = memory.get("memory_type") or "general"
    if memory_type == "boundary":
        return _memory_gate_decision(False, "boundary_memory")
    if memory.get("needs_cleanup") or memory.get("is_expired"):
        return _memory_gate_decision(False, "expired_or_cleanup")

    scope = _normalize_scope(
        memory.get("scope"),
        memory_type,
        memory.get("content") or {},
        memory.get("summary") or "",
        _parse_datetime(memory.get("event_at")),
        _parse_datetime(memory.get("expires_at")),
        memory.get("topic_tags") or [],
    )
    memory_topics = set(_normalize_topic_tags(memory.get("topic_tags"), memory.get("summary") or ""))
    current_topics = set(query_topics or classify_query_topics(query))
    topic_overlap = bool(memory_topics and current_topics and memory_topics & current_topics)
    keyword_overlap = _keyword_overlap_count(query, memory.get("summary") or "")
    metadata = {
        "scope": scope,
        "memory_type": memory_type,
        "memory_topics": sorted(memory_topics),
        "query_topics": sorted(current_topics),
        "keyword_overlap": keyword_overlap,
        "semantic_score": round(float(semantic_score or 0), 4),
    }

    if topic_overlap:
        return _memory_gate_decision(True, "topic_overlap", metadata)

    if scope == "ephemeral":
        if keyword_overlap >= 2:
            return _memory_gate_decision(True, "keyword_overlap", metadata)
        if semantic_score >= 0.80:
            return _memory_gate_decision(True, "semantic_match", metadata)
        return _memory_gate_decision(False, "unrelated", metadata)
    if scope == "topic":
        if keyword_overlap >= 2:
            return _memory_gate_decision(True, "keyword_overlap", metadata)
        if semantic_score >= 0.76:
            return _memory_gate_decision(True, "semantic_match", metadata)
        return _memory_gate_decision(False, "unrelated", metadata)
    if scope == "session":
        if keyword_overlap >= 2:
            return _memory_gate_decision(True, "keyword_overlap", metadata)
        if semantic_score >= 0.78:
            return _memory_gate_decision(True, "semantic_match", metadata)
        return _memory_gate_decision(False, "unrelated", metadata)

    if keyword_overlap >= 1:
        return _memory_gate_decision(True, "keyword_overlap", metadata)
    if semantic_score >= 0.72:
        return _memory_gate_decision(True, "semantic_match", metadata)
    return _memory_gate_decision(False, "unrelated", metadata)


def _memory_gate_decision(kept: bool, reason: str, metadata: dict | None = None) -> dict:
    return {"kept": kept, "reason": reason, "metadata": metadata or {}}


def is_text_relevant_to_query(
    text: str,
    query: str,
    query_topics: list[str] | None = None,
) -> bool:
    return explain_text_relevance(text, query, query_topics)["kept"]


def explain_text_relevance(
    text: str,
    query: str,
    query_topics: list[str] | None = None,
) -> dict:
    if _asks_for_pending_topic(query):
        return _memory_gate_decision(True, "pending_topic_requested")
    text_topics = set(classify_query_topics(text or ""))
    current_topics = set(query_topics or classify_query_topics(query or ""))
    keyword_overlap = _keyword_overlap_count(query, text)
    metadata = {
        "text_topics": sorted(text_topics),
        "query_topics": sorted(current_topics),
        "keyword_overlap": keyword_overlap,
    }
    if text_topics and current_topics and text_topics & current_topics:
        return _memory_gate_decision(True, "topic_overlap", metadata)
    if keyword_overlap >= 2:
        return _memory_gate_decision(True, "keyword_overlap", metadata)
    return _memory_gate_decision(False, "unrelated", metadata)


def _memory_relevance_score(
    memory: dict,
    query: str,
    query_topics: list[str] | None = None,
    semantic_score: float = 0.0,
) -> float:
    memory_topics = set(_normalize_topic_tags(memory.get("topic_tags"), memory.get("summary") or ""))
    current_topics = set(query_topics or classify_query_topics(query))
    score = semantic_score
    if memory_topics and current_topics and memory_topics & current_topics:
        score += 0.6
    score += min(_keyword_overlap_count(query, memory.get("summary") or "") * 0.18, 0.54)
    if memory.get("scope") == "global":
        score += 0.08
    if memory.get("user_confirmed"):
        score += 0.08
    if memory.get("memory_type") == "event":
        score -= 0.05
    return score


def _normalize_scope(
    scope: str | None,
    memory_type: str | None,
    content: dict | None,
    summary: str,
    event_at: datetime | None,
    expires_at: datetime | None,
    topic_tags: list[str] | None,
) -> str:
    raw_scope = (scope or "").strip().lower()
    if raw_scope in MEMORY_SCOPES:
        return raw_scope

    content = content or {}
    if memory_type == "event" or event_at or expires_at or content.get("event_at") or content.get("expires_at"):
        return "ephemeral"
    if memory_type == "boundary":
        return "global"
    if memory_type in {"routine", "preference"} and topic_tags:
        return "topic"
    if topic_tags and memory_type in {"general", "insight"}:
        return "topic"
    return DEFAULT_MEMORY_SCOPE


def _normalize_topic_tags(tags, text: str = "") -> list[str]:
    normalized = []
    if isinstance(tags, list):
        for tag in tags:
            value = str(tag or "").strip().lower()
            if value in TOPIC_KEYWORDS and value not in normalized:
                normalized.append(value)
    inferred = _infer_topic_tags(text)
    for tag in inferred:
        if tag not in normalized:
            normalized.append(tag)
    return normalized[:8]


def _infer_topic_tags(text: str) -> list[str]:
    text_lower = (text or "").lower()
    tags = []
    for topic, keywords in TOPIC_KEYWORDS.items():
        if any(keyword.lower() in text_lower for keyword in keywords):
            tags.append(topic)
    return tags


def _keyword_overlap_count(query: str, text: str) -> int:
    query_keywords = _known_keywords_in_text(query)
    text_keywords = _known_keywords_in_text(text)
    return len(query_keywords & text_keywords)


def _known_keywords_in_text(text: str) -> set[str]:
    text_lower = (text or "").lower()
    keywords = set()
    for values in TOPIC_KEYWORDS.values():
        for keyword in values:
            value = keyword.lower()
            if value in text_lower:
                keywords.add(value)
    for token in re.findall(r"[a-zA-Z0-9_]{2,}", text_lower):
        keywords.add(token)
    return keywords


def _asks_for_pending_topic(query: str) -> bool:
    return any(word in (query or "") for word in ("继续", "上次", "之前", "刚才", "接着"))


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
    structured_fields = _derive_memory_fields(
        layer="co_created",
        memory_type=memory_type,
        summary=summary,
        content=content,
    )
    content = _sync_memory_metadata(content, structured_fields)

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
    scope: str | None = None,
    topic_tags: list[str] | None = None,
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
        scope=scope,
        topic_tags=topic_tags,
    )
    content = _sync_memory_metadata(content or {}, structured_fields)
    item = MemoryItem(
        user_id=user_id,
        layer=layer,
        memory_type=memory_type,
        summary=summary,
        content=content,
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


async def _resolve_explicit_memory_replacements(user_id: str, new_item: MemoryItem, db: AsyncSession) -> int:
    """同步处理用户明确表达的取消/替换，避免旧共建记忆继续展示。"""
    source_text = _replacement_source_text(new_item)
    cancelled_terms = _extract_cancelled_topics(source_text)
    if not cancelled_terms:
        return 0

    result = await db.execute(
        select(MemoryItem)
        .where(
            MemoryItem.user_id == user_id,
            MemoryItem.layer == "co_created",
            MemoryItem.status == "active",
            MemoryItem.user_confirmed.is_(True),
            MemoryItem.id != new_item.id,
        )
        .order_by(MemoryItem.updated_at.desc())
        .limit(80)
    )

    now = datetime.now(timezone.utc)
    superseded_count = 0
    for old_item in result.scalars().all():
        if not _should_supersede_memory(old_item, cancelled_terms, source_text):
            continue
        old_content = dict(old_item.content or {})
        old_content["lifecycle"] = "superseded"
        old_content["superseded_by"] = str(new_item.id)
        old_content["superseded_reason"] = "explicit_replacement"
        old_content["superseded_terms"] = sorted(cancelled_terms)
        old_content["superseded_at"] = _format_datetime(now)
        old_item.content = old_content
        old_item.status = "deleted"
        superseded_count += 1

    if superseded_count:
        new_content = dict(new_item.content or {})
        new_content["replacement"] = {
            "cancelled_terms": sorted(cancelled_terms),
            "superseded_count": superseded_count,
            "resolved_at": _format_datetime(now),
        }
        new_item.content = new_content
        await db.commit()
        await db.refresh(new_item)

    return superseded_count


def _replacement_source_text(item: MemoryItem) -> str:
    content = item.content or {}
    pieces = [
        item.summary or "",
        str(content.get("source_message") or ""),
        str(content.get("source_reply") or ""),
    ]
    return "\n".join(piece for piece in pieces if piece)


def _extract_forbidden_request_terms(text: str, patterns: tuple[str, ...]) -> set[str]:
    terms: set[str] = set()
    for pattern in patterns:
        for match in re.finditer(pattern, text or "", flags=re.IGNORECASE):
            if _is_negated_boundary_action(text or "", match.start()):
                continue
            terms.update(_extract_forbidden_terms(match.group("topic")))
    return terms


def _is_negated_boundary_action(text: str, start: int) -> bool:
    prefix = text[max(0, start - 4):start]
    return bool(re.search(r"(不要|别|不能|不要再|别再)$", prefix))


def _extract_forbidden_terms(text: str) -> set[str]:
    compacted = _compact_forbidden_text(text)
    if not compacted:
        return set()

    terms = set(_extract_topic_terms(compacted))
    if not terms and _is_useful_forbidden_term(compacted):
        terms.add(compacted)
    return {_normalize_match_text(term) for term in terms if _is_useful_forbidden_term(term)}


def _compact_forbidden_text(text: str) -> str:
    compacted = re.sub(r"\s+", "", text or "")
    compacted = re.sub(r"^(关于|有关|对于|对|把|将|这次|当前|以后|之后|后面|接下来)", "", compacted)
    compacted = re.sub(r"(这个话题|那个话题|这件事|那件事|这事|那事|的话题)$", "", compacted)
    compacted = compacted.strip("了啦吧哦呀呢啊吗嘛~～ ，。！？；、")
    return compacted


def _is_useful_forbidden_term(term: str) -> bool:
    normalized = _normalize_match_text(term)
    if not normalized or normalized in VAGUE_FORBIDDEN_TERMS:
        return False
    if len(normalized) < 2 or len(normalized) > 24:
        return False
    return not re.fullmatch(r"[^\w\u4e00-\u9fff]+", normalized)


def _forbidden_item_matches_terms(item: ForbiddenTopic, terms: set[str]) -> bool:
    item_terms = forbidden_topics_to_terms([item])
    for term in terms:
        if term in item_terms:
            return True
        if any(term in item_term or item_term in term for item_term in item_terms):
            return True
    return False


def _normalize_match_text(text: str) -> str:
    return re.sub(r"\s+", "", text or "").lower()


def _stringify_forbidden_text(text: str | dict | None) -> str:
    if text is None:
        return ""
    if isinstance(text, dict):
        return json.dumps(text, ensure_ascii=False)
    return str(text)


def _memory_dict_text(data: dict) -> str:
    pieces = [
        str(data.get("summary") or ""),
        _stringify_forbidden_text(data.get("content") or {}),
    ]
    return "\n".join(piece for piece in pieces if piece)


def _extract_cancelled_topics(text: str) -> set[str]:
    if not _has_replacement_intent(text):
        return set()

    spans: list[str] = []
    for pattern in (
        r"(?:取消|停止|暂停|放弃|停掉|不再|别再|不用|不要|先不)([^，。！？；、\n]{1,24})",
        r"([^，。！？；、\n]{1,24}?)(?:取消了?|停止了?|暂停了?|放弃了?|停掉了?|不做了?|不去了?|不用了?|不要了?)",
        r"(?:把|将)?([^，。！？；、\n]{1,24}?)(?:改为|改成|换成|替换成|改去|改做)",
    ):
        spans.extend(match.group(1) for match in re.finditer(pattern, text))

    terms: set[str] = set()
    for span in spans:
        terms.update(_extract_topic_terms(span))
    return {term for term in terms if len(term) >= 2}


def _extract_topic_terms(phrase: str) -> set[str]:
    phrase = re.sub(r"\s+", "", phrase or "")
    if not phrase:
        return set()

    known_terms = (
        "跑步",
        "健身",
        "运动",
        "训练",
        "面试",
        "考试",
        "会议",
        "求职",
        "简历",
        "香蕉",
        "橘子",
        "水果",
        "早睡",
        "熬夜",
        "睡眠",
        "学习",
        "项目",
        "代码",
        "提醒",
    )
    terms = {term for term in known_terms if term in phrase}
    if terms:
        return terms

    cleaned = phrase
    for word in (
        "用户",
        "自己",
        "我的",
        "我",
        "原来",
        "之前",
        "当前",
        "现在",
        "今天",
        "明天",
        "后天",
        "之后",
        "以后",
        "这次",
        "计划",
        "安排",
        "习惯",
        "目标",
        "需要",
        "准备",
        "已经",
        "还是",
        "那个",
        "这个",
        "一些",
        "的",
        "了",
        "去",
        "做",
        "要",
        "会",
    ):
        cleaned = cleaned.replace(word, "")
    cleaned = cleaned.strip("，。！？；、 ")
    if 2 <= len(cleaned) <= 12:
        return {cleaned}
    return set()


def _has_replacement_intent(text: str) -> bool:
    return bool(re.search(r"(取消|停止|暂停|放弃|停掉|不再|别再|不用|不要|不做了|不去了|改为|改成|换成|替换成|改去|改做)", text or ""))


def _should_supersede_memory(old_item: MemoryItem, cancelled_terms: set[str], source_text: str) -> bool:
    old_text = _memory_text(old_item)
    matched_terms = [term for term in cancelled_terms if term and term in old_text]
    if not matched_terms:
        return False

    old_type = old_item.memory_type or "general"
    if old_type == "boundary":
        return False

    for term in matched_terms:
        if _is_negative_constraint_about_term(old_text, term):
            continue
        if old_type in {"event", "routine"}:
            return True
        if old_type == "preference":
            return _looks_like_activity_or_plan_memory(old_text, term) or _is_preference_reversal(source_text, term)
        if old_type in {"general", "profile", "insight"}:
            return _looks_like_activity_or_plan_memory(old_text, term)
    return False


def _memory_text(item: MemoryItem) -> str:
    return "\n".join([
        item.summary or "",
        json.dumps(item.content or {}, ensure_ascii=False),
    ])


def _is_negative_constraint_about_term(text: str, term: str) -> bool:
    for part in re.split(r"[，。！？；、\n]", text or ""):
        if term not in part:
            continue
        if any(word in part for word in ("不会", "不能", "不在同一天", "不同时", "不要同时", "不一起")):
            return True
    return False


def _looks_like_activity_or_plan_memory(text: str, term: str) -> bool:
    if term not in text:
        return False
    markers = (
        "计划",
        "安排",
        "准备",
        "打算",
        "目标",
        "明天",
        "今天",
        "后天",
        "每天",
        "每周",
        "每次",
        "经常",
        "常常",
        "习惯",
        "固定",
        "围绕",
        "公里",
        "喜欢",
    )
    return any(marker in text for marker in markers)


def _is_preference_reversal(text: str, term: str) -> bool:
    if term not in text:
        return False
    return any(word in text for word in ("不喜欢", "讨厌", "不想", "不再喜欢", "不爱", "不要"))


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
