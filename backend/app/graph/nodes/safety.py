from app.graph.state import ChatState
from app.graph.schemas import status_event


SENSITIVE_WORDS = ["自杀", "自残", "跳楼", "杀了我", "活不下去"]


async def safety_input_node(state: ChatState):
    """Step 1: 输入安全检查"""
    for word in SENSITIVE_WORDS:
        if word in state.message:
            state.error = "检测到敏感内容，请换个话题聊聊"
            return [status_event("safety", "安全检测")]

    return [status_event("safety", "安全检查通过")]
