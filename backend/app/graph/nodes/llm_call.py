from functools import lru_cache
from pathlib import Path

from app.graph.state import ChatState
from app.graph.schemas import text_chunk_event, status_event
from app.services.model_gateway import gateway


async def llm_call_node(state: ChatState):
    """Step 5: 调用模型生成回复"""
    events = [status_event("thinking", "伴行正在思考...")]

    # 拼接 Prompt：记忆顺序为默契层 -> 共建层 -> 当前会话。
    system_parts = [state.compiled_soul, _load_memory_usage_prompt()]

    # 注入默契画像
    if state.tacit_context:
        system_parts.append(f"\n# 默契层人物理解\n{state.tacit_context}")

    # 注入已通过当前问题匹配的共建事实
    if state.memories:
        memory_context = "\n".join(
            f"- {m['summary']}" for m in state.memories[:3]
        )
        system_parts.append(f"\n# 与当前问题匹配的共建事实\n{memory_context}")

    # 注入当前会话上下文
    if state.session_context:
        system_parts.append(f"\n# 当前会话上下文\n{state.session_context}")

    # 注入未完待续
    if state.pending_anchors:
        anchor_line = "\n".join(f"- 上次提到: {a['topic']}" for a in state.pending_anchors)
        system_parts.append(f"\n# 上次未完成的话题\n{anchor_line}")

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


@lru_cache(maxsize=1)
def _load_memory_usage_prompt() -> str:
    prompt_path = Path(__file__).resolve().parents[2] / "prompts" / "chat_memory_usage.md"
    try:
        return prompt_path.read_text(encoding="utf-8").strip()
    except OSError:
        return "只使用与当前用户问题直接相关的记忆，不要主动提及无关的其他会话事项。"
