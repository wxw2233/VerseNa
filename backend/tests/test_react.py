import pytest
import pytest_asyncio
import asyncio
import json
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


@pytest.mark.asyncio
async def test_reasoning_is_detected_from_stream_when_capability_is_unknown():
    class DynamicReasoningAdapter(BaseModelAdapter):
        model_name = "custom-model"
        reasoning_available = False

        async def chat(self, messages, tools=None, stream=True, reasoning_enabled=False, **kwargs):
            assert reasoning_enabled is True
            yield ModelResponse(reasoning_content="实际推理")
            yield ModelResponse(content="回答")

        async def list_models(self):
            return [self.model_name]

    events = [event async for event in ReActAgent(
        DynamicReasoningAdapter(), MemoryManager()
    ).run(
        "dynamic-reasoning-session",
        "问题",
        agent_config={"reasoning_enabled": True},
    )]

    reasoning = [
        event["segment"] for event in events
        if event.get("segment", {}).get("type") == "reasoning"
    ]
    assert any(segment.get("content") == "实际推理" for segment in reasoning)
    assert not any(segment.get("status") == "unavailable" for segment in reasoning)
    assert events[-1]["reasoning_available"] is True


@pytest.mark.asyncio
async def test_unknown_model_is_marked_unavailable_only_after_response_finishes():
    class PlainAdapter(BaseModelAdapter):
        model_name = "plain-model"
        reasoning_available = False

        async def chat(self, messages, tools=None, stream=True, reasoning_enabled=False, **kwargs):
            yield ModelResponse(content="普通回答")

        async def list_models(self):
            return [self.model_name]

    events = [event async for event in ReActAgent(PlainAdapter(), MemoryManager()).run(
        "plain-reasoning-session",
        "问题",
        agent_config={"reasoning_enabled": True},
    )]
    unavailable_index = next(
        index for index, event in enumerate(events)
        if event.get("segment", {}).get("status") == "unavailable"
    )
    answer_index = next(
        index for index, event in enumerate(events)
        if event.get("segment", {}).get("type") == "text"
    )
    assert unavailable_index > answer_index
    assert events[-1]["reasoning_available"] is False


@pytest.mark.asyncio
async def test_identical_tool_call_reuses_result_without_second_execution(tmp_path):
    tool_call = {
        "id": "call_1",
        "type": "function",
        "function": {"name": "counter", "arguments": '{"value": 1}'},
    }

    class RepeatingAdapter(BaseModelAdapter):
        model_name = "repeat-model"

        def __init__(self):
            self.calls = 0

        async def chat(self, messages, tools=None, stream=True, **kwargs):
            self.calls += 1
            if self.calls <= 2:
                yield ModelResponse(tool_calls=[tool_call])
            else:
                yield ModelResponse(content="完成")

        async def list_models(self):
            return [self.model_name]

    class CountingRegistry:
        def __init__(self):
            self.executions = 0

        def create_context(self, session_id, **kwargs):
            return object()

        async def execute(self, name, arguments, **kwargs):
            self.executions += 1
            return json.dumps({"success": True, "data": {"value": arguments["value"]}})

    registry = CountingRegistry()
    events = [event async for event in ReActAgent(
        RepeatingAdapter(), MemoryManager(), tool_registry=registry
    ).run("repeat-tool-session", "执行", tools=[{}])]

    assert registry.executions == 1
    tool_results = [
        event["segment"] for event in events
        if event.get("segment", {}).get("type") == "tool" and event["segment"].get("status") == "done"
    ]
    assert len(tool_results) == 2


def test_file_reads_must_follow_next_offset_and_stop_at_eof():
    progress = {"large.txt": {"next_offset": 50000, "eof": False}}
    wrong_offset = json.loads(ReActAgent._validate_read_continuation(
        "file_manager",
        {"action": "read", "path": "large.txt", "offset": 40000},
        progress,
    ))
    correct_offset = ReActAgent._validate_read_continuation(
        "file_manager",
        {"action": "read", "path": "large.txt", "offset": 50000},
        progress,
    )
    progress["large.txt"]["eof"] = True
    after_eof = json.loads(ReActAgent._validate_read_continuation(
        "file_manager",
        {"action": "read", "path": "large.txt", "offset": 50000},
        progress,
    ))

    assert wrong_offset["error"] == "READ_CONTINUATION_REQUIRED"
    assert correct_offset is None
    assert after_eof["error"] == "EOF_REACHED"
