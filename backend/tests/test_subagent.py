import asyncio
import json

import pytest

from agent.models.base import BaseModelAdapter, ModelResponse
from agent.subagent import SubagentManager
from tools.base import ToolContext


class ReportAdapter(BaseModelAdapter):
    async def chat(self, messages, tools=None, stream=True, **kwargs):
        yield ModelResponse(content="结论：目标实现位于 backend。\n\n证据：已检查结构。")

    async def list_models(self):
        return ["report-model"]


class CapturingReportAdapter(BaseModelAdapter):
    def __init__(self, report):
        self.report = report
        self.kwargs = {}

    async def chat(self, messages, tools=None, stream=True, **kwargs):
        self.kwargs = kwargs
        yield ModelResponse(content=self.report)

    async def list_models(self):
        return ["capturing-report-model"]


class ExecutorWriteAdapter(BaseModelAdapter):
    def __init__(self, path="executor.txt", content="written", verify=True):
        self.calls = 0
        self.path = path
        self.content = content
        self.verify = verify
        self.tool_result = ""
        self.tool_names = set()

    async def chat(self, messages, tools=None, stream=True, **kwargs):
        self.calls += 1
        self.tool_names = {tool["function"]["name"] for tool in tools or []}
        if self.calls == 1:
            yield ModelResponse(tool_calls=[{
                "id": "executor-write",
                "type": "function",
                "function": {
                    "name": "file_manager",
                    "arguments": json.dumps({
                        "action": "write",
                        "path": self.path,
                        "content": self.content,
                    }),
                },
            }])
            return
        if self.calls == 2 and self.verify:
            self.tool_result = messages[-1]["content"]
            yield ModelResponse(tool_calls=[{
                "id": "executor-read",
                "type": "function",
                "function": {
                    "name": "file_manager",
                    "arguments": json.dumps({
                        "action": "read",
                        "path": self.path,
                    }),
                },
            }])
            return
        self.tool_result = messages[-1]["content"]
        yield ModelResponse(content="已完成执行并检查工具结果。")

    async def list_models(self):
        return ["executor-model"]


class ExecutorCommandAdapter(BaseModelAdapter):
    async def chat(self, messages, tools=None, stream=True, **kwargs):
        yield ModelResponse(tool_calls=[{
            "id": "executor-command",
            "type": "function",
            "function": {
                "name": "code_exec",
                "arguments": json.dumps({
                    "language": "python",
                    "code": "import time; time.sleep(10)",
                    "timeout": 20,
                }),
            },
        }])

    async def list_models(self):
        return ["executor-command-model"]


class VerifierRetryAdapter(BaseModelAdapter):
    def __init__(self):
        self.calls = 0
        self.tool_names = set()

    async def chat(self, messages, tools=None, stream=True, **kwargs):
        self.calls += 1
        self.tool_names = {tool["function"]["name"] for tool in tools or []}
        if self.calls <= 2:
            command = (
                "python -m unittest definitely_missing_test_module"
                if self.calls == 1
                else "python -m unittest"
            )
            yield ModelResponse(tool_calls=[{
                "id": f"verify-{self.calls}",
                "type": "function",
                "function": {
                    "name": "verification_exec",
                    "arguments": json.dumps({
                        "code": command,
                        "check_id": "unit_tests",
                    }),
                },
            }])
            return
        yield ModelResponse(content="动态验证已通过。")

    async def list_models(self):
        return ["verifier-model"]


class EmptyVerifierAdapter(BaseModelAdapter):
    def __init__(self):
        self.calls = 0

    async def chat(self, messages, tools=None, stream=True, **kwargs):
        self.calls += 1
        if self.calls == 1:
            yield ModelResponse(tool_calls=[{
                "id": "verify-empty",
                "type": "function",
                "function": {
                    "name": "verification_exec",
                    "arguments": json.dumps({
                        "code": "python -m unittest",
                        "check_id": "unit_tests",
                    }),
                },
            }])
            return
        yield ModelResponse(content="命令退出码为零，但没有执行任何测试。")

    async def list_models(self):
        return ["verifier-empty-model"]


@pytest.mark.asyncio
async def test_subagent_returns_report_without_writing_memory(tmp_path):
    events = []

    async def progress(event):
        events.append(event)

    context = ToolContext(
        "session",
        tmp_path,
        model=ReportAdapter(),
        progress_callback=progress,
        agent_config={"max_tokens": 2048},
    )
    result = json.loads(await SubagentManager().run(
        role="explorer",
        task="定位实现",
        context=context,
    ))

    assert result["success"] is True
    assert "目标实现" in result["data"]["report"]
    subagent_segments = [event["segment"] for event in events]
    assert subagent_segments[0]["status"] == "running"
    assert subagent_segments[-1]["status"] == "done"
    assert subagent_segments[0]["subagent_id"] == subagent_segments[-1]["subagent_id"]


