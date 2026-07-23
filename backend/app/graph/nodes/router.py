from app.graph.state import ChatState
from app.graph.schemas import status_event


INTERVIEW_KEYWORDS = ["面试", "求职", "岗位", "简历", "offer", "招聘", "找工作", "跳槽"]


async def router_node(state: ChatState):
    """Step 4: 意图路由"""
    for kw in INTERVIEW_KEYWORDS:
        if kw in state.message:
            state.intent = "interview"
            return [status_event("route", "检测到面试相关话题")]

    state.intent = "daily"
    return [status_event("route", "日常陪伴模式")]
