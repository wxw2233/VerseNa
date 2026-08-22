import pytest
import pytest_asyncio
import asyncio
import json
from types import SimpleNamespace
from agent.react import ReActAgent
from agent.models.base import BaseModelAdapter, ModelResponse
from agent.memory import MemoryManager
from agent.diagnostics import runtime_diagnostics
from db.database import db
from tools.registry import ToolRegistry
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


@pytest.mark.asyncio
async def test_long_tool_loop_compacts_instead_of_ending_on_message_count():
    class LongRunningAdapter(BaseModelAdapter):
        def __init__(self):
            self.calls = 0

        async def chat(self, messages, tools=None, stream=True, **kwargs):
            self.calls += 1
            if self.calls <= 25:
                yield ModelResponse(tool_calls=[{
                    "id": f"tool-{self.calls}",
                    "type": "function",
                    "function": {
                        "name": "counter",
                        "arguments": json.dumps({"index": self.calls}),
                    },
                }])
            else:
                yield ModelResponse(content="long task completed")

        async def list_models(self):
            return ["long-running-model"]

    class Registry:
        def create_context(self, session_id, **kwargs):
            return object()

        async def execute(self, name, arguments, **kwargs):
            return json.dumps({"success": True, "data": {"index": arguments["index"]}})

    events = [event async for event in ReActAgent(
        LongRunningAdapter(), MemoryManager(), tool_registry=Registry(),
    ).run(
        "long-tool-loop",
        "finish the long task",
        tools=[{}],
        agent_config={"max_steps": 30, "max_context": 1_000_000},
    )]

    assert runtime_diagnostics.snapshot("long-tool-loop")["last_compaction"]["reason"] == "tool_loop_message_count"
    assert any(
        event.get("segment", {}).get("content") == "long task completed"
        for event in events
    )
    assert not any("对话过长" in event.get("segment", {}).get("content", "") for event in events)


@pytest.mark.asyncio
async def test_long_tool_loop_stops_only_when_requested():
    stop_event = asyncio.Event()

    class LongToolAdapter(BaseModelAdapter):
        def __init__(self):
            self.calls = 0

        async def chat(self, messages, tools=None, stream=True, **kwargs):
            self.calls += 1
            yield ModelResponse(tool_calls=[{
                "id": f"loop-tool-{self.calls}",
                "type": "function",
                "function": {"name": "counter", "arguments": json.dumps({"index": self.calls})},
            }])

        async def list_models(self):
            return ["endless-tool-model"]

    class Registry:
        def create_context(self, session_id, **kwargs):
            return object()

        async def execute(self, name, arguments, **kwargs):
            if arguments["index"] >= 4:
                stop_event.set()
            return json.dumps({"success": True, "data": {"ok": True}})

    events = [event async for event in ReActAgent(
        LongToolAdapter(), MemoryManager(), tool_registry=Registry(),
    ).run(
        "unlimited-loop",
        "continue until the stop signal arrives",
        tools=[{}],
        stop_event=stop_event,
        agent_config={"max_steps": 1},
    )]

    assert events[-1]["type"] == "done"
    assert events[-1]["finish_reason"] == "stopped"


def test_tool_result_context_is_bounded_without_losing_result_ends():
    result = "start" + ("x" * 20_000) + "end"

    compacted = ReActAgent._tool_result_for_context(result)

    assert len(compacted) < len(result)
    assert compacted.startswith("start")
    assert compacted.endswith("end")
    assert "truncated for context" in compacted


def test_tool_result_context_uses_configured_limit():
    result = "start" + ("x" * 20_000) + "end"

    compacted = ReActAgent._tool_result_for_context(result, 16_000)

    assert len(compacted) < 16_100
    assert compacted.startswith("start")
    assert compacted.endswith("end")


def test_untrusted_large_tool_result_keeps_compatible_status_fields():
    from agent.context_protocol import format_untrusted_tool_output

    framed = json.loads(format_untrusted_tool_output(
        {"success": True, "data": {"output": "x" * 50_000}, "message": "done"},
        source="code_exec",
        max_chars=1200,
    ))

    assert framed["success"] is True
    assert framed["status"] == "success"
    assert framed["truncated"] is True
    assert framed["_versena_context"]["untrusted"] is True


def test_untrusted_partial_read_keeps_continuation_fields():
    from agent.context_protocol import format_untrusted_tool_output

    framed = json.loads(format_untrusted_tool_output(
        {
            "success": True,
            "data": {
                "path": "large.txt",
                "output": "x" * 50_000,
                "next_offset": 12_345,
                "remaining_bytes": 50_000,
                "eof": False,
            },
        },
        source="file_manager",
        max_chars=2_000,
    ))

    assert framed["truncated"] is True
    assert framed["data"]["next_offset"] == 12_345
    assert framed["data"]["eof"] is False