@pytest.mark.asyncio
async def test_subagent_output_and_report_limits_follow_advanced_settings(tmp_path):
    adapter = CapturingReportAdapter("x" * 80_000)
    context = ToolContext(
        "limits",
        tmp_path,
        model=adapter,
        agent_config={"subagent_max_tokens": 48_000, "subagent_report_max_chars": 70_000},
    )

    result = json.loads(await SubagentManager().run(
        role="explorer", task="report limits", context=context,
    ))

    assert adapter.kwargs["max_tokens"] == 48_000
    assert len(result["data"]["report"]) == 70_000


@pytest.mark.asyncio
async def test_verifier_without_dynamic_evidence_cannot_report_done(tmp_path):
    result = json.loads(await SubagentManager().run(
        role="verifier",
        task="运行测试并验证结果",
        context=ToolContext("verifier-empty", tmp_path, model=ReportAdapter()),
    ))

    assert result["success"] is False
    assert result["error"] == "NEEDS_VERIFICATION"
    assert result["data"]["status"] == "needs_verification"


@pytest.mark.asyncio
async def test_verifier_runs_restricted_command_and_resolves_corrected_attempt(tmp_path):
    tmp_path.joinpath("test_sample.py").write_text(
        "import unittest\n\nclass SampleTest(unittest.TestCase):\n    def test_ok(self):\n        self.assertTrue(True)\n",
        encoding="utf-8",
    )
    adapter = VerifierRetryAdapter()
    result = json.loads(await SubagentManager().run(
        role="verifier",
        task="运行 unittest 验证",
        context=ToolContext("verifier-retry", tmp_path, model=adapter),
    ))

    assert result["success"] is True
    assert result["data"]["status"] == "done"
    assert "verification_exec" in adapter.tool_names
    assert "code_exec" not in adapter.tool_names
    assert result["data"]["evidence"]["failures"] == []
    assert result["data"]["evidence"]["verifications"] == [
        "命令通过: python -m unittest"
    ]
    assert result["data"]["evidence"]["resolved_failures"] == [
        "已恢复: verification_exec: PROCESS_EXIT (python -m unittest definitely_missing_test_module)"
    ]
    assert result["data"]["evidence"]["verification_quality"][-1] == {
        "check_id": "unit_tests",
        "verification_kind": "python:unittest",
        "verification_quality": "meaningful",
        "tests_discovered": True,
        "tests_executed": 1,
        "test_count": 1,
    }


@pytest.mark.asyncio
async def test_verifier_marks_empty_test_suite_as_needs_attention(tmp_path):
    result = json.loads(await SubagentManager().run(
        role="verifier",
        task="运行 unittest 验证",
        context=ToolContext("verifier-empty-suite", tmp_path, model=EmptyVerifierAdapter()),
    ))

    assert result["success"] is False
    assert result["error"] == "NEEDS_ATTENTION"
    assert result["data"]["status"] == "needs_attention"
    assert result["data"]["evidence"]["verifications"] == []
    assert result["data"]["evidence"]["verification_quality"][0]["verification_quality"] == "empty"


@pytest.mark.asyncio
async def test_subagent_blocks_mutating_file_action(tmp_path):
    tool_call = {
        "id": "write-call",
        "type": "function",
        "function": {
            "name": "file_manager",
            "arguments": json.dumps({
                "action": "write",
                "path": "forbidden.txt",
                "content": "no",
            }),
        },
    }

    class MutatingAdapter(BaseModelAdapter):
        def __init__(self):
            self.calls = 0
            self.tool_result = ""

        async def chat(self, messages, tools=None, stream=True, **kwargs):
            self.calls += 1
            if self.calls == 1:
                file_tool = next(tool for tool in tools if tool["function"]["name"] == "file_manager")
                assert set(file_tool["function"]["parameters"]["properties"]["action"]["enum"]) == {
                    "read", "list", "search", "info",
                }
                yield ModelResponse(tool_calls=[tool_call])
                return
            self.tool_result = messages[-1]["content"]
            yield ModelResponse(content="已确认写入被拒绝。")

        async def list_models(self):
            return ["mutating-model"]

    adapter = MutatingAdapter()
    context = ToolContext("session", tmp_path, model=adapter)
    result = json.loads(await SubagentManager().run(
        role="reviewer",
        task="尝试修改文件",
        context=context,
    ))

    assert result["success"] is False
    assert result["data"]["status"] == "needs_attention"
    assert json.loads(adapter.tool_result)["error"] == "SUBAGENT_READ_ONLY"
    assert not tmp_path.joinpath("forbidden.txt").exists()


