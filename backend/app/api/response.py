"""统一 API 响应格式"""

from typing import Any


def ok(data: Any, message: str = "ok") -> dict:
    return {"success": True, "data": data, "message": message}


def fail(message: str = "操作失败", data: Any = None) -> dict:
    return {"success": False, "data": data, "message": message}
