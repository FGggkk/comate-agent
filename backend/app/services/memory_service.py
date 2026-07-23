import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.memory import ForbiddenTopic, MemoryItem, PendingAnchor


async def search(
    user_id: str,
    query: str,
    top_k: int = 5,
    db: AsyncSession = None,
) -> list[dict]:
    """混合检索记忆 + 禁区过滤"""
    result = await db.execute(
        select(MemoryItem).where(
            MemoryItem.user_id == user_id,
            MemoryItem.status == "active",
        ).order_by(MemoryItem.created_at.desc()).limit(top_k * 3)
    )
    items = result.scalars().all()

    # 关键词简单评分
    keywords = set(query.lower().split())
    scored = []
    for item in items:
        score = 0.0
        summary_lower = item.summary.lower()
        for kw in keywords:
            if kw in summary_lower:
                score += 0.3
        if item.user_confirmed:
            score += 0.2
        if item.layer == "co_created":
            score += 0.1
        scored.append((score, item))

    scored.sort(key=lambda x: x[0], reverse=True)

    # 获取禁区话题
    forbidden = await get_forbidden(user_id, db)
    forbidden_words = {f.topic_summary.lower() for f in forbidden}

    results = []
    for score, item in scored[:top_k]:
        # 禁区过滤
        if any(fw in item.summary.lower() for fw in forbidden_words):
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
    """对话后抽取记忆候选（简化版关键词匹配）"""
    candidates = []
    keywords = {
        "喜欢": ("preference", "喜欢"),
        "目标": ("goal", "目标"),
        "打算": ("goal", "打算"),
        "下个月": ("goal", "下个月"),
        "下周": ("goal", "下周"),
        "工作": ("identity", "工作"),
        "学校": ("identity", "学校"),
    }

    for kw, (mtype, label) in keywords.items():
        if kw in message:
            candidates.append({
                "layer": "co_created",
                "memory_type": mtype,
                "summary": message,
                "requires_confirmation": True,
            })
            break

    return candidates


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