@pytest.mark.asyncio
async def test_subagent_stops_with_parent_event(tmp_path):
    class BlockingAdapter(BaseModelAdapter):
        async def chat(self, messages, tools=None, stream=True, **kwargs):
            await asyncio.Event().wait()
            yield ModelResponse(content="unreachable")

        async def list_models(self):
            return ["blocking-model"]

    stop_event = asyncio.Event()
    context = ToolContext("session", tmp_path, stop_event=stop_event, model=BlockingAdapter())
    operation = asyncio.create_task(SubagentManager().run(
        role="explorer",
        task="等待停止",
        context=context,
    ))
    await asyncio.sleep(0.05)
    stop_event.set()
    result = json.loads(await asyncio.wait_for(operation, timeout=1))

    assert result["success"] is False
    assert result["data"]["status"] == "stopped"


@pytest.mark.asyncio
async def test_subagent_allows_two_runs_and_rejects_third_per_session(tmp_path):
    release = asyncio.Event()

    class WaitingAdapter(BaseModelAdapter):
        async def chat(self, messages, tools=None, stream=True, **kwargs):
            await release.wait()
            yield ModelResponse(content="完成")

        async def list_models(self):
            return ["waiting-model"]

    manager = SubagentManager()
    context = ToolContext("same-session", tmp_path, model=WaitingAdapter())
    first = asyncio.create_task(manager.run(role="explorer", task="first", context=context))
    second = asyncio.create_task(manager.run(role="reviewer", task="second", context=context))
    await asyncio.sleep(0.05)
    third = json.loads(await manager.run(role="researcher", task="third", context=context))
    assert manager.active_count("same-session") == 2
    release.set()
    await asyncio.wait_for(asyncio.gather(first, second), timeout=1)

    assert third["error"] == "SUBAGENT_BUSY"
    assert manager.active_count("same-session") == 0


@pytest.mark.asyncio
async def test_stopping_one_subagent_does_not_stop_sibling(tmp_path):
    release = asyncio.Event()

    class WaitingAdapter(BaseModelAdapter):
        async def chat(self, messages, tools=None, stream=True, **kwargs):
            await release.wait()
            yield ModelResponse(content="完成")

        async def list_models(self):
            return ["waiting-model"]

    events = []

    async def progress(event):
        events.append(event)

    manager = SubagentManager()
    context = ToolContext(
        "same-session",
        tmp_path,
        model=WaitingAdapter(),
        progress_callback=progress,
    )
    first = asyncio.create_task(manager.run(role="explorer", task="first", context=context))
    second = asyncio.create_task(manager.run(role="reviewer", task="second", context=context))
    await asyncio.sleep(0.05)
    run_ids = []
    for event in events:
        run_id = event["segment"]["subagent_id"]
        if run_id not in run_ids:
            run_ids.append(run_id)
    assert len(run_ids) == 2
    assert manager.stop("same-session", run_ids[0]) is True

    first_result = json.loads(await asyncio.wait_for(first, timeout=1))
    assert first_result["data"]["status"] == "stopped"
    assert second.done() is False

    release.set()
    second_result = json.loads(await asyncio.wait_for(second, timeout=1))
    assert second_result["data"]["status"] == "done"


@pytest.mark.asyncio
async def test_delegate_tasks_runs_two_reports_in_parallel(tmp_path, monkeypatch):
    from tools.builtin.delegate_task import DelegateTasksTool
    import tools.builtin.delegate_task as delegate_module

    running = 0
    peak = 0

    class FakeManager:
        async def run(self, *, role, task, context, timeout):
            nonlocal running, peak
            running += 1
            peak = max(peak, running)
            await asyncio.sleep(0.05)
            running -= 1
            return json.dumps({
                "type": "subagent_result",
                "success": True,
                "data": {"role": role, "task": task, "status": "done", "report": task},
            }, ensure_ascii=False)

    monkeypatch.setattr(delegate_module, "subagent_manager", FakeManager())
    context = ToolContext("session", tmp_path, model=ReportAdapter())
    result = json.loads(await DelegateTasksTool().execute(
        tasks=[
            {"role": "explorer", "task": "检查后端"},
            {"role": "reviewer", "task": "审查前端"},
        ],
        _context=context,
    ))

    assert result["success"] is True
    assert peak == 2
    assert [item["report"] for item in result["data"]["results"]] == ["检查后端", "审查前端"]