@pytest.mark.parametrize("limit", [512, 800, 1200, 2000])
def test_untrusted_tool_result_never_exceeds_configured_limit(limit):
    from agent.context_protocol import format_untrusted_tool_output

    encoded = format_untrusted_tool_output(
        {
            "success": False,
            "error": "PROCESS_EXIT",
            "message": "m" * 10_000,
            "data": {"output": "x" * 50_000, "exit_code": 1},
        },
        source="code_exec",
        max_chars=limit,
    )

    assert len(encoded) <= limit
    framed = json.loads(encoded)
    assert framed["_versena_context"]["untrusted"] is True

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
async def test_reasoning_chunks_are_hidden_when_reasoning_is_disabled():
    class UnexpectedReasoningAdapter(BaseModelAdapter):
        model_name = "hybrid-model"
        reasoning_available = True

        async def chat(self, messages, tools=None, stream=True, reasoning_enabled=False, **kwargs):
            assert reasoning_enabled is False
            yield ModelResponse(reasoning_content="hidden analysis")
            yield ModelResponse(content="answer")

        async def list_models(self):
            return [self.model_name]

    events = [event async for event in ReActAgent(
        UnexpectedReasoningAdapter(), MemoryManager()
    ).run(
        "reasoning-disabled-session",
        "simple request",
        agent_config={"reasoning_enabled": False},
    )]

    segments = [event.get("segment", {}) for event in events]
    assert not any(segment.get("type") == "reasoning" for segment in segments)
    assert "".join(
        segment.get("content", "")
        for segment in segments
        if segment.get("type") == "text"
    ) == "answer"
    assert events[-1]["reasoning_enabled"] is False


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


@pytest.mark.asyncio
async def test_code_exec_results_are_not_reused_between_identical_calls():
    tool_call = {
        "id": "call_exec",
        "type": "function",
        "function": {"name": "code_exec", "arguments": '{"language":"python","code":"print(1)"}'},
    }

    class RepeatingAdapter(BaseModelAdapter):
        def __init__(self):
            self.calls = 0

        async def chat(self, messages, tools=None, stream=True, **kwargs):
            self.calls += 1
            if self.calls <= 2:
                yield ModelResponse(tool_calls=[tool_call])
            else:
                yield ModelResponse(content="完成")

        async def list_models(self):
            return ["exec-model"]

    class CountingRegistry:
        def __init__(self):
            self.executions = 0

        def create_context(self, session_id, **kwargs):
            return object()

        async def execute(self, name, arguments, **kwargs):
            self.executions += 1
            return json.dumps({"success": True, "data": {"output": str(self.executions)}})

    registry = CountingRegistry()
    events = [event async for event in ReActAgent(
        RepeatingAdapter(), MemoryManager(), tool_registry=registry
    ).run("exec-repeat-session", "执行验证", tools=[{}])]

    assert registry.executions == 2


@pytest.mark.asyncio
async def test_intermediate_text_is_kept_out_of_saved_final_answer():
    tool_call = {
        "id": "call_intermediate",
        "type": "function",
        "function": {"name": "counter", "arguments": '{"value": 1}'},
    }

    class StagedAdapter(BaseModelAdapter):
        def __init__(self):
            self.calls = 0

        async def chat(self, messages, tools=None, stream=True, **kwargs):
            self.calls += 1
            if self.calls == 1:
                yield ModelResponse(content="阶段性说明", tool_calls=[tool_call])
            else:
                yield ModelResponse(content="最终总结")

        async def list_models(self):
            return ["staged-model"]

    class Registry:
        def create_context(self, session_id, **kwargs):
            return object()

        async def execute(self, name, arguments, **kwargs):
            return json.dumps({"success": True, "data": {"value": arguments["value"]}})

    events = [event async for event in ReActAgent(
        StagedAdapter(),
        MemoryManager(),
        tool_registry=Registry(),
    ).run("staged-session", "执行", tools=[{}])]

    text = "".join(
        event["segment"].get("content", "")
        for event in events
        if event.get("segment", {}).get("type") == "text"
    )
    assert text == "阶段性说明最终总结"

    history = await db.get_history("staged-session")
    assistant = next(message for message in history if message["role"] == "assistant")
    assert assistant["content"] == "最终总结"


