"""时间工具 — 获取当前北京时间"""

import datetime

from app.graph.tools.base import BaseTool


class TimeTool(BaseTool):
    name = "get_current_time"
    description = "获取当前的日期和时间（北京时间），当用户问时间、日期、星期、节日时调用"
    parameters = {
        "type": "object",
        "properties": {},
        "required": [],
    }

    async def execute(self, **kwargs) -> str:
        now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
        weekday_cn = ["一", "二", "三", "四", "五", "六", "日"][now.weekday()]
        return (
            f"当前北京时间：{now.strftime('%Y年%m月%d日')} 星期{weekday_cn} "
            f"{now.strftime('%H:%M:%S')}"
        )