@pytest.mark.asyncio
async def test_executor_writes_with_auto_approval_and_has_no_recursive_tools(tmp_path):
    adapter = ExecutorWriteAdapter()
    context = ToolContext(
        "executor-auto",
        tmp_path,
        approval_mode="auto",
        model=adapter,
    )

    result = json.loads(await SubagentManager().run(
        role="executor",
        task="创建 executor.txt 并验证内容",
        context=context,
    ))

    assert result["success"] is True
    assert tmp_path.joinpath("executor.txt").read_text(encoding="utf-8") == "written"
    assert json.loads(adapter.tool_result)["success"] is True
    assert {"file_manager", "code_exec", "runtime_smoke"} <= adapter.tool_names
    assert "delegate_task" not in adapter.tool_names
    assert "delegate_tasks" not in adapter.tool_names
    assert "delegate_plan" not in adapter.tool_names
    assert "load_skill" not in adapter.tool_names
    audit = result["data"]["evidence"]["parent_audit"]
    assert audit["status"] == "verified"
    assert audit["observed_changed_files"] == ["executor.txt"]


@pytest.mark.asyncio
async def test_delegate_task_executor_audits_actual_worktree_changes(tmp_path):
    from tools.builtin.delegate_task import DelegateTaskTool

    result = json.loads(await DelegateTaskTool().execute(
        role="executor",
        task="创建 delegated.txt 并验证内容",
        allowed_paths=["delegated.txt"],
        _context=ToolContext(
            "delegate-audit",
            tmp_path,
            approval_mode="auto",
            model=ExecutorWriteAdapter(path="delegated.txt"),
        ),
    ))

    assert result["success"] is True
    audit = result["data"]["evidence"]["parent_audit"]
    assert audit["status"] == "verified"
    assert audit["reported_modified_files"] == ["delegated.txt"]
    assert audit["observed_changed_files"] == ["delegated.txt"]


@pytest.mark.asyncio
async def test_executor_uses_inherited_confirmation_callback(tmp_path):
    adapter = ExecutorWriteAdapter(path="approved.txt")
    confirmations = []
    events = []

    async def confirm(payload):
        confirmations.append(payload)
        return True

    async def progress(event):
        events.append(event)

    context = ToolContext(
        "executor-ask",
        tmp_path,
        approval_mode="ask",
        model=adapter,
        progress_callback=progress,
        confirm_callback=confirm,
    )
    result = json.loads(await SubagentManager().run(
        role="executor",
        task="创建 approved.txt",
        context=context,
    ))

    assert result["success"] is True
    assert len(confirmations) == 1
    assert confirmations[0]["type"] == "confirm"
    assert any(event.get("type") == "confirm" for event in events)
    assert tmp_path.joinpath("approved.txt").read_text(encoding="utf-8") == "written"


@pytest.mark.asyncio
async def test_executor_denied_confirmation_prevents_write(tmp_path):
    adapter = ExecutorWriteAdapter(path="denied.txt", verify=False)

    async def deny(_payload):
        return False

    context = ToolContext(
        "executor-denied",
        tmp_path,
        approval_mode="ask",
        model=adapter,
        confirm_callback=deny,
    )
    result = json.loads(await SubagentManager().run(
        role="executor",
        task="尝试创建 denied.txt",
        context=context,
    ))

    assert result["success"] is False
    assert result["data"]["status"] == "needs_attention"
    assert json.loads(adapter.tool_result)["error"] == "USER_DENIED"
    assert not tmp_path.joinpath("denied.txt").exists()


@pytest.mark.asyncio
async def test_executor_requires_real_verification_after_modifying_files(tmp_path):
    adapter = ExecutorWriteAdapter(path="unverified.txt", verify=False)
    context = ToolContext(
        "executor-unverified",
        tmp_path,
        approval_mode="auto",
        model=adapter,
    )

    result = json.loads(await SubagentManager().run(
        role="executor",
        task="创建文件但不验证",
        context=context,
    ))

    assert result["success"] is False
    assert result["error"] == "NEEDS_VERIFICATION"
    assert result["data"]["status"] == "needs_verification"
    assert result["data"]["evidence"]["modified_files"] == [str(tmp_path / "unverified.txt")]
    assert result["data"]["evidence"]["verifications"] == []