@pytest.mark.asyncio
async def test_executor_result_requires_main_agent_verification(tmp_path):
    modified = str((tmp_path / "changed.txt").resolve())

    class VerificationAdapter(BaseModelAdapter):
        def __init__(self):
            self.calls = 0
            self.gate_seen = False

        async def chat(self, messages, tools=None, stream=True, **kwargs):
            self.calls += 1
            if self.calls == 1:
                yield ModelResponse(tool_calls=[{
                    "id": "delegate-executor",
                    "type": "function",
                    "function": {
                        "name": "delegate_task",
                        "arguments": json.dumps({"role": "executor", "task": "修改文件"}),
                    },
                }])
            elif self.calls == 2:
                yield ModelResponse(content="executor 说已经完成，可以直接交付。")
            elif self.calls == 3:
                self.gate_seen = "系统验收门" in messages[-1]["content"]
                yield ModelResponse(tool_calls=[{
                    "id": "verify-file",
                    "type": "function",
                    "function": {
                        "name": "file_manager",
                        "arguments": json.dumps({"action": "read", "path": "changed.txt"}),
                    },
                }])
            else:
                yield ModelResponse(content="已读取真实改动，验收完成。")

        async def list_models(self):
            return ["verification-model"]

    class VerificationRegistry:
        def create_context(self, session_id, **kwargs):
            return SimpleNamespace(workspace=tmp_path)

        async def execute(self, name, arguments, **kwargs):
            if name == "delegate_task":
                return json.dumps({
                    "type": "subagent_result",
                    "success": True,
                    "data": {
                        "role": "executor",
                        "status": "done",
                        "evidence": {"modified_files": [modified]},
                    },
                }, ensure_ascii=False)
            return json.dumps({
                "success": True,
                "data": {"path": modified, "content": "changed"},
            }, ensure_ascii=False)

    adapter = VerificationAdapter()
    events = [event async for event in ReActAgent(
        adapter,
        MemoryManager(),
        tool_registry=VerificationRegistry(),
    ).run("executor-verification", "完成修改", tools=[{}])]

    assert adapter.calls == 4
    assert adapter.gate_seen is True
    assert any(
        event.get("segment", {}).get("content") == "已读取真实改动，验收完成。"
        for event in events
    )
    history = await db.get_history("executor-verification")
    assistant = next(message for message in history if message["role"] == "assistant")
    assert assistant["content"] == "已读取真实改动，验收完成。"


@pytest.mark.asyncio
async def test_delegate_plan_validation_failure_is_repaired_once_and_retried():
    invalid_nodes = [
        {"id": "setup", "role": "executor", "task": "创建文件", "depends_on": []},
        {
            "id": "verify",
            "role": "reviewer",
            "task": "运行 pytest 验证",
            "depends_on": ["setup"],
        },
    ]
    corrected_nodes = [
        invalid_nodes[0],
        {**invalid_nodes[1], "role": "verifier"},
    ]

    class RepairAdapter(BaseModelAdapter):
        def __init__(self):
            self.calls = 0
            self.repair_prompt = ""

        async def chat(self, messages, tools=None, stream=True, **kwargs):
            self.calls += 1
            if self.calls == 1:
                nodes = invalid_nodes
            elif self.calls == 2:
                self.repair_prompt = messages[-1]["content"]
                nodes = corrected_nodes
            else:
                yield ModelResponse(content="计划已自动修正并完成。")
                return
            yield ModelResponse(tool_calls=[{
                "id": f"plan-{self.calls}",
                "type": "function",
                "function": {
                    "name": "delegate_plan",
                    "arguments": json.dumps({"nodes": nodes}, ensure_ascii=False),
                },
            }])

        async def list_models(self):
            return ["repair-model"]

    class RepairRegistry:
        def __init__(self):
            self.executions = []

        def create_context(self, session_id, **kwargs):
            return object()

        async def execute(self, name, arguments, **kwargs):
            self.executions.append(arguments["nodes"])
            if len(self.executions) == 1:
                return json.dumps({
                    "success": False,
                    "error": "SUBAGENT_VERIFIER_ROLE_REQUIRED",
                    "message": "动态验证必须使用 verifier",
                    "data": {
                        "repair": {
                            "retryable": True,
                            "max_retries": 1,
                            "failed_error": "SUBAGENT_VERIFIER_ROLE_REQUIRED",
                            "failed_nodes": invalid_nodes,
                            "requirements": ["动态验收使用 verifier"],
                        },
                    },
                }, ensure_ascii=False)
            return json.dumps({
                "type": "subagent_plan_result",
                "success": True,
                "data": {
                    "status": "done",
                    "nodes": corrected_nodes,
                    "evidence": {"modified_files": []},
                },
            }, ensure_ascii=False)

    adapter = RepairAdapter()
    registry = RepairRegistry()
    events = [event async for event in ReActAgent(
        adapter, MemoryManager(), tool_registry=registry,
    ).run("plan-auto-repair", "执行计划", tools=[{}])]

    assert adapter.calls == 3
    assert len(registry.executions) == 2
    assert registry.executions[0][1]["role"] == "reviewer"
    assert registry.executions[1][1]["role"] == "verifier"
    assert "系统计划修正门" in adapter.repair_prompt
    assert "唯一一次自动修正机会" in adapter.repair_prompt
    assert any(
        event.get("segment", {}).get("content") == "计划已自动修正并完成。"
        for event in events
    )


