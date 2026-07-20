import json
import httpx
from typing import AsyncGenerator
from .base import BaseModelAdapter, ModelResponse

class OpenAIAdapter(BaseModelAdapter):
    def __init__(self, api_key: str, base_url: str, model_name: str):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model_name = model_name

    @staticmethod
    def _sanitize_messages(messages: list[dict]) -> list[dict]:
        """清理消息中的非法字符，防止 JSON 序列化问题"""
        cleaned = []
        for msg in messages:
            c = msg.get("content")
            if isinstance(c, str):
                # 移除控制字符（保留换行和制表符）
                c = ''.join(ch for ch in c if ch in ('\n', '\r', '\t') or ord(ch) >= 32)
                cleaned.append({**msg, "content": c})
            elif isinstance(c, list):
                # vision 格式：保留原文
                cleaned.append(msg)
            else:
                cleaned.append(msg)
        return cleaned

    async def chat(self, messages: list[dict], tools: list = None, stream: bool = True,
                   temperature: float = None, top_p: float = None, max_tokens: int = None) -> AsyncGenerator[ModelResponse, None]:
        messages = self._sanitize_messages(messages)

        payload = {
            "model": self.model_name,
            "messages": messages,
            "stream": stream,
        }
        if tools:
            payload["tools"] = tools
        if temperature is not None:
            payload["temperature"] = temperature
        if top_p is not None:
            payload["top_p"] = top_p
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        # 日志：记录请求大小
        from api.log_api import log_info
        try:
            _size = len(json.dumps(payload).encode('utf-8'))
        except Exception:
            _size = -1

        # 调试日志
        from api.log_api import log_info
        try:
            _size = len(json.dumps(payload).encode('utf-8'))
        except Exception:
            _size = -1
        log_info("LLM", f"请求: {len(messages)}条消息, {_size}字节, 模型={self.model_name}, tools={len(tools) if tools else 0}")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        # 请求 + 重试
        last_error = None
        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=120) as client:
                    if stream:
                        resp = await client.post(f"{self.base_url}/chat/completions", json=payload, headers=headers)
                    else:
                        resp = await client.post(f"{self.base_url}/chat/completions", json=payload, headers=headers)

                if resp.status_code == 200:
                    break  # 成功

                last_error = f"[API错误 {resp.status_code}] {resp.text[:200]}"
                if attempt < 2:
                    from api.log_api import log_info
                    log_info("LLM", f"请求失败({resp.status_code})，重试 {attempt+1}/2")
                    # 保存失败请求用于调试
                    try:
                        with open("data/debug_request.json", "w", encoding="utf-8") as f:
                            json.dump(payload, f, ensure_ascii=False)
                    except Exception:
                        pass
                    import asyncio
                    await asyncio.sleep(1)
                else:
                    yield ModelResponse(content=last_error)
                    return
            except Exception as e:
                last_error = f"[连接失败] {e}"
                if attempt < 2:
                    import asyncio
                    await asyncio.sleep(1)
                else:
                    yield ModelResponse(content=last_error)
                    return

        # 解析响应
        if stream:
            accumulated_tool_calls = {}
            content = ""

            for line in resp.text.split("\n"):
                line = line.strip()
                if not line.startswith("data: ") or line == "data: [DONE]":
                    continue
                try:
                    chunk = json.loads(line[6:])
                except json.JSONDecodeError:
                    continue
                if not chunk.get("choices"):
                    continue
                delta = chunk["choices"][0].get("delta", {})

                if delta.get("content"):
                    content += delta["content"]
                    yield ModelResponse(content=delta["content"])

                if delta.get("tool_calls"):
                    for tc_delta in delta["tool_calls"]:
                        idx = tc_delta.get("index", 0)
                        if idx not in accumulated_tool_calls:
                            accumulated_tool_calls[idx] = {
                                "id": tc_delta.get("id", ""),
                                "type": tc_delta.get("type", "function"),
                                "function": {"name": "", "arguments": ""}
                            }
                        tc = accumulated_tool_calls[idx]
                        if tc_delta.get("id"):
                            tc["id"] = tc_delta["id"]
                        func = tc_delta.get("function", {})
                        if func.get("name"):
                            tc["function"]["name"] += func["name"]
                        if func.get("arguments"):
                            tc["function"]["arguments"] += func["arguments"]

            if accumulated_tool_calls:
                complete = [accumulated_tool_calls[i] for i in sorted(accumulated_tool_calls.keys())]
                yield ModelResponse(content="", tool_calls=complete)
        else:
            data = resp.json()
            choice = data["choices"][0]
            yield ModelResponse(
                content=choice["message"].get("content", ""),
                tool_calls=choice["message"].get("tool_calls") or [],
                finish_reason=choice.get("finish_reason", "stop")
            )

    async def list_models(self) -> list[str]:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{self.base_url}/models", headers={"Authorization": f"Bearer {self.api_key}"})
            data = resp.json()
            return [m["id"] for m in data.get("data", [])]