@pytest.mark.asyncio
async def test_executor_enforces_allowed_write_paths(tmp_path):
    adapter = ExecutorWriteAdapter(path="outside.txt", verify=False)
    context = ToolContext(
        "executor-scope",
        tmp_path,
        approval_mode="auto",
        model=adapter,
    )

    result = json.loads(await SubagentManager().run(
        role="executor",
        task="尝试修改范围外文件",
        context=context,
        allowed_paths=["allowed"],
        constraints=["不得修改 allowed 目录以外的文件"],
        acceptance_criteria=["范围外文件不存在"],
    ))

    assert result["success"] is False
    assert result["data"]["status"] == "needs_attention"
    assert result["data"]["contract"]["allowed_paths"] == ["allowed"]
    assert "SUBAGENT_SCOPE_VIOLATION" in result["data"]["evidence"]["failures"][0]
    assert not tmp_path.joinpath("outside.txt").exists()


@pytest.mark.asyncio
async def test_subagent_duplicate_calls_force_summary(tmp_path):
    tmp_path.joinpath("same.txt").write_text("same", encoding="utf-8")

    class DuplicateAdapter(BaseModelAdapter):
        def __init__(self):
            self.calls = 0
            self.last_tools = None

        async def chat(self, messages, tools=None, stream=True, **kwargs):
            self.calls += 1
            self.last_tools = tools
            if tools:
                yield ModelResponse(tool_calls=[{
                    "id": f"duplicate-{self.calls}",
                    "type": "function",
                    "function": {
                        "name": "file_manager",
                        "arguments": json.dumps({"action": "read", "path": "same.txt"}),
                    },
                }])
            else:
                assert "检测到重复工具调用" in messages[-1]["content"]
                yield ModelResponse(content="已停止重复读取并基于已有证据总结。")

        async def list_models(self):
            return ["duplicate-model"]

    adapter = DuplicateAdapter()
    result = json.loads(await SubagentManager().run(
        role="explorer",
        task="读取文件并总结",
        context=ToolContext("duplicate", tmp_path, model=adapter),
    ))

    assert result["success"] is True
    assert result["data"]["tool_calls"] == 3
    assert result["data"]["steps"] == 4
    assert result["data"]["budget"]["unlimited_steps"] is True
    assert result["data"]["budget"]["unlimited_tool_calls"] is True
    assert result["data"]["budget"]["tool_calls_used"] == 3
    assert adapter.last_tools == []


def test_subagent_timeout_uses_advanced_setting_and_allows_long_tasks():
    manager = SubagentManager()

    assert manager._timeout_limit(None, None) == 300
    assert manager._timeout_limit(None, {"subagent_timeout": 480}) == 480
    assert manager._timeout_limit(1200, {"subagent_timeout": 480}) == 900


def test_subagent_tool_result_context_includes_truncation_marker_within_limit():
    manager = SubagentManager()
    encoded = manager._tool_result_for_context(
        "start" + "x" * 10_000 + "end",
        {"tool_result_max_chars": 8_000},
    )

    assert len(encoded) <= 8_000
    assert encoded.startswith("start")
    assert "truncated for context" in encoded


def test_executor_resolves_corrected_verification_command_failure(tmp_path):
    manager = SubagentManager()
    evidence = manager._empty_evidence()
    failed_arguments = {
        "language": "shell",
        "code": "npx tsc --noEmit;",
    }
    successful_arguments = {
        "language": "shell",
        "code": "npx tsc --noEmit",
    }
    failed_result = json.dumps({
        "success": False,
        "error": "PROCESS_EXIT",
        "data": {"exit_code": 1},
    })
    successful_result = json.dumps({
        "success": True,
        "data": {"exit_code": 0},
    })

    manager._record_evidence("code_exec", failed_arguments, failed_result, evidence, tmp_path)
    assert manager._completion_status("executor", evidence)[0] == "needs_attention"

    manager._record_evidence("code_exec", successful_arguments, successful_result, evidence, tmp_path)

    assert manager._completion_status("executor", evidence)[0] == "done"
    assert evidence["failures"] == []
    assert evidence["verifications"] == ["命令通过: npx tsc --noEmit"]
    assert evidence["recoverable_failures"] == []
    assert evidence["resolved_failures"] == [
        "已恢复: code_exec: PROCESS_EXIT (npx tsc --noEmit;)"
    ]


def test_executor_keeps_unrelated_command_failure_unresolved(tmp_path):
    manager = SubagentManager()
    evidence = manager._empty_evidence()
    manager._record_evidence(
        "code_exec",
        {"language": "shell", "code": "npm test"},
        json.dumps({"success": False, "error": "PROCESS_EXIT"}),
        evidence,
        tmp_path,
    )
    manager._record_evidence(
        "code_exec",
        {"language": "shell", "code": "npx tsc --noEmit"},
        json.dumps({"success": True, "data": {"exit_code": 0}}),
        evidence,
        tmp_path,
    )

    assert manager._completion_status("executor", evidence)[0] == "needs_attention"
    assert evidence["failures"] == ["code_exec: PROCESS_EXIT (npm test)"]
    assert evidence["resolved_failures"] == []


