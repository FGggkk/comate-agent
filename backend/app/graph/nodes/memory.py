from app.graph.state import ChatState
from app.graph.schemas import memory_card_event, status_event
from app.services.memory_service import get_anchors, search
from app.services.tacit_profile_service import get_tacit_context


async def memory_node(state: ChatState, db):
    """Step 3: 读取相关记忆 + 未完待续锚点"""
    events = [status_event("memory", "正在回忆我们的聊天记录")]

    # 语义检索记忆
    memories = await search(state.user_id, state.message, top_k=3, db=db)
    state.memories = memories

    try:
        state.tacit_context = await get_tacit_context(state.user_id, db)
    except Exception as e:
        print(f"[memory] 默契画像读取失败: {e}")
        state.tacit_context = ""

    # 记忆卡片（最多 2 条）
    for m in memories[:2]:
        card = memory_card_event(m["summary"], m["layer"])
        if card:
            events.append(card)

    # 读取未完待续锚点
    anchors = await get_anchors(state.user_id, db=db)
    state.pending_anchors = [
        {"id": str(a.id), "topic": a.topic_summary}
        for a in anchors
    ]
    # 如果有锚点，也作为卡片展示
    if state.pending_anchors:
        for a in state.pending_anchors[:1]:
            card = memory_card_event(f"上次提到: {a['topic']}", "anchor")
            if card:
                events.append(card)

    return events
