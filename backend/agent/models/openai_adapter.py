import json
import httpx
from typing import AsyncGenerator
from urllib.parse import urlparse
from .base import BaseModelAdapter, ModelResponse

_DIRECT_BASE_URLS: set[str] = set()

class OpenAIAdapter(BaseModelAdapter):
    def __init__(
        self,
        api_key: str,
        base_url: str,
        model_name: str,
        provider_id: str = "custom",
        reasoning_available: bool = False,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model_name = model_name
        self.provider_id = provider_id
        self.reasoning_available = reasoning_available

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
                   temperature: float = None, top_p: float = None, max_tokens: int = None,
                   reasoning_enabled: bool = False,
                   reasoning_effort: str = "medium") -> AsyncGenerator[ModelResponse, None]:
        messages = self._sanitize_messages(messages)

        payload = {
            "model": self.model_name,
            "messages": messages,
            "stream": stream,
        }
        if tools:
            payload["tools"] = tools
        openai_reasoning = (
            reasoning_enabled
            and self.reasoning_available
            and self.provider_id == "openai"
        )
        if temperature is not None and not openai_reasoning:
            payload["temperature"] = temperature
        if top_p is not None and not openai_reasoning:
            payload["top_p"] = top_p
        if max_tokens is not None:
            token_key = "max_completion_tokens" if openai_reasoning else "max_tokens"
            payload[token_key] = max_tokens
        if openai_reasoning:
            payload["reasoning_effort"] = self._normalize_reasoning_effort(reasoning_effort)
        if self._uses_mimo_thinking_control():
            payload["thinking"] = {
                "type": "enabled" if reasoning_enabled else "disabled",
            }

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
        trust_env = not self._prefers_direct_connection()
        for attempt in range(3):
            try:
                timeout = httpx.Timeout(connect=20, read=600, write=120, pool=20)
                async with httpx.AsyncClient(timeout=timeout, trust_env=trust_env) as client:
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
                                    reasoning_content = self._extract_reasoning(delta)
                                    if reasoning_content:
                                        yield ModelResponse(reasoning_content=reasoning_content)
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
                                        reasoning_content=self._extract_reasoning(message),
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
                                reasoning_content=self._extract_reasoning(choice["message"]),
                                tool_calls=choice["message"].get("tool_calls") or [],
                                finish_reason=choice.get("finish_reason", "stop"),
                            )
                            return
                        last_error = f"[API错误 {resp.status_code}] {resp.text[:200]}"
            except httpx.TransportError as e:
                last_error = f"[连接失败] {e}"
                if trust_env:
                    trust_env = False
                    _DIRECT_BASE_URLS.add(self.base_url)
                    log_info("LLM", "环境代理连接失败，切换为直连")
                    if attempt < 2:
                        continue
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
    def _normalize_reasoning_effort(value: str) -> str:
        return value if value in {"low", "medium", "high"} else "medium"

    def _uses_mimo_thinking_control(self) -> bool:
        hostname = (urlparse(self.base_url).hostname or "").lower()
        return self.model_name.lower().startswith("mimo-") or hostname.endswith("xiaomimimo.com")

    def _prefers_direct_connection(self) -> bool:
        hostname = (urlparse(self.base_url).hostname or "").lower()
        return self.base_url in _DIRECT_BASE_URLS or hostname == "token-plan-cn.xiaomimimo.com"

    @staticmethod
    def _extract_reasoning(data: dict) -> str:
        for key in ("reasoning_content", "reasoning"):
            value = data.get(key)
            if isinstance(value, str) and value:
                return value

        details = data.get("reasoning_details")
        if not isinstance(details, list):
            return ""
        parts = []
        for detail in details:
            if not isinstance(detail, dict):
                continue
            value = detail.get("text") or detail.get("content") or detail.get("summary")
            if isinstance(value, str) and value:
                parts.append(value)
        return "".join(parts)

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
        from api.log_api import log_info

        headers = {"Authorization": f"Bearer {self.api_key}"}
        trust_env = not self._prefers_direct_connection()
        try:
            async with httpx.AsyncClient(trust_env=trust_env) as client:
                resp = await client.get(f"{self.base_url}/models", headers=headers)
        except httpx.TransportError as exc:
            if not trust_env:
                raise
            _DIRECT_BASE_URLS.add(self.base_url)
            log_info("LLM", f"环境代理连接失败，模型列表切换为直连: {type(exc).__name__}")
            async with httpx.AsyncClient(trust_env=False) as client:
                resp = await client.get(f"{self.base_url}/models", headers=headers)
        resp.raise_for_status()
        data = resp.json()
        return [m["id"] for m in data.get("data", [])]
