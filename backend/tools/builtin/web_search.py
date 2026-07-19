import httpx
import json
import re
from tools.base import BaseTool


class WebSearchTool(BaseTool):
    name = "web_search"
    description = "搜索互联网获取信息，支持 SerpAPI、Tavily、Bing API 和内置爬取"
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "搜索关键词"},
            "provider": {
                "type": "string",
                "enum": ["auto", "serpapi", "tavily", "bing", "builtin"],
                "description": "指定搜索引擎，auto 为自动选择"
            }
        },
        "required": ["query"]
    }

    async def _get_search_config(self):
        """从数据库读取搜索配置"""
        try:
            from db.database import db
            config = {}
            for key in ["search_strategy", "search_provider", "serpapi_key", "tavily_key", "bing_key"]:
                val = await db.get_config(f"search_{key}", "")
                config[key] = val
            return config
        except Exception:
            return {"search_strategy": "auto", "search_provider": "builtin", "serpapi_key": "", "tavily_key": "", "bing_key": ""}

    async def execute(self, query: str = "", provider: str = "auto", **kwargs) -> str:
        if not query:
            return "错误：请提供搜索关键词"

        config = await self._get_search_config()

        # 确定使用哪个搜索引擎
        if provider and provider != "auto":
            # Agent 显式指定
            chosen = provider
        elif config.get("search_strategy") == "指定":
            chosen = config.get("search_provider", "builtin")
        else:
            # 自动：优先用有 key 的 API
            if config.get("serpapi_key"):
                chosen = "serpapi"
            elif config.get("tavily_key"):
                chosen = "tavily"
            elif config.get("bing_key"):
                chosen = "bing"
            else:
                chosen = "builtin"

        # 执行搜索
        try:
            if chosen == "serpapi" and config.get("serpapi_key"):
                return await self._search_serpapi(query, config["serpapi_key"])
            elif chosen == "tavily" and config.get("tavily_key"):
                return await self._search_tavily(query, config["tavily_key"])
            elif chosen == "bing" and config.get("bing_key"):
                return await self._search_bing_api(query, config["bing_key"])
        except Exception as e:
            # API 失败时回退到内置爬取
            pass

        # 内置爬取
        return await self._search_builtin(query)

    async def _search_serpapi(self, query: str, api_key: str) -> str:
        """SerpAPI (Google)"""
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                "https://serpapi.com/search",
                params={"q": query, "api_key": api_key, "engine": "google", "num": 5, "hl": "zh-cn"}
            )
            data = resp.json()
            results = []
            for item in data.get("organic_results", [])[:5]:
                title = item.get("title", "")
                snippet = item.get("snippet", "")
                link = item.get("link", "")
                results.append(f"**{title}**\n{snippet}\n{link}")
            return "\n\n".join(results) if results else "SerpAPI 未返回结果"

    async def _search_tavily(self, query: str, api_key: str) -> str:
        """Tavily (AI 优化搜索)"""
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                "https://api.tavily.com/search",
                json={"query": query, "api_key": api_key, "max_results": 5, "search_depth": "basic"},
            )
            data = resp.json()
            results = []
            for item in data.get("results", [])[:5]:
                title = item.get("title", "")
                content = item.get("content", "")
                url = item.get("url", "")
                results.append(f"**{title}**\n{content}\n{url}")
            return "\n\n".join(results) if results else "Tavily 未返回结果"

    async def _search_bing_api(self, query: str, api_key: str) -> str:
        """Bing Web Search API"""
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                "https://api.bing.microsoft.com/v7.0/search",
                params={"q": query, "count": 5, "mkt": "zh-CN"},
                headers={"Ocp-Apim-Subscription-Key": api_key}
            )
            data = resp.json()
            results = []
            for item in data.get("webPages", {}).get("value", [])[:5]:
                name = item.get("name", "")
                snippet = item.get("snippet", "")
                url = item.get("url", "")
                results.append(f"**{name}**\n{snippet}\n{url}")
            return "\n\n".join(results) if results else "Bing API 未返回结果"

    async def _search_builtin(self, query: str) -> str:
        """内置 HTML 爬取（Bing + 百度）"""
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            try:
                results = await self._scrape_bing(client, query, headers)
                if results:
                    return results
            except Exception:
                pass
            try:
                results = await self._scrape_baidu(client, query, headers)
                if results:
                    return results
            except Exception:
                pass
        return "搜索失败：无法连接到搜索引擎"

    async def _scrape_bing(self, client, query, headers) -> str:
        resp = await client.get(
            "https://cn.bing.com/search",
            params={"q": query, "ensearch": "0"},
            headers=headers,
        )
        text = resp.text
        snippets = re.findall(r'<p[^>]*>(.*?)</p>', text)
        clean = []
        for s in snippets:
            s = re.sub(r'<[^>]+>', '', s).strip()
            if len(s) > 20 and '...' not in s[:5]:
                clean.append(s)
        if clean:
            return "\n\n".join(clean[:5])
        return ""

    async def _scrape_baidu(self, client, query, headers) -> str:
        resp = await client.get(
            "https://www.baidu.com/s",
            params={"wd": query},
            headers=headers,
        )
        text = resp.text
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