def test_executor_only_resolves_matching_failure_when_errors_share_a_code(tmp_path):
    manager = SubagentManager()
    evidence = manager._empty_evidence()
    failed_result = json.dumps({"success": False, "error": "PROCESS_EXIT"})
    successful_result = json.dumps({"success": True, "data": {"exit_code": 0}})

    manager._record_evidence(
        "code_exec", {"language": "shell", "code": "npm test"},
        failed_result, evidence, tmp_path,
    )
    manager._record_evidence(
        "code_exec", {"language": "shell", "code": "npx tsc --noEmit;"},
        failed_result, evidence, tmp_path,
    )
    manager._record_evidence(
        "code_exec", {"language": "shell", "code": "npx tsc --noEmit"},
        successful_result, evidence, tmp_path,
    )

    assert evidence["failures"] == ["code_exec: PROCESS_EXIT (npm test)"]
    assert evidence["resolved_failures"] == [
        "已恢复: code_exec: PROCESS_EXIT (npx tsc --noEmit;)"
    ]
    assert manager._completion_status("executor", evidence)[0] == "needs_attention"


def test_read_only_runtime_guard_uses_registry_role_metadata():
    manager = SubagentManager()

    assert manager._read_only_violation("explorer", "list_memory", {}) is None
    denied = json.loads(manager._read_only_violation("explorer", "save_memory", {}))
    assert denied["error"] == "SUBAGENT_TOOL_DENIED"


def test_executor_does_not_resolve_a_different_command_for_same_verification_tool(tmp_path):
    manager = SubagentManager()
    evidence = manager._empty_evidence()
    manager._record_evidence(
        "code_exec",
        {"language": "shell", "code": "cd frontend; npx tsc --noEmit;"},
        json.dumps({"success": False, "error": "PROCESS_EXIT"}),
        evidence,
        tmp_path,
    )
    manager._record_evidence(
        "code_exec",
        {"language": "shell", "cwd": ".", "code": "npx tsc --noEmit"},
        json.dumps({"success": True, "data": {"exit_code": 0}}),
        evidence,
        tmp_path,
    )

    assert evidence["failures"] == [
        "code_exec: PROCESS_EXIT (cd frontend; npx tsc --noEmit;)"
    ]
    assert len(evidence["recoverable_failures"]) == 1
    assert evidence["resolved_failures"] == []
    assert manager._completion_status("executor", evidence)[0] == "needs_attention"


def test_verification_check_id_cannot_resolve_a_different_tool_failure(tmp_path):
    manager = SubagentManager()
    evidence = manager._empty_evidence()
    manager._record_evidence(
        "verification_exec",
        {"code": "npm test", "check_id": "shared_check"},
        json.dumps({"success": False, "error": "PROCESS_EXIT"}),
        evidence,
        tmp_path,
    )
    manager._record_evidence(
        "verification_exec",
        {"code": "npx tsc --noEmit", "check_id": "shared_check"},
        json.dumps({"success": True, "data": {"exit_code": 0}}),
        evidence,
        tmp_path,
    )

    assert evidence["failures"] == [
        "verification_exec: PROCESS_EXIT (npm test)"
    ]
    assert evidence["resolved_failures"] == []
    assert manager._completion_status("verifier", evidence)[0] == "needs_attention"


def test_acceptance_checks_bind_to_required_working_directory(tmp_path):
    manager = SubagentManager()
    frontend = tmp_path / "frontend"
    frontend.mkdir()
    evidence = manager._empty_evidence([
        "Run unit tests",
        "Run TypeScript typecheck in frontend directory",
    ])

    manager._record_evidence(
        "verification_exec",
        {"code": "npx tsc --noEmit", "check_id": "typecheck", "cwd": str(frontend)},
        json.dumps({
            "success": True,
            "data": {"exit_code": 0, "verification_kind": "tsc", "check_id": "typecheck"},
        }),
        evidence,
        ToolContext("cwd-check", tmp_path),
    )
    manager._record_evidence(
        "verification_exec",
        {"code": "python -m unittest", "check_id": "unit_tests", "cwd": str(tmp_path)},
        json.dumps({
            "success": True,
            "data": {"exit_code": 0, "verification_kind": "python:unittest", "check_id": "unit_tests"},
        }),
        evidence,
        ToolContext("cwd-check", tmp_path),
    )

    assert evidence["required_checks"] == ["unit_tests", "typecheck@frontend"]
    assert evidence["passed_checks"] == ["unit_tests", "typecheck@frontend"]
    assert evidence["missing_checks"] == []
    assert manager._completion_status("verifier", evidence)[0] == "done"


