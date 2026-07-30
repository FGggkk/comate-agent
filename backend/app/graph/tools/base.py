"""Tool 基类，所有 tool 从这里继承"""

from abc import ABC, abstractmethod


class BaseTool(ABC):
    """工具基类"""

    @property
    @abstractmethod
    def name(self) -> str:
        """工具名称（英文小写蛇形，作为 function name）"""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """工具描述（模型根据描述决定是否调用）"""
        ...

    @property
    @abstractmethod
    def parameters(self) -> dict:
        """参数 JSON Schema（OpenAI Function Calling 格式）"""
        ...

    @abstractmethod
    async def execute(self, **kwargs) -> str:
        """执行工具，返回结果文本"""
        ...
