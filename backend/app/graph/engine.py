import asyncio
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session_factory
from app.graph.state import ChatState
from app.graph.schemas import SSEEvent, done_event, error_event
from app.graph.nodes.safety import safety_input_node
from app.graph.nodes.soul_loader import load_soul_node
from app.graph.nodes.memory import memory_node
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

        # Step 7: 异步后处理（不阻塞，直接跑）
        asyncio.create_task(_run_postprocess(state, db))

        # Step 8: 快捷按钮
        for event in await actions_node(state):
            yield event

        # Step 9: 完成
        yield done_event()


async def _run_postprocess(state: ChatState, db: AsyncSession):
    """后台异步执行后处理"""
    try:
        await postprocess_node(state, db)
    except Exception:
        pass  # 后处理失败不影响用户
