import httpx
import re
from tools.base import BaseTool


class WebFetchTool(BaseTool):
    name = "web_fetch"
    description = "抓取指定网页内容并返回文本，适合阅读文章、获取网页信息"
    parameters = {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "要抓取的网页 URL"},
            "max_length": {"type": "integer", "description": "返回内容最大字符数，默认 5000"}
        },
        "required": ["url"]
    }

    async def execute(self, url: str = "", max_length: int = 5000, **kwargs) -> str:
        if not url:
            return "错误：请提供 URL"

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }

        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                resp = await client.get(url, headers=headers)
                resp.raise_for_status()
                content_type = resp.headers.get("content-type", "")

                # 如果是纯文本或 JSON，直接返回
                if "json" in content_type:
                    text = resp.text[:max_length]
                    return f"[JSON 内容]\n{text}"

                if "text/plain" in content_type:
                    return resp.text[:max_length]

                # HTML → 纯文本提取
                text = resp.text
                # 移除 script/style
                text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL | re.IGNORECASE)
                text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
                # 移除 HTML 标签
                text = re.sub(r'<[^>]+>', ' ', text)
                # 清理空白
                text = re.sub(r'\s+', ' ', text).strip()
                # 解码常见 HTML 实体
                text = text.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
                text = text.replace('&quot;', '"').replace('&#39;', "'").replace('&nbsp;', ' ')

                if not text:
                    return "网页内容为空或无法提取文本"

                title_match = re.search(r'<title[^>]*>(.*?)</title>', resp.text, re.DOTALL | re.IGNORECASE)
                title = title_match.group(1).strip() if title_match else ""

                result = f"[{title}]\n\n{text}" if title else text
                if len(result) > max_length:
                    result = result[:max_length] + f"\n\n... (已截断，共 {len(text)} 字符)"

                return result

        except httpx.TimeoutException:
            return f"抓取超时（15秒）：{url}"
        except httpx.HTTPStatusError as e:
            return f"HTTP 错误 {e.response.status_code}：{url}"
        except Exception as e:
            return f"抓取失败：{type(e).__name__}: {e}"


def register(registry):
    registry.register(WebFetchTool())
