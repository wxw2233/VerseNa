import pytest
import asyncio
from agent.models.base import BaseModelAdapter, ModelResponse

def test_model_response_dataclass():
    r = ModelResponse(content="hello")
    assert r.content == "hello"
    assert r.reasoning_content == ""
    assert r.tool_calls == []
    assert r.finish_reason == "stop"

def test_openai_adapter_init():
    from agent.models.openai_adapter import OpenAIAdapter
    adapter = OpenAIAdapter(api_key="test", base_url="https://api.openai.com/v1", model_name="gpt-4")
    assert adapter.model_name == "gpt-4"
    assert adapter.base_url == "https://api.openai.com/v1"


class FakeStreamResponse:
    def __init__(self, lines, release=None, status_code=200, headers=None, body=b""):
        self.status_code = status_code
        self._lines = lines
        self._release = release
        self.headers = headers or {}
        self._body = body

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def aiter_lines(self):
        for index, line in enumerate(self._lines):
            yield line
            if index == 0 and self._release:
                await self._release.wait()

    async def aread(self):
        return self._body


class FakeAsyncClient:
    def __init__(self, response):
        self.response = response

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    def stream(self, *args, **kwargs):
        return self.response


@pytest.mark.asyncio
async def test_openai_adapter_yields_sse_before_response_finishes(monkeypatch):
    from agent.models import openai_adapter as adapter_module
    from agent.models.openai_adapter import OpenAIAdapter

    release = asyncio.Event()
    response = FakeStreamResponse([
        'data:{"choices":[{"delta":{"content":"first"}}]}',
        'data: {"choices":[{"delta":{"content":" second"}}]}',
        'data: [DONE]',
    ], release=release)
    monkeypatch.setattr(adapter_module.httpx, "AsyncClient", lambda **kwargs: FakeAsyncClient(response))

    adapter = OpenAIAdapter("key", "https://example.com/v1", "model")
    stream = adapter.chat([{"role": "user", "content": "hello"}])

    first = await anext(stream)
    assert first.content == "first"

    second_task = asyncio.create_task(anext(stream))
    await asyncio.sleep(0)
    assert second_task.done() is False
    release.set()
    assert (await second_task).content == " second"


@pytest.mark.asyncio
async def test_openai_adapter_falls_back_to_json_response(monkeypatch):
    from agent.models import openai_adapter as adapter_module
    from agent.models.openai_adapter import OpenAIAdapter

    response = FakeStreamResponse([
        '{"choices":[{"message":{"content":"fallback"},"finish_reason":"stop"}]}',
    ])
    monkeypatch.setattr(adapter_module.httpx, "AsyncClient", lambda **kwargs: FakeAsyncClient(response))

    adapter = OpenAIAdapter("key", "https://example.com/v1", "model")
    chunks = [chunk async for chunk in adapter.chat([{"role": "user", "content": "hello"}])]

    assert [chunk.content for chunk in chunks] == ["fallback"]


@pytest.mark.asyncio
async def test_openai_adapter_accepts_jsonl_and_sse_metadata(monkeypatch):
    from agent.models import openai_adapter as adapter_module
    from agent.models.openai_adapter import OpenAIAdapter

    response = FakeStreamResponse([
        "{\"choices\":[{\"delta\":{\"content\":\"jsonl\"}}]}",
        "event: message",
        "data: {\"choices\":[{\"delta\":{\"content\":\" +sse\"}}]}",
        "id: 2",
        "data: [DONE]",
    ])
    monkeypatch.setattr(
        adapter_module.httpx,
        "AsyncClient",
        lambda **kwargs: FakeAsyncClient(response),
    )

    adapter = OpenAIAdapter("key", "https://example.com/v1", "model")
    chunks = [chunk async for chunk in adapter.chat([{"role": "user", "content": "hello"}])]

    assert [chunk.content for chunk in chunks] == ["jsonl", " +sse"]


