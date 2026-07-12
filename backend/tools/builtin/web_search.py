import httpx
from tools.base import BaseTool

class WebSearchTool(BaseTool):
    name = "web_search"
    description = "搜索互联网获取信息"
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "搜索关键词"}
        },
        "required": ["query"]
    }

    async def execute(self, query: str = "", **kwargs) -> str:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    "https://api.duckduckgo.com/",
                    params={"q": query, "format": "json", "no_html": 1}
                )
                data = resp.json()
                abstract = data.get("AbstractText", "")
                if abstract:
                    return abstract
                results = data.get("RelatedTopics", [])[:3]
                return "\n".join(r.get("Text", "") for r in results if r.get("Text")) or "未找到相关结果"
        except Exception as e:
            return f"搜索失败: {e}"

def register(registry):
    registry.register(WebSearchTool())
