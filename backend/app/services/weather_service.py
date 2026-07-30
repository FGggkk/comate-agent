"""和风天气服务"""

from app.config.settings import get_settings

# 常用城市名称 → 城市 ID 映射（避免调用 Geo API）
CITY_IDS: dict[str, str] = {
    "北京": "101010100", "上海": "101020100", "广州": "101280101",
    "深圳": "101280601", "杭州": "101210101", "成都": "101270101",
    "南京": "101190101", "武汉": "101200101", "重庆": "101040100",
    "天津": "101030100", "苏州": "101190401", "西安": "101110101",
    "长沙": "101250101", "郑州": "101180101", "东莞": "101281601",
    "青岛": "101120201", "厦门": "101230201", "宁波": "101210401",
    "大连": "101070201", "济南": "101120101", "珠海": "101280701",
    "佛山": "101280301", "合肥": "101220101", "昆明": "101290101",
    "哈尔滨": "101050101", "福州": "101230101", "温州": "101210701",
    "南宁": "101300101", "贵阳": "101260101", "太原": "101100101",
    "南昌": "101240101", "石家庄": "101090101", "沈阳": "101070101",
    "长春": "101060101", "兰州": "101160101", "海口": "101310101",
    "三亚": "101310201", "呼和浩特": "101080101", "银川": "101170101",
    "西宁": "101150101", "拉萨": "101140101", "乌鲁木齐": "101130101",
    "香港": "101320101", "澳门": "101330101", "台北": "101340101",
    # 青岛下辖区
    "黄岛": "101120201", "黄岛区": "101120201",
    "崂山": "101120202", "即墨": "101120209",
    # 上海下辖区
    "浦东": "101020300", "浦东新区": "101020300",
    "松江": "101020900", "嘉定": "101020500",
}

# 关键词映射：从"青岛黄岛区"提取"青岛"
CITY_KEYWORDS: list[tuple[str, str]] = [
    ("黄岛区", "黄岛"), ("浦东新区", "浦东"),
    ("黄岛", "黄岛"), ("浦东", "浦东"),
    ("北京", "北京"), ("上海", "上海"), ("广州", "广州"),
    ("深圳", "深圳"), ("杭州", "杭州"), ("成都", "成都"),
    ("南京", "南京"), ("武汉", "武汉"), ("重庆", "重庆"),
    ("天津", "天津"), ("苏州", "苏州"), ("西安", "西安"),
    ("长沙", "长沙"), ("郑州", "郑州"), ("青岛", "青岛"),
    ("厦门", "厦门"), ("大连", "大连"), ("济南", "济南"),
    ("珠海", "珠海"), ("深圳", "深圳"), ("香港", "香港"),
    ("澳门", "澳门"), ("台北", "台北"),
]


def _find_city_id(city_input: str) -> tuple[str, str] | None:
    """从用户输入中提取城市名并返回 (city_id, city_name)"""
    # 精确匹配
    if city_input in CITY_IDS:
        return CITY_IDS[city_input], city_input

    # 关键词匹配
    for keyword, city_name in CITY_KEYWORDS:
        if keyword in city_input:
            cid = CITY_IDS.get(city_name)
            if cid:
                return cid, city_name

    return None


async def get_weather(city: str) -> dict | None:
    """调用和风天气 API 获取实时天气"""
    settings = get_settings()
    if not settings.heweather_api_key or settings.heweather_api_key == "your-heweather-api-key":
        return None

    result = _find_city_id(city)
    if not result:
        return None
    city_id, city_name = result

    import httpx

    base = settings.heweather_base_url.rstrip("/")

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            weather_url = f"{base}/v7/weather/now"
            params = {"location": city_id, "key": settings.heweather_api_key}
            resp = await client.get(weather_url, params=params)
            resp.raise_for_status()
            data = resp.json()

            if data.get("code") != "200":
                return None

            now = data.get("now", {})
            return {
                "city": city_name,
                "temp": now.get("temp"),
                "feels_like": now.get("feelsLike"),
                "weather": now.get("text"),
                "wind_dir": now.get("windDir"),
                "wind_level": now.get("windScale"),
                "humidity": now.get("humidity"),
                "visibility": now.get("vis"),
                "pressure": now.get("pressure"),
                "update_time": data.get("updateTime", ""),
            }
    except Exception as e:
        print(f"[weather] 和风天气 API 调用失败: {e}")
        return None