@pytest.mark.asyncio
async def test_openai_adapter_reports_non_openai_stream_response(monkeypatch):
    from agent.models import openai_adapter as adapter_module
    from agent.models.openai_adapter import OpenAIAdapter

    import asyncio

    async def no_sleep(_):
        return None

    response = FakeStreamResponse(
        ["upstream gateway is unavailable"],
        headers={"content-type": "text/plain; charset=utf-8"},
    )
    monkeypatch.setattr(adapter_module.httpx, "AsyncClient", lambda **kwargs: FakeAsyncClient(response))
    monkeypatch.setattr(asyncio, "sleep", no_sleep)

    adapter = OpenAIAdapter("key", "https://example.com/v1", "model")
    chunks = [chunk async for chunk in adapter.chat([{"role": "user", "content": "hello"}])]

    assert len(chunks) == 1
    assert "兼容性错误" in chunks[0].content
    assert "text/plain" in chunks[0].content
    assert "upstream gateway is unavailable" in chunks[0].content


@pytest.mark.asyncio
async def test_openai_adapter_normalizes_full_endpoint_url(monkeypatch):
    from agent.models import openai_adapter as adapter_module
    from agent.models.openai_adapter import OpenAIAdapter

    captured = {}
    response = FakeStreamResponse(["data: [DONE]"])

    class CapturingClient(FakeAsyncClient):
        def stream(self, *args, **kwargs):
            captured["url"] = args[1]
            return self.response

    monkeypatch.setattr(
        adapter_module.httpx,
        "AsyncClient",
        lambda **kwargs: CapturingClient(response),
    )

    adapter = OpenAIAdapter(
        "key",
        "https://example.com/v1/chat/completions",
        "model",
    )
    _ = [chunk async for chunk in adapter.chat([{"role": "user", "content": "hello"}])]

    assert captured["url"] == "https://example.com/v1/chat/completions"


@pytest.mark.asyncio
async def test_openai_adapter_streams_reasoning_separately(monkeypatch):
    from agent.models import openai_adapter as adapter_module
    from agent.models.openai_adapter import OpenAIAdapter

    response = FakeStreamResponse([
        'data: {"choices":[{"delta":{"reasoning_content":"先分析"}}]}',
        'data: {"choices":[{"delta":{"content":"最终答案"}}]}',
        'data: [DONE]',
    ])
    monkeypatch.setattr(adapter_module.httpx, "AsyncClient", lambda **kwargs: FakeAsyncClient(response))

    adapter = OpenAIAdapter("key", "https://example.com/v1", "deepseek-reasoner")
    chunks = [chunk async for chunk in adapter.chat([{"role": "user", "content": "hello"}])]

    assert chunks[0].reasoning_content == "先分析"
    assert chunks[0].content == ""
    assert chunks[1].content == "最终答案"
    assert chunks[1].reasoning_content == ""


@pytest.mark.asyncio
async def test_openai_reasoning_request_uses_supported_parameters(monkeypatch):
    from agent.models import openai_adapter as adapter_module
    from agent.models.openai_adapter import OpenAIAdapter

    captured = {}
    response = FakeStreamResponse(['data: [DONE]'])

    class CapturingClient(FakeAsyncClient):
        def stream(self, *args, **kwargs):
            captured.update(kwargs)
            return self.response

    monkeypatch.setattr(adapter_module.httpx, "AsyncClient", lambda **kwargs: CapturingClient(response))

    adapter = OpenAIAdapter(
        "key",
        "https://api.openai.com/v1",
        "o3",
        provider_id="openai",
        reasoning_available=True,
    )
    _ = [chunk async for chunk in adapter.chat(
        [{"role": "user", "content": "hello"}],
        temperature=0.8,
        top_p=0.9,
        max_tokens=2048,
        reasoning_enabled=True,
        reasoning_effort="high",
    )]

    payload = captured["json"]
    assert payload["reasoning_effort"] == "high"
    assert payload["max_completion_tokens"] == 2048
    assert "max_tokens" not in payload
    assert "temperature" not in payload
    assert "top_p" not in payload