@pytest.mark.asyncio
async def test_delegate_plan_auto_repair_stops_after_second_validation_failure():
    class RepeatedInvalidAdapter(BaseModelAdapter):
        def __init__(self):
            self.calls = 0
            self.second_prompt_has_gate = False
            self.third_prompt_has_gate = False

        async def chat(self, messages, tools=None, stream=True, **kwargs):
            self.calls += 1
            if self.calls == 2:
                self.second_prompt_has_gate = "系统计划修正门" in messages[-1]["content"]
            if self.calls == 3:
                self.third_prompt_has_gate = "系统计划修正门" in messages[-1]["content"]
                yield ModelResponse(content="计划仍然无效，停止自动重试。")
                return
            yield ModelResponse(tool_calls=[{
                "id": f"invalid-plan-{self.calls}",
                "type": "function",
                "function": {
                    "name": "delegate_plan",
                    "arguments": json.dumps({
                        "nodes": [
                            {"id": "a", "role": "explorer", "task": "A", "depends_on": ["missing"]},
                            {"id": "b", "role": "reviewer", "task": "B", "depends_on": ["a"]},
                        ],
                    }),
                },
            }])

        async def list_models(self):
            return ["invalid-repair-model"]

    class AlwaysInvalidRegistry:
        def __init__(self):
            self.executions = 0

        def create_context(self, session_id, **kwargs):
            return object()

        async def execute(self, name, arguments, **kwargs):
            self.executions += 1
            return json.dumps({
                "success": False,
                "error": "UNKNOWN_SUBAGENT_DEPENDENCY",
                "message": "节点 a 依赖不存在: missing",
                "data": {
                    "repair": {
                        "retryable": True,
                        "max_retries": 1,
                        "failed_error": "UNKNOWN_SUBAGENT_DEPENDENCY",
                        "requirements": ["依赖 ID 必须存在"],
                    },
                },
            }, ensure_ascii=False)

    adapter = RepeatedInvalidAdapter()
    registry = AlwaysInvalidRegistry()
    events = [event async for event in ReActAgent(
        adapter, MemoryManager(), tool_registry=registry,
    ).run("plan-repair-limit", "执行计划", tools=[{}])]

    assert registry.executions == 2
    assert adapter.calls == 3
    assert adapter.second_prompt_has_gate is True
    assert adapter.third_prompt_has_gate is False
    assert any(
        event.get("segment", {}).get("content") == "计划仍然无效，停止自动重试。"
        for event in events
    )


@pytest.mark.asyncio
async def test_delegate_plan_repair_gate_skips_remaining_tool_calls_in_same_batch():
    class BatchAdapter(BaseModelAdapter):
        def __init__(self):
            self.calls = 0
            self.skipped_result_seen = False

        async def chat(self, messages, tools=None, stream=True, **kwargs):
            self.calls += 1
            if self.calls == 1:
                yield ModelResponse(tool_calls=[
                    {
                        "id": "invalid-plan",
                        "type": "function",
                        "function": {
                            "name": "delegate_plan",
                            "arguments": json.dumps({"nodes": [
                                {"id": "a", "role": "explorer", "task": "A", "depends_on": ["missing"]},
                                {"id": "b", "role": "reviewer", "task": "B", "depends_on": ["a"]},
                            ]}),
                        },
                    },
                    {
                        "id": "must-not-run",
                        "type": "function",
                        "function": {
                            "name": "code_exec",
                            "arguments": json.dumps({"language": "python", "code": "print('unsafe')"}),
                        },
                    },
                ])
                return
            self.skipped_result_seen = any(
                message.get("role") == "tool"
                and "SKIPPED_DUE_TO_PLAN_REPAIR" in message.get("content", "")
                for message in messages
            )
            yield ModelResponse(content="停止批次并等待重建计划。")

        async def list_models(self):
            return ["batch-repair-model"]

    class BatchRegistry:
        def __init__(self):
            self.names = []

        def create_context(self, session_id, **kwargs):
            return object()

        async def execute(self, name, arguments, **kwargs):
            self.names.append(name)
            return json.dumps({
                "success": False,
                "error": "UNKNOWN_SUBAGENT_DEPENDENCY",
                "data": {"repair": {
                    "retryable": True,
                    "max_retries": 1,
                    "failed_error": "UNKNOWN_SUBAGENT_DEPENDENCY",
                    "requirements": ["依赖 ID 必须存在"],
                }},
            }, ensure_ascii=False)

    adapter = BatchAdapter()
    registry = BatchRegistry()
    events = [event async for event in ReActAgent(
        adapter, MemoryManager(), tool_registry=registry,
    ).run("plan-repair-batch", "执行计划", tools=[{}])]

    assert registry.names == ["delegate_plan"]
    assert adapter.skipped_result_seen is True
    history = await db.get_history("plan-repair-batch")
    assistant = next(message for message in history if message["role"] == "assistant")
    assert "自动修正计划未完成" in assistant["content"]


