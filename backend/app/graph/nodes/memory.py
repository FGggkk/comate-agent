from app.config.settings import get_settings
from app.graph.state import ChatState
from app.graph.schemas import memory_card_event, status_event
from app.services.conversation_context_service import get_current_session_context
from app.services.memory_gate_service import log_gate_trace
from app.services.memory_service import (
    classify_query_topics,
    get_forbidden,
    is_forbidden_text,
    memory_search_limit,
    search,
    sync_forbidden_topics_from_message,
)
from app.services.tacit_profile_service import get_tacit_context


async def memory_node(state: ChatState, db):
    """Step 3: 分层读取记忆。

    顺序固定为：默契层人物理解 -> 当前问题匹配的共建事实 -> 当前会话上下文。
    """
    events = [status_event("memory", "正在回忆我们的聊天记录")]
    state.memory_gate_trace = []
    state.query_topics = classify_query_topics(state.message)

    # 0. 禁区边界：先同步用户当前消息里的明示边界，再读取任何记忆。
    try:
        state.forbidden_updates = await sync_forbidden_topics_from_message(state.user_id, state.message, db)
    except Exception as e:
        print(f"[memory] 禁区话题同步失败: {e}")
        state.forbidden_updates = {}

    forbidden_topics = await get_forbidden(state.user_id, db)
    state.forbidden_topics = [{"id": str(f.id), "topic": f.topic_summary} for f in forbidden_topics]
    state.forbidden_query_blocked = is_forbidden_text(state.message, forbidden_topics)

    # 1. 默契层：只作为人物理解和陪伴方式参考。
    try:
        state.tacit_context = await get_tacit_context(
            state.user_id,
            db,
            query=state.message,
            forbidden_topics=forbidden_topics,
            gate_trace=state.memory_gate_trace,
        )
    except Exception as e:
        print(f"[memory] 默契画像读取失败: {e}")
        state.tacit_context = ""

    # 2. 共建层：只取和当前问题相关的事实。
    memory_limit = memory_search_limit(state.message)
    memories = await search(
        state.user_id,
        state.message,
        top_k=memory_limit,
        db=db,
        gate_trace=state.memory_gate_trace,
    )
    state.memories = memories

    # 思考过程里展示本轮实际注入的相关共建线索。
    for m in memories:
        card = memory_card_event(m["summary"], m["layer"])
        if card:
            events.append(card)

    # 3. 当前会话：只读取当前 session，不跨会话拼接聊天记录。
    state.session_context = await get_current_session_context(
        state.user_id,
        state.conversation_id,
        db,
        query=state.message,
        query_topics=state.query_topics,
        forbidden_topics=forbidden_topics,
        gate_trace=state.memory_gate_trace,
    )

    state.pending_anchors = []

    settings = get_settings()
    log_gate_trace(
        state.memory_gate_trace,
        enabled=settings.debug,
        user_id=state.user_id,
        query=state.message,
        query_topics=state.query_topics,
    )

    return events
