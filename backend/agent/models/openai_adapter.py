import json
import httpx
from typing import AsyncGenerator
from urllib.parse import urlparse
from .base import BaseModelAdapter, ModelResponse
from security_utils import redact_sensitive_text

_DIRECT_BASE_URLS: set[str] = set()
_RESPONSE_PREVIEW_CHARS = 500

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

    def _endpoint_url(self, endpoint: str) -> str:
        """Allow users to paste either a base URL or an OpenAI endpoint URL."""
        base_url = self.base_url.rstrip("/")
        for suffix in ("/chat/completions", "/models"):
            if base_url.lower().endswith(suffix):
                base_url = base_url[: -len(suffix)].rstrip("/")
                break
        return f"{base_url}/{endpoint.lstrip('/')}"

    @staticmethod
    def _content_type(response) -> str:
        headers = getattr(response, "headers", {}) or {}
        return str(headers.get("content-type", "")).split(";", 1)[0].strip()

    @staticmethod
    def _safe_url(value) -> str:
        """Keep diagnostics useful without logging query strings or credentials."""
        if not value:
            return ""
        try:
            parsed = urlparse(str(value))
            hostname = parsed.hostname or ""
            if not hostname:
                return ""
            try:
                port = parsed.port
            except ValueError:
                port = None
            host = f"{hostname}:{port}" if port else hostname
            return f"{parsed.scheme}://{host}{parsed.path or '/'}"
        except (TypeError, ValueError):
            return ""

    @classmethod
    def _response_target(cls, response, fallback: str) -> str:
        return cls._safe_url(getattr(response, "url", None) or fallback)

    @staticmethod
    def _preview(body: str) -> str:
        body = (body or "").lstrip("\ufeff").strip()
        if not body:
            return "<空响应>"
        return redact_sensitive_text(body[:_RESPONSE_PREVIEW_CHARS])

    @classmethod
    def _diagnostic_error(
        cls,
        status: int,
        content_type: str,
        body: str,
        request_url: str = "",
    ) -> str:
        type_hint = content_type or "未知"
        target_hint = f"; 请求地址={request_url}" if request_url else ""
        return (
            f"[API响应异常 {status}] 内容类型={type_hint}; "
            f"响应前缀={cls._preview(body)}{target_hint}"
        )

    @staticmethod
    async def _read_response_text(response) -> str:
        try:
            body = await response.aread()
        except AttributeError:
            body = getattr(response, "content", b"")
        if isinstance(body, bytes):
            return body.decode("utf-8", errors="replace")
        return str(body or "")

    @staticmethod
    def _text_content(value) -> str:
        if isinstance(value, str):
            return value
        if isinstance(value, list):
            parts = []
            for part in value:
                if isinstance(part, str):
                    parts.append(part)
                elif isinstance(part, dict):
                    text = part.get("text") or part.get("content")
                    if isinstance(text, str):
                        parts.append(text)
            return "".join(parts)
        return "" if value is None else str(value)

    @classmethod
    def _response_from_completion(cls, payload: dict) -> ModelResponse:
        if not isinstance(payload, dict):
            raise ValueError("上游响应不是 JSON 对象")
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ValueError("上游响应缺少 choices 字段")
        choice = choices[0]
        if not isinstance(choice, dict):
            raise ValueError("上游响应的 choices[0] 不是对象")
        message = choice.get("message") or choice.get("delta") or {}
        if not isinstance(message, dict):
            raise ValueError("上游响应缺少 message 或 delta 对象")
        return ModelResponse(
            content=cls._text_content(message.get("content", "")),
            reasoning_content=cls._extract_reasoning(message),
            tool_calls=message.get("tool_calls") or [],
            finish_reason=choice.get("finish_reason", "stop"),
        )

    @classmethod
    def _stream_payload_responses(
        cls,
        payload: dict,
        accumulated_tool_calls: dict,
    ) -> list[ModelResponse]:
        if not isinstance(payload, dict) or not payload.get("choices"):
            return []
        choice = payload["choices"][0]
        if not isinstance(choice, dict):
            return []
        delta = choice.get("delta") or choice.get("message") or {}
        if not isinstance(delta, dict):
            return []

        responses = []
        reasoning_content = cls._extract_reasoning(delta)
        if reasoning_content:
            responses.append(ModelResponse(reasoning_content=reasoning_content))
        content = cls._text_content(delta.get("content", ""))
        if content:
            responses.append(ModelResponse(content=content))
        cls._merge_tool_call_deltas(
            accumulated_tool_calls,
            delta.get("tool_calls") or [],
        )
        return responses

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
        endpoint = self._endpoint_url("chat/completions")
        for attempt in range(3):
            try:
                timeout = httpx.Timeout(connect=20, read=600, write=120, pool=20)
                async with httpx.AsyncClient(timeout=timeout, trust_env=trust_env) as client:
                    if stream:
                        async with client.stream(
                            "POST",
                            endpoint,
                            json=payload,
                            headers=headers,
                        ) as resp:
                            content_type = self._content_type(resp)
                            request_url = self._response_target(resp, endpoint)
                            if not 200 <= resp.status_code < 300:
                                body = await self._read_response_text(resp)
                                last_error = self._diagnostic_error(
                                    resp.status_code, content_type, body, request_url,
                                )
                            else:
                                last_error = None
                                accumulated_tool_calls = {}
                                fallback_lines = []
                                last_json_payload = ""
                                saw_sse = False
                                saw_valid_payload = False

                                async for raw_line in resp.aiter_lines():
                                    line = raw_line.lstrip("\ufeff").strip()
                                    if not line:
                                        continue
                                    # SSE 注释、事件名和重试提示不是模型数据。
                                    if line.startswith(":") or line.lower().startswith(
                                        ("event:", "id:", "retry:")
                                    ):
                                        continue

                                    if line.lower().startswith("data:"):
                                        saw_sse = True
                                        data_text = line[5:].strip()
                                        if data_text == "[DONE]":
                                            break
                                    else:
                                        # 一些中转站返回 JSONL，而不是 SSE。
                                        data_text = line

                                    if not data_text:
                                        continue
                                    try:
                                        chunk = json.loads(data_text)
                                    except json.JSONDecodeError:
                                        fallback_lines.append(data_text)
                                        continue

                                    last_json_payload = data_text
                                    responses = self._stream_payload_responses(
                                        chunk,
                                        accumulated_tool_calls,
                                    )
                                    if isinstance(chunk, dict) and chunk.get("choices"):
                                        saw_valid_payload = True
                                    for response in responses:
                                        yield response

                                # 兼容一整段 JSON（包括格式化后的多行 JSON）。
                                if not saw_valid_payload and fallback_lines:
                                    fallback_text = "\n".join(fallback_lines).strip()
                                    try:
                                        fallback = json.loads(fallback_text)
                                        response = self._response_from_completion(fallback)
                                    except (json.JSONDecodeError, ValueError) as exc:
                                        last_error = (
                                            f"[兼容性错误] {exc}; "
                                            f"内容类型={content_type or '未知'}; "
                                            f"响应前缀={self._preview(fallback_text)}"
                                        )
                                    else:
                                        saw_valid_payload = True
                                        yield response

                                if not saw_valid_payload:
                                    diagnostic_body = "\n".join(fallback_lines).strip()
                                    if not diagnostic_body:
                                        diagnostic_body = last_json_payload
                                    if content_type == "text/html":
                                        compatibility_hint = (
                                            "上游返回了 HTML 页面，通常是 Base URL/接口路径错误、"
                                            "登录页重定向或网关拦截"
                                        )
                                    else:
                                        compatibility_hint = (
                                            "中转站返回的内容不是有效的 OpenAI "
                                            "chat/completions 响应"
                                        )
                                    last_error = (
                                        f"[兼容性错误] {compatibility_hint}; "
                                        f"内容类型={content_type or '未知'}; "
                                        f"响应前缀={self._preview(diagnostic_body)}; "
                                        f"请求地址={request_url}"
                                    )

                                if last_error:
                                    log_info("LLM", f"响应解析失败: {last_error[:700]}")
                                else:
                                    if accumulated_tool_calls:
                                        yield ModelResponse(
                                            content="",
                                            tool_calls=[
                                                accumulated_tool_calls[index]
                                                for index in sorted(accumulated_tool_calls)
                                            ],
                                        )
                                    return
                    else:
                        resp = await client.post(
                            endpoint,
                            json=payload,
                            headers=headers,
                        )
                        content_type = self._content_type(resp)
                        request_url = self._response_target(resp, endpoint)
                        if 200 <= resp.status_code < 300:
                            last_error = None
                            body = await self._read_response_text(resp)
                            try:
                                data = json.loads(body) if body.strip() else resp.json()
                                yield self._response_from_completion(data)
                            except (json.JSONDecodeError, ValueError) as exc:
                                last_error = (
                                    f"[兼容性错误] {exc}; 内容类型={content_type or '未知'}; "
                                    f"响应前缀={self._preview(body)}; 请求地址={request_url}"
                                )
                                log_info("LLM", f"响应解析失败: {last_error[:700]}")
                            else:
                                return
                        else:
                            body = await self._read_response_text(resp)
                            last_error = self._diagnostic_error(
                                resp.status_code, content_type, body, request_url,
                            )
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

            yield ModelResponse(content=redact_sensitive_text(last_error or "[连接失败]"))
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
                resp = await client.get(self._endpoint_url("models"), headers=headers)
        except httpx.TransportError as exc:
            if not trust_env:
                raise
            _DIRECT_BASE_URLS.add(self.base_url)
            log_info("LLM", f"环境代理连接失败，模型列表切换为直连: {type(exc).__name__}")
            async with httpx.AsyncClient(trust_env=False) as client:
                resp = await client.get(self._endpoint_url("models"), headers=headers)
        resp.raise_for_status()
        data = resp.json()
        return [m["id"] for m in data.get("data", [])]
