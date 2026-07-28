import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import text as sa_text

from app.db.session import async_session_factory
from app.models.memory import ForbiddenTopic, MemoryItem, PendingAnchor
from app.services.embedding_service import get_embedding


CHAT_MEMORY_LAYERS = ("co_created", "tacit")
ALLOWED_MEMORY_TYPES = {
    "general",
    "preference",
    "profile",
    "event",
    "routine",
    "boundary",
    "insight",
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
                   user_confirmed, is_inference, created_at,
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
            if not _is_available_for_chat(row.layer, row.user_confirmed, row.memory_type, row.content):
                continue
            # 禁区过滤
            summary_lower = (row.summary or "").lower()
            if any(fw in summary_lower for fw in forbidden_words):
                continue
            results.append({
                "id": str(row.id),
                "layer": row.layer,
                "memory_type": row.memory_type or "general",
                "summary": row.summary,
                "content": row.content,
                "user_confirmed": row.user_confirmed,
                "is_inference": row.is_inference,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "lifecycle": _memory_lifecycle(row.memory_type, row.content),
                "is_expired": _is_expired_memory(row.memory_type, row.content),
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
    )
    return {"success": True, "data": _item_to_dict(item), "message": "ok"}


async def _get_existing_active_memory(
    user_id: str,
    layer: str,
    summary: str,
    memory_type: str,
    db: AsyncSession,
) -> MemoryItem | None:
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
) -> MemoryItem:
    item = MemoryItem(
        user_id=user_id,
        layer=layer,
        summary=summary,
        content=content or {},
        source_type="user_input",
        user_confirmed=(layer != "tacit"),
        is_inference=(layer == "tacit"),
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


async def update_item(user_id: str, item_id: str, data: dict, db: AsyncSession = None) -> dict:
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
        item.content = _normalize_memory_content(
            memory_type=data["memory_type"],
            content=item.content or {},
            source=(item.content or {}).get("source", item.source_type),
        )

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
    return {
        "id": str(item.id),
        "layer": item.layer,
        "memory_type": item.memory_type or "general",
        "summary": item.summary,
        "content": content,
        "event_at": content.get("event_at"),
        "expires_at": content.get("expires_at"),
        "lifecycle": _memory_lifecycle(item.memory_type, content),
        "is_expired": _is_expired_memory(item.memory_type, content),
        "needs_cleanup": _needs_cleanup(item.memory_type, content),
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


def _format_datetime(value: datetime | str) -> str:
    if isinstance(value, str):
        parsed = _parse_datetime(value)
        return parsed.isoformat() if parsed else value
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


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


def _memory_lifecycle(memory_type: str | None, content: dict | None) -> str:
    content = content or {}
    lifecycle = content.get("lifecycle") or "active"
    if memory_type == "event" and lifecycle == "active" and _is_expired_memory(memory_type, content):
        return "expired"
    return lifecycle


def _is_expired_memory(memory_type: str | None, content: dict | None) -> bool:
    if memory_type != "event":
        return False
    expires_at = _parse_datetime((content or {}).get("expires_at"))
    if not expires_at:
        return False
    return expires_at <= datetime.now(timezone.utc)


def _needs_cleanup(memory_type: str | None, content: dict | None) -> bool:
    return memory_type == "event" and _memory_lifecycle(memory_type, content) == "expired"


def _is_item_available_for_chat(item: MemoryItem) -> bool:
    return _is_available_for_chat(item.layer, item.user_confirmed, item.memory_type, item.content)


def _is_available_for_chat(
    layer: str,
    user_confirmed: bool,
    memory_type: str | None,
    content: dict | None,
) -> bool:
    if layer not in CHAT_MEMORY_LAYERS:
        return False
    if not user_confirmed:
        return False
    if _needs_cleanup(memory_type, content):
        return False
    if (content or {}).get("lifecycle") in {"dismissed", "archived"}:
        return False
    return True


async def extract_candidates(user_id: str, message: str, reply: str, db: AsyncSession = None) -> list[dict]:
    """对话后用 LLM 提取记忆候选，等待用户确认后再保存。"""
    summary = await _extract_memory_summary(message, reply)
    if not summary:
        return []

    return [{
        "summary": summary,
        "layer": "co_created",
        "memory_type": _guess_memory_type(summary),
        "content": {
            "source_message": message[:200],
            "source_reply": reply[:200],
            "source": "model_candidate",
        },
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
) -> MemoryItem | None:
    """保存记忆并异步生成 embedding"""
    if user_confirmed is None:
        user_confirmed = (layer != "tacit")
    item = MemoryItem(
        user_id=user_id,
        layer=layer,
        memory_type=memory_type,
        summary=summary,
        content=content or {},
        source_type=source_type,
        user_confirmed=user_confirmed,
        is_inference=(layer == "tacit"),
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
