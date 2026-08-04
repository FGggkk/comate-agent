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

        results = await search_web(query, max_results=8)
        if not results:
            return f"未搜索到关于「{query}」的结果"

        # 优先展示商品详情页链接
        product_domains = ["item.jd.com", "detail.tmall.com", "detail.1688.com", "product.dangdang.com", "item.taobao.com"]
        product_results = [r for r in results if any(d in (r.get("url","") or "") for d in product_domains)]
        other_results = [r for r in results if r not in product_results]
        sorted_results = product_results + other_results

        lines = [f"关于「{query}」的搜索结果："]
        for i, r in enumerate(sorted_results[:5], 1):
            lines.append(f"\n{i}. {r['title']}")
            if r.get("description"):
                lines.append(f"   {r['description']}")
            lines.append(f"   链接: {r['url']}")
        return "\n".join(lines)
