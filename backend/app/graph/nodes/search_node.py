"""Step 3.5: 搜索/天气前置状态提示（实际工作在 llm_call_node 的 Tool 模式中处理）"""

from app.graph.state import ChatState


async def search_node(state: ChatState):
    """前置提示节点 — Tool 的实际调用在 llm_call_node 的 function calling 中处理"""
    # 此节点仅为流水线占位，实际 tool 决策由模型在 llm_call 中完成
    return []