@pytest.mark.asyncio
async def test_openai_adapter_falls_back_to_direct_connection(monkeypatch):
    from agent.models import openai_adapter as adapter_module
    from agent.models.openai_adapter import OpenAIAdapter

    trust_env_values = []
    response = FakeStreamResponse([
        'data: {"choices":[{"delta":{"content":"connected"}}]}',
        'data: [DONE]',
    ])

    class ProxyFailureStream:
        async def __aenter__(self):
            raise adapter_module.httpx.ConnectError("proxy unavailable")

        async def __aexit__(self, *args):
            return False

    class NetworkClient(FakeAsyncClient):
        def __init__(self, trust_env=True, **kwargs):
            super().__init__(response)
            self.trust_env = trust_env
            trust_env_values.append(trust_env)

        def stream(self, *args, **kwargs):
            if self.trust_env:
                return ProxyFailureStream()
            return self.response

    monkeypatch.setattr(adapter_module.httpx, "AsyncClient", NetworkClient)

    adapter = OpenAIAdapter("key", "https://stream-fallback.example/v1", "model")
    chunks = [chunk async for chunk in adapter.chat([{"role": "user", "content": "hello"}])]

    assert [chunk.content for chunk in chunks] == ["connected"]
    assert trust_env_values == [True, False]

    second_adapter = OpenAIAdapter("key", "https://stream-fallback.example/v1", "model")
    second_chunks = [
        chunk
        async for chunk in second_adapter.chat([{"role": "user", "content": "hello again"}])
    ]
    assert [chunk.content for chunk in second_chunks] == ["connected"]
    assert trust_env_values == [True, False, False]


@pytest.mark.asyncio
async def test_openai_non_stream_falls_back_to_direct_connection(monkeypatch):
    from agent.models import openai_adapter as adapter_module
    from agent.models.openai_adapter import OpenAIAdapter

    trust_env_values = []

    class ChatResponse:
        status_code = 200

        def json(self):
            return {
                "choices": [{
                    "message": {"content": "connected"},
                    "finish_reason": "stop",
                }],
            }

    class NetworkClient:
        def __init__(self, trust_env=True, **kwargs):
            self.trust_env = trust_env
            trust_env_values.append(trust_env)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, *args, **kwargs):
            if self.trust_env:
                raise adapter_module.httpx.ConnectError("proxy unavailable")
            return ChatResponse()

    monkeypatch.setattr(adapter_module.httpx, "AsyncClient", NetworkClient)

    adapter = OpenAIAdapter("key", "https://nonstream-fallback.example/v1", "model")
    chunks = [
        chunk
        async for chunk in adapter.chat(
            [{"role": "user", "content": "hello"}],
            stream=False,
        )
    ]

    assert [chunk.content for chunk in chunks] == ["connected"]
    assert trust_env_values == [True, False]


@pytest.mark.asyncio
async def test_openai_model_list_falls_back_to_direct_connection(monkeypatch):
    from agent.models import openai_adapter as adapter_module
    from agent.models.openai_adapter import OpenAIAdapter

    trust_env_values = []

    class ModelListResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"data": [{"id": "model-a"}]}

    class NetworkClient:
        def __init__(self, trust_env=True, **kwargs):
            self.trust_env = trust_env
            trust_env_values.append(trust_env)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, *args, **kwargs):
            if self.trust_env:
                raise adapter_module.httpx.ConnectError("proxy unavailable")
            return ModelListResponse()

    monkeypatch.setattr(adapter_module.httpx, "AsyncClient", NetworkClient)

    adapter = OpenAIAdapter("key", "https://models-fallback.example/v1", "model")

    assert await adapter.list_models() == ["model-a"]
    assert trust_env_values == [True, False]


@pytest.mark.asyncio
async def test_mimo_disables_thinking_and_prefers_direct_connection(monkeypatch):
    from agent.models import openai_adapter as adapter_module
    from agent.models.openai_adapter import OpenAIAdapter

    captured = {}
    response = FakeStreamResponse([
        'data: {"choices":[{"delta":{"content":"fast"}}]}',
        'data: [DONE]',
    ])

    class CapturingClient(FakeAsyncClient):
        def __init__(self, **kwargs):
            super().__init__(response)
            captured["client"] = kwargs

        def stream(self, *args, **kwargs):
            captured["request"] = kwargs
            return self.response

    monkeypatch.setattr(adapter_module.httpx, "AsyncClient", CapturingClient)

    adapter = OpenAIAdapter(
        "key",
        "https://token-plan-cn.xiaomimimo.com/v1",
        "mimo-v2.5-pro",
    )
    chunks = [chunk async for chunk in adapter.chat([{"role": "user", "content": "hello"}])]

    assert [chunk.content for chunk in chunks] == ["fast"]
    assert captured["client"]["trust_env"] is False
    assert captured["request"]["json"]["thinking"] == {"type": "disabled"}
