from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Message, Session


async def get_current_session_context(
    user_id: str,
    session_id: str | None,
    db: AsyncSession,
    limit: int = 8,
) -> str:
    if not session_id:
        return ""

    session_result = await db.execute(
        select(Session.id).where(Session.id == session_id, Session.user_id == user_id)
    )
    if not session_result.scalar_one_or_none():
        return ""

    result = await db.execute(
        select(Message)
        .where(Message.session_id == session_id, Message.msg_type == "text")
        .order_by(Message.created_at.desc())
        .limit(limit)
    )
    messages = list(reversed(result.scalars().all()))
    lines = []
    for message in messages:
        content = _compact_text(message.content, 300)
        if not content:
            continue
        speaker = "用户" if message.role == "user" else "伴行"
        lines.append(f"{speaker}: {content}")
    return "\n".join(lines)


def _compact_text(text: str, limit: int) -> str:
    compacted = " ".join((text or "").split())
    return compacted[:limit]
