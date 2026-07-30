"""Tool 注册器"""

from app.graph.tools.base import BaseTool


class ToolRegistry:
    """全局工具注册器"""

    def __init__(self):
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool):
        self._tools[tool.name] = tool

    def get(self, name: str) -> BaseTool | None:
        return self._tools.get(name)

    def all(self) -> list[BaseTool]:
        return list(self._tools.values())

    def to_openai_tools(self) -> list[dict]:
        """生成 OpenAI Function Calling 格式的工具定义"""
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters,
                },
            }
            for t in self._tools.values()
        ]


# 全局单例
TOOL_REGISTRY = ToolRegistry()


# --- 自动注册所有工具 ---
def _register_all():
    from app.graph.tools.time_tool import TimeTool
    from app.graph.tools.search_tool import SearchTool
    from app.graph.tools.weather_tool import WeatherTool

    TOOL_REGISTRY.register(TimeTool())
    TOOL_REGISTRY.register(SearchTool())
    TOOL_REGISTRY.register(WeatherTool())


_register_all()
