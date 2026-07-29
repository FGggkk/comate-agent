from app.graph.state import ChatState
from app.graph.schemas import action_buttons_event


async def actions_node(state: ChatState):
    """Step 8: 根据意图生成快捷操作按钮"""
    prompt = None
    candidate_summary = None

    if (
        state.forbidden_query_blocked
        or state.forbidden_updates.get("added")
        or state.forbidden_updates.get("removed")
    ):
        state.actions = []
        return []

    if state.memory_candidates:
        candidate = state.memory_candidates[0]
        prompt = "检测到需要关注的内容，请问是否需要记忆？"
        candidate_summary = candidate.get("summary")
        buttons = [
            {"label": "需要，记住", "action": "confirm_memory_candidate", "candidate": candidate},
            {"label": "暂时不用", "action": "dismiss_memory_candidate"},
        ]
        state.actions = buttons
        return [action_buttons_event(buttons, prompt=prompt, candidate_summary=candidate_summary)]

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
