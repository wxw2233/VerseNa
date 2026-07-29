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
                        async with client.stream(
                            "POST",
                            f"{self.base_url}/chat/completions",
                            json=payload,
                            headers=headers,
                        ) as resp:
                            if resp.status_code != 200:
                                body = (await resp.aread()).decode("utf-8", errors="replace")
                                last_error = f"[API错误 {resp.status_code}] {body[:200]}"
                            else:
                                accumulated_tool_calls = {}
                                fallback_lines = []
                                saw_sse = False

                                async for raw_line in resp.aiter_lines():
                                    line = raw_line.strip()
                                    if not line:
                                        continue
                                    if not line.startswith("data:"):
                                        fallback_lines.append(raw_line)
                                        continue

                                    data_text = line[5:].strip()
                                    if data_text == "[DONE]":
                                        break
                                    saw_sse = True
                                    try:
                                        chunk = json.loads(data_text)
                                    except json.JSONDecodeError:
                                        continue
                                    if not chunk.get("choices"):
                                        continue

                                    delta = chunk["choices"][0].get("delta", {})
                                    if delta.get("content"):
                                        yield ModelResponse(content=delta["content"])
                                    self._merge_tool_call_deltas(
                                        accumulated_tool_calls,
                                        delta.get("tool_calls") or [],
                                    )

                                if accumulated_tool_calls:
                                    yield ModelResponse(
                                        content="",
                                        tool_calls=[
                                            accumulated_tool_calls[index]
                                            for index in sorted(accumulated_tool_calls)
                                        ],
                                    )
                                elif not saw_sse and fallback_lines:
                                    fallback = json.loads("\n".join(fallback_lines))
                                    choice = fallback["choices"][0]
                                    message = choice.get("message", {})
                                    yield ModelResponse(
                                        content=message.get("content", ""),
                                        tool_calls=message.get("tool_calls") or [],
                                        finish_reason=choice.get("finish_reason", "stop"),
                                    )
                                return
                    else:
                        resp = await client.post(
                            f"{self.base_url}/chat/completions",
                            json=payload,
                            headers=headers,
                        )
                        if resp.status_code == 200:
                            data = resp.json()
                            choice = data["choices"][0]
                            yield ModelResponse(
                                content=choice["message"].get("content", ""),
                                tool_calls=choice["message"].get("tool_calls") or [],
                                finish_reason=choice.get("finish_reason", "stop"),
                            )
                            return
                        last_error = f"[API错误 {resp.status_code}] {resp.text[:200]}"
            except Exception as e:
                last_error = f"[连接失败] {e}"

            if attempt < 2:
                log_info("LLM", f"请求失败，重试 {attempt + 1}/2: {last_error[:120]}")
                import asyncio
                await asyncio.sleep(1)
                continue

            yield ModelResponse(content=last_error or "[连接失败]")
            return

    @staticmethod
    def _merge_tool_call_deltas(accumulated: dict, deltas: list):
        for delta in deltas:
            index = delta.get("index", 0)
            if index not in accumulated:
                accumulated[index] = {
                    "id": delta.get("id", ""),
                    "type": delta.get("type", "function"),
                    "function": {"name": "", "arguments": ""},
                }
            tool_call = accumulated[index]
            if delta.get("id"):
                tool_call["id"] = delta["id"]
            function = delta.get("function", {})
            if function.get("name"):
                tool_call["function"]["name"] += function["name"]
            if function.get("arguments"):
                tool_call["function"]["arguments"] += function["arguments"]

    async def list_models(self) -> list[str]:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{self.base_url}/models", headers={"Authorization": f"Bearer {self.api_key}"})
            data = resp.json()
            return [m["id"] for m in data.get("data", [])]
