from app.graph.state import ChatState
from app.services.memory_service import extract_candidates
from app.services.reminder_service import parse_reminder_request


async def postprocess_node(state: ChatState, db):
    """Step 7: 后处理，生成可由用户确认的记忆候选"""
    if (
        state.forbidden_query_blocked
        or state.forbidden_updates.get("added")
        or state.forbidden_updates.get("removed")
    ):
        state.memory_candidates = []
    elif parse_reminder_request(state.message):
        state.memory_candidates = []
    else:
        state.memory_candidates = await extract_candidates(
            state.user_id,
            state.message,
            state.reply,
            db=db,
            forbidden_topics=state.forbidden_topics,
        )

    return []  # 不输出事件
