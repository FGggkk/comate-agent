from functools import lru_cache
from pathlib import Path

from app.graph.state import ChatState
from app.graph.schemas import text_chunk_event, status_event
from app.services.model_gateway import gateway


async def llm_call_node(state: ChatState):
    """Step 5: 调用模型生成回复"""
    events = [status_event("thinking", "伴行正在思考...")]

    boundary_reply = _boundary_update_reply(state)
    if boundary_reply:
        state.reply = boundary_reply
        events.append(text_chunk_event(boundary_reply))
        return events

    # 拼接 Prompt：记忆顺序为默契层 -> 共建层 -> 当前会话。
    system_parts = [state.compiled_soul, _load_memory_usage_prompt()]

    if state.forbidden_topics:
        forbidden_line = "、".join(
            topic["topic"] for topic in state.forbidden_topics[:8] if topic.get("topic")
        )
        if forbidden_line:
            system_parts.append(
                "\n# 禁区话题边界\n"
                f"用户已设置这些禁区话题：{forbidden_line}。\n"
                "不要主动提及、展开、联想、追问或复述这些禁区话题；"
                "即使用户询问禁区清单，也只说明存在边界设置，不要倒出具体内容。"
            )

    # 注入默契画像
    if state.tacit_context:
        system_parts.append(f"\n# 默契层人物理解\n{state.tacit_context}")

    # 注入已通过当前问题匹配的共建事实
    if state.memories:
        memory_context = "\n".join(
            f"- {m['summary']}" for m in state.memories
        )
        system_parts.append(f"\n# 与当前问题匹配的共建事实\n{memory_context}")

    # 注入当前会话上下文
    if state.session_context:
        system_parts.append(f"\n# 当前会话上下文\n{state.session_context}")

    system = "\n".join(system_parts)

    prompt = state.message

    try:
        full_reply = ""
        async for chunk in gateway.stream(prompt, system=system):
            full_reply += chunk
            events.append(text_chunk_event(chunk))

        state.reply = full_reply
    except Exception as e:
        state.error = f"模型调用失败: {str(e)}"
        fallback = "嗯，我在听。能再多说一点吗？"
        state.reply = fallback
        events.append(text_chunk_event(fallback))

    return events


def _boundary_update_reply(state: ChatState) -> str:
    updates = state.forbidden_updates or {}
    if updates.get("added"):
        return "收到，我会记住这个边界，之后不主动触碰。我们换个舒服点的话题。"
    if updates.get("removed"):
        return "收到，这个边界已经解除，之后会按你当前的意愿来。"
    if state.forbidden_query_blocked:
        return "这个话题我先不展开。我们可以换个你更舒服的方向聊，或者我陪你整理一下当下的心情。"
    return ""


@lru_cache(maxsize=1)
def _load_memory_usage_prompt() -> str:
    prompt_path = Path(__file__).resolve().parents[2] / "prompts" / "chat_memory_usage.md"
    try:
        return prompt_path.read_text(encoding="utf-8").strip()
    except OSError:
        return "只使用与当前用户问题直接相关的记忆，不要主动提及无关的其他会话事项。"
