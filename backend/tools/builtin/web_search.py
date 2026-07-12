import httpx
import re
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
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            # 尝试 Bing
            try:
                results = await self._search_bing(client, query, headers)
                if results:
                    return results
            except Exception:
                pass
            # 回退到百度
            try:
                results = await self._search_baidu(client, query, headers)
                if results:
                    return results
            except Exception:
                pass
        return "搜索失败：无法连接到搜索引擎"

    async def _search_bing(self, client, query, headers) -> str:
        resp = await client.get(
            "https://cn.bing.com/search",
            params={"q": query, "ensearch": "0"},
            headers=headers,
        )
        text = resp.text
        # 提取搜索结果摘要
        snippets = re.findall(r'<p[^>]*>(.*?)</p>', text)
        clean = []
        for s in snippets:
            s = re.sub(r'<[^>]+>', '', s).strip()
            if len(s) > 20 and '...' not in s[:5]:
                clean.append(s)
        if clean:
            return "\n\n".join(clean[:5])
        return ""

    async def _search_baidu(self, client, query, headers) -> str:
        resp = await client.get(
            "https://www.baidu.com/s",
            params={"wd": query},
            headers=headers,
        )
        text = resp.text
        # 提取搜索结果摘要
        snippets = re.findall(r'<span[^>]*class="content-right_[^"]*"[^>]*>(.*?)</span>', text)
        if not snippets:
            snippets = re.findall(r'<div[^>]*class="c-abstract"[^>]*>(.*?)</div>', text)
        clean = []
        for s in snippets:
            s = re.sub(r'<[^>]+>', '', s).strip()
            if len(s) > 10:
                clean.append(s)
        if clean:
            return "\n\n".join(clean[:5])
        return ""

def register(registry):
    registry.register(WebSearchTool())
