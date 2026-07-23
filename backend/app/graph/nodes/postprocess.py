from app.graph.state import ChatState
from app.services.memory_service import extract_candidates, update_anchors


async def postprocess_node(state: ChatState, db):
    """Step 7: 异步后处理（不阻塞 SSE）"""
    # 抽取记忆候选
    await extract_candidates(state.user_id, state.message, state.reply, db=db)

    # 更新未完待续锚点
    await update_anchors(state.user_id, state.message, state.reply, db=db)

    return []  # 不输出事件
