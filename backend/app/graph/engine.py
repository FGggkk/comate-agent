from typing import AsyncGenerator

from app.db.session import async_session_factory
from app.graph.state import ChatState
from app.graph.schemas import SSEEvent, done_event, error_event
from app.graph.nodes.safety import safety_input_node
from app.graph.nodes.soul_loader import load_soul_node
from app.graph.nodes.memory import memory_node
from app.graph.nodes.search_node import search_node
from app.graph.nodes.router import router_node
from app.graph.nodes.llm_call import llm_call_node
from app.graph.nodes.postprocess import postprocess_node
from app.graph.nodes.actions import actions_node


async def run_engine(
    user_id: str,
    message: str,
    conversation_id: str | None = None,
) -> AsyncGenerator[SSEEvent, None]:
    """编排引擎：9 步流水线"""

    state = ChatState(user_id=user_id, message=message, conversation_id=conversation_id)

    async with async_session_factory() as db:
        # Step 1: 安全检查
        for event in await safety_input_node(state):
            yield event
        if state.error:
            yield error_event(state.error)
            yield done_event()
            return

        # Step 2: 加载 SOUL
        for event in await load_soul_node(state, db):
            yield event

        # Step 3: 读取记忆
        for event in await memory_node(state, db):
            yield event

        # Step 3.5: 搜索（检测是否需要联网搜索）
        for event in await search_node(state):
            yield event

        # Step 4: 路由
        for event in await router_node(state):
            yield event

        # Step 5: 模型调用
        for event in await llm_call_node(state):
            yield event
        if state.error:
            yield error_event(state.error)
            yield done_event()
            return

        # Step 6: 输出安全检查（简化）
        # 省略具体实现，v1 基本过滤

        # Step 7: 后处理。文本已完成流式输出，这里生成记忆候选供快捷按钮确认。
        try:
            await postprocess_node(state, db)
        except Exception as e:
            print(f"[postprocess] 后处理失败: {e}")

        # Step 8: 快捷按钮
        for event in await actions_node(state):
            yield event

        # Step 9: 完成
        yield done_event()
