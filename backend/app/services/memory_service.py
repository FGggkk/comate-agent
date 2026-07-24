import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import func as sa_func

from sqlalchemy import text as sa_text

from app.models.memory import ForbiddenTopic, MemoryItem, PendingAnchor
from app.services.embedding_service import get_embedding


async def search(
    user_id: str,
    query: str,
    top_k: int = 5,
    db: AsyncSession = None,
) -> list[dict]:
    """语义检索 + 关键词兜底 + 禁区过滤"""
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
              AND embedding IS NOT NULL
            ORDER BY embedding <=> CAST(:query_vec AS vector)
            LIMIT :top_k
        """)
        result = await db.execute(sql, {"query_vec": vec_literal, "user_id": user_id, "top_k": top_k})
        rows = result.fetchall()
        results = []
        for row in rows:
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
                "score": float(row.score) if row.score else 0,
            })
        if results:
            return results[:top_k]

    # 2. 兜底：ILIKE 关键词模糊匹配
    result = await db.execute(
        select(MemoryItem).where(
            MemoryItem.user_id == user_id,
            MemoryItem.status == "active",
        ).order_by(MemoryItem.created_at.desc()).limit(50)
    )
    items = result.scalars().all()

    keywords = set(query.lower().split())
    scored = []
    for item in items:
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


async def update_item(item_id: str, data: dict, db: AsyncSession = None) -> dict:
    await db.execute(
        update(MemoryItem).where(MemoryItem.id == item_id).values(**data)
    )
    await db.commit()
    return {"success": True}


async def delete_item(item_id: str, db: AsyncSession = None) -> dict:
    await db.execute(
        update(MemoryItem).where(MemoryItem.id == item_id).values(status="deleted")
    )
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


async def remove_forbidden(topic_id: str, db: AsyncSession = None) -> dict:
    await db.execute(delete(ForbiddenTopic).where(ForbiddenTopic.id == topic_id))
    await db.commit()
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


async def fulfill_anchor(anchor_id: str, db: AsyncSession = None) -> dict:
    await db.execute(
        update(PendingAnchor).where(PendingAnchor.id == anchor_id).values(status="fulfilled")
    )
    await db.commit()
    return {"success": True}


def _item_to_dict(item: MemoryItem) -> dict:
    return {
        "id": str(item.id),
        "layer": item.layer,
        "memory_type": item.memory_type,
        "summary": item.summary,
        "content": item.content,
        "user_confirmed": item.user_confirmed,
        "is_inference": item.is_inference,
        "created_at": item.created_at.isoformat() if item.created_at else None,
    }


async def extract_candidates(user_id: str, message: str, reply: str, db: AsyncSession = None) -> list[dict]:
    """对话后用 LLM 提取记忆点，生成 embedding 并保存到数据库"""
    # 用 LLM 提取
    summary = await _extract_memory_summary(message, reply)
    if not summary:
        return []

    # 保存到数据库 + 生成 embedding
    await add_with_embedding(user_id, "co_created", summary, {
        "source_message": message[:200],
        "source_reply": reply[:200],
        "requires_confirmation": True,
    }, db=db)

    return [{"summary": summary, "layer": "co_created"}]


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
) -> MemoryItem | None:
    """保存记忆并异步生成 embedding"""
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
