"""搜索工具 — 调用 Firecrawl 进行 Web 搜索"""

from app.graph.tools.base import BaseTool
from app.services.search_service import search_web


class SearchTool(BaseTool):
    name = "search_web"
    description = "搜索互联网上的最新信息，当用户询问新闻、热点、实时信息、知识性问题时调用"
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "搜索关键词，尽量完整准确",
            }
        },
        "required": ["query"],
    }

    async def execute(self, **kwargs) -> str:
        query = kwargs.get("query", "")
        if not query:
            return "搜索失败：未提供搜索关键词"

        results = await search_web(query, max_results=5)
        if not results:
            return f"未搜索到关于「{query}」的结果"

        lines = [f"关于「{query}」的搜索结果："]
        for i, r in enumerate(results, 1):
            lines.append(f"\n{i}. {r['title']}")
            if r.get("description"):
                lines.append(f"   {r['description']}")
            if r.get("content"):
                lines.append(f"   {r['content'][:300]}")
            lines.append(f"   来源: {r['url']}")
        return "\n".join(lines)
