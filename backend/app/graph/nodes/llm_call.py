"""Step 5: 模型调用节点 — 支持 Function Calling（Tool 模式）"""

import json
import datetime
from functools import lru_cache
from pathlib import Path

from app.graph.state import ChatState
from app.graph.schemas import text_chunk_event, status_event
from app.graph.tools import TOOL_REGISTRY
from app.services.model_gateway import gateway


async def llm_call_node(state: ChatState):
    """两轮调用：先让模型决策是否要调工具，再流式输出最终回答"""
    events = [status_event("thinking", "伴行正在思考...")]

    # 边界回复（禁区等）
    boundary_reply = _boundary_update_reply(state)
    if boundary_reply:
        state.reply = boundary_reply
        events.append(text_chunk_event(boundary_reply))
        return events

    # 1. 构建 system prompt
    system = _build_system_prompt(state)

    # 2. 第一轮：非流式，带 tools 定义，让模型决策
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": state.message},
    ]
    tools_def = TOOL_REGISTRY.to_openai_tools()

    try:
        first_resp = await gateway.chat_with_tools(messages, tools=tools_def)
        choice = first_resp["choices"][0]
        msg = choice.get("message", {})

        tool_calls = msg.get("tool_calls")

        # 3. 如果有 tool_calls，执行工具
        if tool_calls:
            events.append(status_event("tool_call", "正在获取信息..."))
            # 添加 assistant 的 tool_call 消息
            messages.append({
                "role": "assistant",
                "content": msg.get("content") or None,
                "tool_calls": [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {
                            "name": tc["function"]["name"],
                            "arguments": tc["function"]["arguments"],
                        },
                    }
                    for tc in tool_calls
                ],
            })

            # 逐个执行工具
            for tc in tool_calls:
                func_name = tc["function"]["name"]
                try:
                    args = json.loads(tc["function"]["arguments"])
                except json.JSONDecodeError:
                    args = {}

                tool = TOOL_REGISTRY.get(func_name)
                if tool:
                    result = await tool.execute(**args)
                else:
                    result = f"未知工具: {func_name}"

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": result,
                })

            # 4. 第二轮：流式输出最终回答
            events.append(status_event("thinking", "伴行正在整理回答..."))
            full_reply = ""
            async for chunk in gateway.stream_messages(messages):
                full_reply += chunk
                events.append(text_chunk_event(chunk))

            state.reply = full_reply
        else:
            # 没有 tool_calls，直接流式输出第一轮的回答
            content = msg.get("content", "")
            if content:
                # 将第一轮的非流式结果拆成一句输出（模拟流式）
                events.append(text_chunk_event(content))
                state.reply = content
            else:
                # 回退：用 stream_messages 再调一次
                full_reply = ""
                async for chunk in gateway.stream_messages(messages):
                    full_reply += chunk
                    events.append(text_chunk_event(chunk))
                state.reply = full_reply

    except Exception as e:
        state.error = f"模型调用失败: {str(e)}"
        fallback = "嗯，我在听。能再多说一点吗？"
        state.reply = fallback
        events.append(text_chunk_event(fallback))

    return events


def _build_system_prompt(state: ChatState) -> str:
    """构建 system prompt"""
    parts = [state.compiled_soul, _load_memory_usage_prompt()]

    # 注入当前时间（让模型知道 context，但不强制用 tool）
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
    weekday_cn = ["一", "二", "三", "四", "五", "六", "日"][now.weekday()]
    time_str = now.strftime(f"%Y年%m月%d日") + f" 星期{weekday_cn} " + now.strftime("%H:%M")
    parts.append(f"\n# 当前时间\n当前是北京时间 {time_str}。如果用户问时间、日期、节日等信息，你可以直接用 get_current_time 工具获取精确时间。")

    # 禁区话题
    if state.forbidden_topics:
        forbidden_line = "、".join(
            topic["topic"] for topic in state.forbidden_topics[:8] if topic.get("topic")
        )
        if forbidden_line:
            parts.append(
                "\n# 禁区话题边界\n"
                f"用户已设置这些禁区话题：{forbidden_line}。\n"
                "不要主动提及、展开、联想、追问或复述这些禁区话题；"
                "即使用户询问禁区清单，也只说明存在边界设置，不要倒出具体内容。"
            )

    # 默契画像
    if state.tacit_context:
        parts.append(f"\n# 默契层人物理解\n{state.tacit_context}")

    # 共建事实
    if state.memories:
        memory_context = "\n".join(f"- {m['summary']}" for m in state.memories)
        parts.append(f"\n# 与当前问题匹配的共建事实\n{memory_context}")

    # 会话上下文
    if state.session_context:
        parts.append(f"\n# 当前会话上下文\n{state.session_context}")

    return "\n".join(parts)


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