@pytest.mark.asyncio
async def test_choice_tool_emits_clickable_segment_and_waits_for_user():
    tool_call = {
        "id": "call_choice",
        "type": "function",
        "function": {
            "name": "ask_user_choice",
            "arguments": json.dumps({
                "question": "主要用途是什么？",
                "options": [
                    {"label": "自己学习"},
                    {"label": "课堂演示"},
                ],
            }, ensure_ascii=False),
        },
    }

    class ChoiceAdapter(BaseModelAdapter):
        def __init__(self):
            self.calls = 0

        async def chat(self, messages, tools=None, stream=True, **kwargs):
            self.calls += 1
            yield ModelResponse(content="先确认一下。", tool_calls=[tool_call])

        async def list_models(self):
            return ["choice-model"]

    registry = ToolRegistry()
    registry.load_builtins()
    adapter = ChoiceAdapter()
    events = [event async for event in ReActAgent(
        adapter,
        MemoryManager(),
        tool_registry=registry,
    ).run("choice-session", "帮我设计", tools=registry.get_tools())]

    choices = [
        event["segment"] for event in events
        if event.get("segment", {}).get("type") == "choice"
    ]
    tool_segments = [
        event["segment"] for event in events
        if event.get("segment", {}).get("type") == "tool"
    ]

    assert adapter.calls == 1
    assert len(choices) == 1
    assert choices[0]["question"] == "主要用途是什么？"
    assert [option["id"] for option in choices[0]["options"]] == ["A", "B"]
    assert tool_segments == []

    history = await db.get_history("choice-session")
    assistant = next(message for message in history if message["role"] == "assistant")
    assert "先确认一下。" in assistant["content"]
    assert "A：自己学习" in assistant["content"]


@pytest.mark.asyncio
async def test_stop_cancels_active_tool_and_skips_remaining_calls():
    tool_calls = [
        {
            "id": f"call_{index}",
            "type": "function",
            "function": {"name": "blocking", "arguments": json.dumps({"index": index})},
        }
        for index in range(2)
    ]

    class ToolCallingAdapter(BaseModelAdapter):
        async def chat(self, messages, tools=None, stream=True, **kwargs):
            yield ModelResponse(tool_calls=tool_calls)

        async def list_models(self):
            return ["tool-model"]

    class BlockingRegistry:
        def __init__(self):
            self.executions = []
            self.cancelled = False

        def create_context(self, session_id, **kwargs):
            return object()

        async def execute(self, name, arguments, **kwargs):
            self.executions.append(arguments["index"])
            try:
                await asyncio.Event().wait()
            finally:
                self.cancelled = True

    registry = BlockingRegistry()
    stop_event = asyncio.Event()
    stream = ReActAgent(
        ToolCallingAdapter(),
        MemoryManager(),
        tool_registry=registry,
    ).run(
        "stop-tool-session",
        "run tools",
        tools=[{}],
        stop_event=stop_event,
    )

    running = await anext(stream)
    assert running["segment"]["type"] == "tool"
    assert running["segment"]["status"] == "running"

    async def collect_remaining():
        return [event async for event in stream]

    remaining_task = asyncio.create_task(collect_remaining())
    await asyncio.sleep(0.05)
    assert registry.executions == [0]
    stop_event.set()
    remaining = await asyncio.wait_for(remaining_task, timeout=1)
    assert registry.executions == [0]
    assert registry.cancelled is True
    assert any(
        "已停止" in event.get("segment", {}).get("content", "")
        for event in remaining
    )


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
