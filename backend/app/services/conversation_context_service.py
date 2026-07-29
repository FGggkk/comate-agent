import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Message, Session
from app.services.memory_service import classify_query_topics, is_forbidden_text


TOPIC_NOISE_KEYWORDS = {
    "interview": ("面试", "求职", "简历", "offer", "岗位", "招聘", "hr", "HR", "技术岗"),
    "work": ("项目", "代码", "分支", "提交", "pr", "PR", "bug", "需求", "上线", "开发"),
    "emotion": ("焦虑", "压力", "烦", "累", "紧张", "情绪", "崩", "难受", "开心", "低落"),
    "finance": ("记账", "账单", "预算", "消费", "花销", "收入", "支出", "省钱"),
    "travel": ("旅游", "旅行", "行程", "酒店", "机票", "路线", "景点"),
    "study": ("学习", "考试", "备考", "刷题", "课程", "复习", "论文"),
    "sleep": ("睡眠", "作息", "早睡", "熬夜", "失眠", "起床"),
}


async def get_current_session_context(
    user_id: str,
    session_id: str | None,
    db: AsyncSession,
    query: str | None = None,
    query_topics: list[str] | None = None,
    forbidden_topics: list | None = None,
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
    current_topics = query_topics if query_topics is not None else classify_query_topics(query or "")
    lines = []
    for message in messages:
        content = _filter_message_for_query(message.content, query or "", current_topics, forbidden_topics)
        if not content:
            continue
        speaker = "用户" if message.role == "user" else "伴行"
        lines.append(f"{speaker}: {content}")
    return "\n".join(lines)


def _compact_text(text: str, limit: int) -> str:
    compacted = " ".join((text or "").split())
    return compacted[:limit]


def _filter_message_for_query(
    text: str,
    query: str,
    query_topics: list[str],
    forbidden_topics: list | None = None,
) -> str:
    content = _compact_text(text, 600)
    if not content:
        return ""

    kept = []
    for chunk in _split_context_chunks(content):
        compacted = _compact_text(chunk, 140)
        if not compacted:
            continue
        if is_forbidden_text(compacted, forbidden_topics):
            continue
        if not query_topics:
            kept.append(compacted)
            if len(kept) >= 3:
                break
            continue
        if _has_off_topic_noise(compacted, query_topics):
            continue
        if _has_topic_overlap(compacted, query_topics):
            kept.append(compacted)
        if len(kept) >= 3:
            break

    return _compact_text("，".join(kept), 300)


def _split_context_chunks(text: str) -> list[str]:
    chunks = re.split(r"[。！？!?；;\n\r]+|[，,、]\s*", text or "")
    return [chunk.strip() for chunk in chunks if chunk and chunk.strip()]


def _has_off_topic_noise(text: str, query_topics: list[str]) -> bool:
    current_topics = set(query_topics or [])
    for topic, keywords in TOPIC_NOISE_KEYWORDS.items():
        if topic in current_topics:
            continue
        lowered = text.lower()
        if any(keyword.lower() in lowered for keyword in keywords):
            return True
    return False


def _has_topic_overlap(text: str, query_topics: list[str]) -> bool:
    text_topics = set(classify_query_topics(text or ""))
    current_topics = set(query_topics or [])
    return bool(text_topics and current_topics and text_topics & current_topics)
