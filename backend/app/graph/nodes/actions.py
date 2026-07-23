from app.graph.state import ChatState
from app.graph.schemas import action_buttons_event


async def actions_node(state: ChatState):
    """Step 8: 根据意图生成快捷操作按钮"""
    if state.intent == "interview":
        buttons = [
            {"label": "开始模拟面试", "action": "start_interview"},
            {"label": "查看面经技巧", "action": "interview_tips"},
        ]
    else:
        buttons = [
            {"label": "查看记忆", "action": "view_memory"},
            {"label": "设定提醒", "action": "set_reminder"},
        ]

    state.actions = buttons
    return [action_buttons_event(buttons)]
