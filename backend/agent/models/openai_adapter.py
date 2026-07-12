import json
import httpx
from typing import AsyncGenerator
from .base import BaseModelAdapter, ModelResponse

class OpenAIAdapter(BaseModelAdapter):
    def __init__(self, api_key: str, base_url: str, model_name: str):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model_name = model_name

    async def chat(self, messages: list[dict], tools: list = None, stream: bool = True) -> AsyncGenerator[ModelResponse, None]:
        payload = {
            "model": self.model_name,
            "messages": messages,
            "stream": stream,
        }
        if tools:
            payload["tools"] = tools

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=120) as client:
            if stream:
                async with client.stream("POST", f"{self.base_url}/chat/completions", json=payload, headers=headers) as resp:
                    if resp.status_code != 200:
                        body = await resp.aread()
                        yield ModelResponse(content=f"[API错误 {resp.status_code}] {body.decode()[:200]}")
                        return

                    # Accumulate streaming tool_calls by index
                    accumulated_tool_calls = {}
                    content = ""

                    async for line in resp.aiter_lines():
                        if line.startswith("data: ") and line.strip() != "data: [DONE]":
                            try:
                                chunk = json.loads(line[6:])
                            except json.JSONDecodeError:
                                continue
                            if not chunk.get("choices"):
                                continue
                            delta = chunk["choices"][0].get("delta", {})

                            # Accumulate text content
                            if delta.get("content"):
                                content += delta["content"]
                                yield ModelResponse(content=delta["content"])

                            # Accumulate tool_call deltas
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

                    # Yield complete tool_calls at the end
                    if accumulated_tool_calls:
                        complete = [accumulated_tool_calls[i] for i in sorted(accumulated_tool_calls.keys())]
                        yield ModelResponse(content="", tool_calls=complete)
            else:
                resp = await client.post(f"{self.base_url}/chat/completions", json=payload, headers=headers)
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
