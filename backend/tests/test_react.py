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


@pytest.mark.asyncio
async def test_reasoning_is_streamed_separately_and_not_saved_as_answer():
    class ReasoningAdapter(BaseModelAdapter):
        model_name = "reasoning-model"
        reasoning_available = True

        async def chat(self, messages, tools=None, stream=True, reasoning_enabled=False, reasoning_effort="medium"):
            assert reasoning_enabled is True
            assert reasoning_effort == "high"
            yield ModelResponse(reasoning_content="内部分析")
            yield ModelResponse(content="最终回答")

        async def list_models(self):
            return [self.model_name]

    agent = ReActAgent(ReasoningAdapter(), MemoryManager())
    events = [event async for event in agent.run(
        "reasoning-session",
        "复杂问题",
        agent_config={"reasoning_enabled": True, "reasoning_effort": "high"},
    )]

    reasoning = [event["segment"] for event in events if event.get("segment", {}).get("type") == "reasoning"]
    text = [event["segment"] for event in events if event.get("segment", {}).get("type") == "text"]
    assert "内部分析" in "".join(segment.get("content", "") for segment in reasoning)
    assert "".join(segment["content"] for segment in text) == "最终回答"
    assert reasoning[-1]["status"] == "done"

    history = await db.get_history("reasoning-session")
    assistant = next(message for message in history if message["role"] == "assistant")
    assert assistant["content"] == "最终回答"
    assert "内部分析" not in assistant["content"]
