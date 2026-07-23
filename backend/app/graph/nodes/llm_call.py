from app.graph.state import ChatState
from app.graph.schemas import text_chunk_event, status_event
from app.services.model_gateway import gateway


async def llm_call_node(state: ChatState):
    """Step 5: 调用模型生成回复"""
    events = [status_event("thinking", "伴行正在思考...")]

    # 拼接 Prompt
    system_parts = [state.compiled_soul]

    # 注入记忆上下文
    if state.memories:
        memory_context = "\n".join(
            f"- 我记得: {m['summary']}" for m in state.memories[:3]
        )
        system_parts.append(f"\n# 相关记忆\n{memory_context}")

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
