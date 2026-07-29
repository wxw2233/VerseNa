import pytest
import pytest_asyncio
import asyncio
from agent.react import ReActAgent
from agent.models.base import BaseModelAdapter, ModelResponse
from agent.memory import MemoryManager
from db.database import db
from typing import AsyncGenerator

class MockAdapter(BaseModelAdapter):
    def __init__(self, responses):
        self.responses = responses
        self.call_count = 0

    async def chat(self, messages, tools=None, stream=True) -> AsyncGenerator:
        resp = self.responses[self.call_count]
        self.call_count += 1
        yield ModelResponse(content=resp)

    async def list_models(self):
        return ["mock-model"]

@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    """Initialize in-memory database for tests."""
    db.db_path = ":memory:"
    await db.connect()
    yield
    await db.close()

@pytest.mark.asyncio
async def test_react_simple_response():
    adapter = MockAdapter(["你好！我是次元人格。"])
    memory = MemoryManager()
    agent = ReActAgent(adapter, memory)

    results = []
    async for event in agent.run("test-session", "你好"):
        results.append(event)

    answers = [r for r in results if r["type"] == "segment" and r["segment"]["type"] == "text"]
    assert len(answers) > 0
    assert "你好" in "".join(r["segment"]["content"] for r in answers)


@pytest.mark.asyncio
async def test_stop_interrupts_active_model_stream():
    class SlowAdapter(BaseModelAdapter):
        def __init__(self):
            self.closed = False
            self.wait_forever = asyncio.Event()

        async def chat(self, messages, tools=None, stream=True):
            try:
                yield ModelResponse(content="first")
                await self.wait_forever.wait()
                yield ModelResponse(content="late")
            finally:
                self.closed = True

        async def list_models(self):
            return ["slow-model"]

    adapter = SlowAdapter()
    agent = ReActAgent(adapter, MemoryManager())
    stop_event = asyncio.Event()
    stream = agent.run("stop-session", "please stop", stop_event=stop_event)

    first = await anext(stream)
    assert first["segment"]["content"] == "first"

    stop_event.set()
    remaining = [event async for event in stream]

    assert adapter.closed is True
    assert any("已停止" in event.get("segment", {}).get("content", "") for event in remaining)
    assert remaining[-1]["type"] == "done"
