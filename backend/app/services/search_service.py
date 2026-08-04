"""Firecrawl 搜索服务"""

from app.config.settings import get_settings


async def search_web(query: str, max_results: int = 5) -> list[dict]:
    """调用 Firecrawl Search API，返回搜索结果列表"""
    settings = get_settings()
    if not settings.firecrawl_api_key or settings.firecrawl_api_key == "your-firecrawl-api-key":
        return []

    import httpx

    url = f"{settings.firecrawl_base_url}/v1/search"
    headers = {
        "Authorization": f"Bearer {settings.firecrawl_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "query": query,
        "limit": max_results,
    }

    try:
        async with httpx.AsyncClient(timeout=15, trust_env=False) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            results = []
            for item in (data.get("data", []) or []):
                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "description": item.get("description", ""),
                    "content": (item.get("markdown") or item.get("content") or "")[:500],
                })
            return results
    except Exception as e:
        print(f"[search] Firecrawl API 调用失败: {e}")
        return []


def needs_search(message: str) -> str | None:
    """检测消息是否需要搜索，返回搜索关键词或 None"""
    msg = message.strip()

    # 时间/日期类
    time_kw = ["现在几点", "今天几号", "今天星期", "什么时间", "几点了", "什么日子"]
    for kw in time_kw:
        if kw in msg:
            return None  # 时间由 Phase 1 注入处理

    # 天气类
    weather_kw = ["天气", "气温", "多少度", "会不会下雨", "冷不冷", "热不热", "空气质量"]
    for kw in weather_kw:
        if kw in msg:
            return f"{msg}"

    # 新闻/热点
    news_kw = [
        "新闻", "热点", "热搜", "快讯", "情报", "行情",
        "最新", "发生了什么", "最近", "今日", "近期",
        "AI", "芯片", "科技", "行业",
    ]
    for kw in news_kw:
        if kw in msg:
            return msg

    # 搜索/查询类
    search_kw = ["搜索", "查一下", "帮我查", "找一下", "搜一下", "百度", "谷歌"]
    for kw in search_kw:
        if kw in msg:
            return msg.replace(kw, "").strip() or msg

    return None