def test_acceptance_check_in_wrong_working_directory_stays_unmatched(tmp_path):
    manager = SubagentManager()
    evidence = manager._empty_evidence(["Run TypeScript typecheck in frontend directory"])
    manager._record_evidence(
        "verification_exec",
        {"code": "npx tsc --noEmit", "check_id": "typecheck", "cwd": str(tmp_path)},
        json.dumps({
            "success": True,
            "data": {"exit_code": 0, "verification_kind": "tsc", "check_id": "typecheck"},
        }),
        evidence,
        ToolContext("cwd-mismatch", tmp_path),
    )

    assert evidence["passed_checks"] == []
    assert evidence["missing_checks"] == ["typecheck@frontend"]
    assert evidence["unmatched_checks"] == ["typecheck@."]
    assert manager._completion_status("verifier", evidence)[0] == "needs_verification"


def test_read_only_roles_ignore_dynamic_acceptance_checks(tmp_path):
    manager = SubagentManager()

    assert manager._criteria_for_role(
        "explorer",
        ["必须运行单元测试", "必须运行 TypeScript 类型检查", "确认目标文件存在"],
    ) == ["确认目标文件存在"]
    assert manager._criteria_for_role(
        "reviewer",
        ["运行 lint", "检查实现是否符合要求"],
    ) == ["检查实现是否符合要求"]
    assert manager._criteria_for_role(
        "verifier",
        ["必须运行单元测试", "必须运行 TypeScript 类型检查"],
    ) == ["必须运行单元测试", "必须运行 TypeScript 类型检查"]


@pytest.mark.asyncio
async def test_explorer_with_copied_plan_checks_still_completes(tmp_path):
    result = json.loads(await SubagentManager().run(
        role="explorer",
        task="调查测试目录结构",
        acceptance_criteria=["必须运行单元测试", "必须运行 TypeScript 类型检查"],
        context=ToolContext("explorer-check-scope", tmp_path, model=ReportAdapter()),
    ))

    assert result["success"] is True
    assert result["data"]["status"] == "done"
    assert result["data"]["evidence"]["required_checks"] == []
    assert result["data"]["evidence"]["missing_checks"] == []


def test_unknown_test_quality_does_not_count_as_executor_verification(tmp_path):
    manager = SubagentManager()
    evidence = manager._empty_evidence()
    evidence["modified_files"].add(str(tmp_path / "changed.py"))
    manager._record_evidence(
        "verification_exec",
        {"code": "npm test", "check_id": "unit_tests"},
        json.dumps({
            "success": True,
            "data": {
                "exit_code": 0,
                "verification_kind": "npm",
                "verification_quality": "unknown",
                "check_id": "unit_tests",
            },
        }),
        evidence,
        tmp_path,
    )

    assert evidence["verifications"] == []
    assert manager._completion_status("executor", evidence)[0] == "needs_verification"


@pytest.mark.asyncio
async def test_executor_handoff_limits_repeated_research_and_preserves_dependencies(tmp_path):
    tmp_path.joinpath("source.txt").write_text("source", encoding="utf-8")

    class HandoffAdapter(BaseModelAdapter):
        def __init__(self):
            self.calls = 0
            self.blocked_result = ""
            self.first_prompt = ""

        async def chat(self, messages, tools=None, stream=True, **kwargs):
            self.calls += 1
            if self.calls == 1:
                self.first_prompt = messages[-1]["content"]
            if self.calls <= 9:
                yield ModelResponse(tool_calls=[{
                    "id": f"read-{self.calls}",
                    "type": "function",
                    "function": {
                        "name": "file_manager",
                        "arguments": json.dumps({
                            "action": "read",
                            "path": "source.txt",
                            "offset": self.calls - 1,
                            "max_size": 1,
                        }),
                    },
                }])
                return
            self.blocked_result = messages[-1]["content"]
            yield ModelResponse(content="交接后的重复调查已停止。")

        async def list_models(self):
            return ["handoff-model"]

    adapter = HandoffAdapter()
    result = json.loads(await SubagentManager().run(
        role="executor",
        task="修改 source.txt",
        context=ToolContext(
            "handoff",
            tmp_path,
            approval_mode="auto",
            model=adapter,
            agent_config={"subagent_max_steps": 16},
        ),
        plan_id="plan_1",
        node_id="implement",
        depends_on=["explore_game"],
        dependency_context=[{
            "id": "explore_game",
            "role": "explorer",
            "report": "已定位 source.txt，并给出明确实现方案。",
        }],
    ))

    assert "前序任务结构化交接" in adapter.first_prompt
    assert adapter.first_prompt.count("已定位 source.txt") == 1
    assert adapter.calls == 10
    assert "交接后的重复调查已停止" in result["data"]["report"]
    assert result["data"]["plan_id"] == "plan_1"
    assert result["data"]["node_id"] == "implement"
    assert result["data"]["depends_on"] == ["explore_game"]
    assert result["data"]["dependency_context_used"] is True


