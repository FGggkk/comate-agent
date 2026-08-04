"""天气工具 — 调用和风天气 API 获取实时天气"""

from app.graph.tools.base import BaseTool
from app.services.weather_service import get_weather


class WeatherTool(BaseTool):
    name = "get_weather"
    description = "查询某个城市的实时天气信息，包括温度、体感温度、天气状况、风力、湿度等"
    parameters = {
        "type": "object",
        "properties": {
            "city": {
                "type": "string",
                "description": "城市名，如：北京、上海、广州、深圳",
            }
        },
        "required": ["city"],
    }

    async def execute(self, **kwargs) -> str:
        city = kwargs.get("city", "")
        if not city:
            return "天气查询失败：请提供城市名"

        weather = await get_weather(city)
        if not weather:
            return f"未查询到 {city} 的天气信息"

        return (
            f"📍 {weather['city']} 实时天气\n"
            f"🌤 {weather['weather']}\n"
            f"🌡 {weather['temp']}°C（体感 {weather['feels_like']}°C）\n"
            f"💨 {weather['wind_dir']} {weather['wind_level']}级\n"
            f"💧 湿度：{weather['humidity']}%\n"
            f"👁 能见度：{weather['visibility']}公里\n"
            f"🕐 数据更新：{weather['update_time']}"
        )
