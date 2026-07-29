import pytest
import asyncio
from agent.models.base import BaseModelAdapter, ModelResponse

def test_model_response_dataclass():
    r = ModelResponse(content="hello")
    assert r.content == "hello"
    assert r.tool_calls == []
    assert r.finish_reason == "stop"

def test_openai_adapter_init():
    from agent.models.openai_adapter import OpenAIAdapter
    adapter = OpenAIAdapter(api_key="test", base_url="https://api.openai.com/v1", model_name="gpt-4")
    assert adapter.model_name == "gpt-4"
    assert adapter.base_url == "https://api.openai.com/v1"


class FakeStreamResponse:
    def __init__(self, lines, release=None):
        self.status_code = 200
        self._lines = lines
        self._release = release

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def aiter_lines(self):
        for index, line in enumerate(self._lines):
            yield line
            if index == 0 and self._release:
                await self._release.wait()


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