@pytest.mark.asyncio
async def test_executor_and_read_only_subagents_are_mutually_exclusive(tmp_path):
    release = asyncio.Event()

    class WaitingAdapter(BaseModelAdapter):
        async def chat(self, messages, tools=None, stream=True, **kwargs):
            await release.wait()
            yield ModelResponse(content="完成")

        async def list_models(self):
            return ["waiting-model"]

    manager = SubagentManager()
    context = ToolContext("exclusive-session", tmp_path, model=WaitingAdapter())
    readonly = asyncio.create_task(manager.run(role="explorer", task="调查", context=context))
    await asyncio.sleep(0.05)
    blocked_executor = json.loads(await manager.run(
        role="executor", task="修改", context=context,
    ))
    assert blocked_executor["error"] == "SUBAGENT_BUSY"
    release.set()
    await asyncio.wait_for(readonly, timeout=1)

    release.clear()
    executor = asyncio.create_task(manager.run(role="executor", task="修改", context=context))
    await asyncio.sleep(0.05)
    blocked_readonly = json.loads(await manager.run(
        role="reviewer", task="审查", context=context,
    ))
    assert blocked_readonly["error"] == "SUBAGENT_BUSY"
    release.set()
    await asyncio.wait_for(executor, timeout=1)


@pytest.mark.asyncio
async def test_delegate_tasks_rejects_executor(tmp_path):
    from tools.builtin.delegate_task import DelegateTasksTool

    result = json.loads(await DelegateTasksTool().execute(
        tasks=[
            {"role": "executor", "task": "修改文件"},
            {"role": "reviewer", "task": "审查修改"},
        ],
        _context=ToolContext("batch", tmp_path, model=ReportAdapter()),
    ))

    assert result["success"] is False
    assert result["error"] == "SUBAGENT_BATCH_READ_ONLY"


@pytest.mark.asyncio
@pytest.mark.parametrize("stop_kind", ["parent", "individual"])
async def test_executor_command_honors_stop_signals(tmp_path, stop_kind):
    events = []
    parent_stop = asyncio.Event()

    async def progress(event):
        events.append(event)

    manager = SubagentManager()
    context = ToolContext(
        "executor-stop",
        tmp_path,
        stop_event=parent_stop,
        approval_mode="auto",
        model=ExecutorCommandAdapter(),
        progress_callback=progress,
    )
    operation = asyncio.create_task(manager.run(
        role="executor",
        task="运行耗时命令",
        context=context,
    ))

    for _ in range(100):
        running = [
            event["segment"]
            for event in events
            if event.get("type") == "segment"
            and event.get("segment", {}).get("role") == "executor"
        ]
        if running and running[-1].get("tool_calls") == 1:
            break
        await asyncio.sleep(0.01)
    assert running

    if stop_kind == "parent":
        parent_stop.set()
    else:
        assert manager.stop("executor-stop", running[-1]["subagent_id"]) is True

    result = json.loads(await asyncio.wait_for(operation, timeout=3))
    assert result["success"] is False
    assert result["data"]["status"] == "stopped"
    if stop_kind == "individual":
        assert parent_stop.is_set() is False


def test_dynamic_acceptance_criteria_are_owned_by_verifier_nodes_only():
    criteria = ["运行 pytest 单元测试并执行 npx tsc --noEmit 类型检查"]

    for role in ("explorer", "researcher", "reviewer", "executor"):
        effective = SubagentManager._criteria_for_role(role, criteria)
        evidence = SubagentManager._empty_evidence(effective)
        assert effective == []
        assert evidence["required_checks"] == []

    verifier_evidence = SubagentManager._empty_evidence(
        SubagentManager._criteria_for_role("verifier", criteria)
    )
    assert verifier_evidence["required_checks"] == ["unit_tests", "typecheck"]
