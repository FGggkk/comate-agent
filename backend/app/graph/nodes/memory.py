from app.graph.state import ChatState
from app.graph.schemas import memory_card_event, status_event
from app.services.conversation_context_service import get_current_session_context
from app.services.memory_service import classify_query_topics, get_anchors, is_text_relevant_to_query, search
from app.services.tacit_profile_service import get_tacit_context


async def memory_node(state: ChatState, db):
    """Step 3: 分层读取记忆。

    顺序固定为：默契层人物理解 -> 当前问题匹配的共建事实 -> 当前会话上下文。
    """
    events = [status_event("memory", "正在回忆我们的聊天记录")]
    state.query_topics = classify_query_topics(state.message)

    # 1. 默契层：只作为人物理解和陪伴方式参考。
    try:
        state.tacit_context = await get_tacit_context(state.user_id, db, query=state.message)
    except Exception as e:
        print(f"[memory] 默契画像读取失败: {e}")
        state.tacit_context = ""

    # 2. 共建层：只取和当前问题相关的事实。
    memories = await search(state.user_id, state.message, top_k=3, db=db)
    state.memories = memories

    # 记忆卡片（最多 2 条）
    for m in memories[:2]:
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
    )

    # 读取未完待续锚点
    anchors = await get_anchors(state.user_id, db=db)
    state.pending_anchors = [
        {"id": str(a.id), "topic": a.topic_summary}
        for a in anchors
        if is_text_relevant_to_query(a.topic_summary, state.message, state.query_topics)
    ]
    # 如果有锚点，也作为卡片展示
    if state.pending_anchors:
        for a in state.pending_anchors[:1]:
            card = memory_card_event(f"上次提到: {a['topic']}", "anchor")
            if card:
                events.append(card)

    return events
