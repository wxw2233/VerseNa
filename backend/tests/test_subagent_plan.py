import asyncio
import json

import pytest

from agent.subagent_plan import SubagentPlanManager
from tools.base import ToolContext


def result(role, report, status="done", modified=None):
    return json.dumps({
        "type": "subagent_result",
        "success": status == "done",
        "data": {
            "run_id": f"sub_{role}",
            "role": role,
            "status": status,
            "report": report,
            "duration_ms": 10,
            "evidence": {
                "modified_files": modified or [],
                "verifications": ["验证通过"] if modified else [],
                "failures": [],
            },
        },
    }, ensure_ascii=False)


def test_subagent_plan_rejects_cycles_and_unknown_dependencies():
    manager = SubagentPlanManager()
    cycle = manager._validate([
        {"id": "a", "role": "explorer", "task": "A", "depends_on": ["b"]},
        {"id": "b", "role": "reviewer", "task": "B", "depends_on": ["a"]},
    ])
    unknown = manager._validate([
        {"id": "a", "role": "explorer", "task": "A", "depends_on": []},
        {"id": "b", "role": "reviewer", "task": "B", "depends_on": ["missing"]},
    ])

    assert json.loads(cycle)["error"] == "CYCLIC_SUBAGENT_PLAN"
    assert json.loads(unknown)["error"] == "UNKNOWN_SUBAGENT_DEPENDENCY"


def test_subagent_plan_requires_explicit_and_unambiguous_dependencies():
    manager = SubagentPlanManager()
    missing = manager._validate([
        {"id": "inspect", "role": "explorer", "task": "检查代码"},
        {"id": "verify", "role": "reviewer", "task": "验证结果", "depends_on": ["inspect"]},
    ])
    ambiguous = manager._validate([
        {"id": "inspect", "role": "explorer", "task": "检查代码", "depends_on": []},
        {"id": "implement", "role": "executor", "task": "完成实现", "depends_on": []},
        {"id": "verify", "role": "reviewer", "task": "验证结果", "depends_on": ["implement"]},
    ])

    assert json.loads(missing)["error"] == "SUBAGENT_DEPENDENCY_REQUIRED"
    ambiguous_payload = json.loads(ambiguous)
    assert ambiguous_payload["error"] == "AMBIGUOUS_SUBAGENT_DEPENDENCIES"
    assert ambiguous_payload["data"]["root_executors"] == ["implement"]
    assert ambiguous_payload["data"]["root_readonly"] == ["inspect"]


def test_plan_aggregates_verification_quality_evidence():
    manager = SubagentPlanManager()
    evidence = manager._aggregate_evidence({
        "verify": {
            "id": "verify",
            "status": "needs_attention",
            "evidence": {
                "verification_quality": [{
                    "check_id": "unit_tests",
                    "verification_quality": "empty",
                    "tests_discovered": False,
                    "tests_executed": 0,
                    "test_count": 0,
                }],
            },
        },
    })

    assert evidence["verification_quality"][0]["check_id"] == "unit_tests"
    assert evidence["verification_quality"][0]["verification_quality"] == "empty"


def test_plan_recomputes_missing_checks_after_merging_nodes():
    manager = SubagentPlanManager()
    evidence = manager._aggregate_evidence({
        "verify_tests": {
            "id": "verify_tests",
            "status": "done",
            "evidence": {
                "required_checks": ["unit_tests", "typecheck"],
                "passed_checks": ["unit_tests"],
                "missing_checks": ["typecheck"],
            },
        },
        "verify_types": {
            "id": "verify_types",
            "status": "done",
            "evidence": {
                "required_checks": ["typecheck"],
                "passed_checks": ["typecheck"],
                "missing_checks": [],
            },
        },
    })

    assert evidence["required_checks"] == ["unit_tests", "typecheck"]
    assert evidence["passed_checks"] == ["unit_tests", "typecheck"]
    assert evidence["missing_checks"] == []


def test_subagent_plan_requires_verifier_for_dynamic_validation():
    manager = SubagentPlanManager()
    invalid = manager._validate([
        {"id": "setup", "role": "executor", "task": "创建测试文件", "depends_on": []},
        {
            "id": "verify_tsc",
            "role": "reviewer",
            "task": "运行 npx tsc --noEmit 并报告退出码",
            "depends_on": ["setup"],
        },
    ])
    valid = manager._validate([
        {"id": "setup", "role": "executor", "task": "创建测试文件", "depends_on": []},
        {
            "id": "verify_tsc",
            "role": "verifier",
            "task": "运行 npx tsc --noEmit 并报告退出码",
            "depends_on": ["setup"],
        },
    ])

    assert json.loads(invalid)["error"] == "SUBAGENT_VERIFIER_ROLE_REQUIRED"
    assert isinstance(valid, list)
    assert valid[1]["role"] == "verifier"


@pytest.mark.asyncio
async def test_plan_validation_error_includes_structured_repair_guidance(tmp_path):
    payload = json.loads(await SubagentPlanManager().run(nodes=[
        {"id": "setup", "role": "executor", "task": "创建文件", "depends_on": []},
        {
            "id": "verify",
            "role": "reviewer",
            "task": "运行 pytest 验证",
            "depends_on": ["setup"],
        },
    ], context=ToolContext("repair-plan", tmp_path, model=object())))

    repair = payload["data"]["repair"]
    assert payload["error"] == "SUBAGENT_VERIFIER_ROLE_REQUIRED"
    assert repair["retryable"] is True
    assert repair["max_retries"] == 1
    assert repair["failed_error"] == payload["error"]
    assert repair["failed_nodes"][1] == {
        "id": "verify",
        "role": "reviewer",
        "depends_on": ["setup"],
    }


@pytest.mark.asyncio
async def test_plan_parallelizes_readers_then_passes_reports_to_executor(tmp_path, monkeypatch):
    import agent.subagent_plan as plan_module

    running = set()
    peak = 0
    executor_overlap = False
    executor_task = ""
    executor_handoff = []
    executor_depends_on = []

    class FakeManager:
        async def run(self, *, role, task, dependency_context=None, depends_on=None, **kwargs):
            nonlocal peak, executor_overlap, executor_task, executor_handoff, executor_depends_on
            if role == "executor":
                executor_overlap = bool(running)
                executor_task = task
                executor_handoff = dependency_context or []
                executor_depends_on = depends_on or []
            running.add(role)
            peak = max(peak, len(running))
            await asyncio.sleep(0.04 if role != "executor" else 0.01)
            running.remove(role)
            return result(
                role,
                f"{role} 报告",
                modified=[str(tmp_path / "changed.txt")] if role == "executor" else None,
            )

    monkeypatch.setattr(plan_module, "subagent_manager", FakeManager())
    events = []

    async def progress(event):
        events.append(event)

    context = ToolContext("plan", tmp_path, model=object(), progress_callback=progress)
    raw = await SubagentPlanManager().run(nodes=[
        {"id": "inspect", "role": "explorer", "task": "检查代码", "depends_on": []},
        {"id": "research", "role": "researcher", "task": "查询资料", "depends_on": []},
        {
            "id": "implement",
            "role": "executor",
            "task": "完成实现",
            "depends_on": ["inspect", "research"],
            "allowed_paths": ["changed.txt"],
        },
    ], context=context)
    payload = json.loads(raw)

    assert payload["success"] is True
    assert peak == 2
    assert executor_overlap is False
    assert executor_task == "完成实现"
    assert [item["report"] for item in executor_handoff] == ["explorer 报告", "researcher 报告"]
    assert executor_depends_on == ["inspect", "research"]
    assert payload["data"]["evidence"]["modified_files"] == [str(tmp_path / "changed.txt")]
    plan_segments = [event["segment"] for event in events]
    assert plan_segments[0]["status"] == "running"
    assert plan_segments[-1]["status"] == "done"


@pytest.mark.asyncio
async def test_plan_honors_full_dependency_order_and_transfers_each_handoff(tmp_path, monkeypatch):
    import agent.subagent_plan as plan_module

    started = []
    handoffs = {}
    dependencies = {}

    class FakeManager:
        async def run(self, *, role, node_id, dependency_context=None, depends_on=None, **kwargs):
            started.append(node_id)
            handoffs[node_id] = dependency_context or []
            dependencies[node_id] = depends_on or []
            await asyncio.sleep(0.01)
            return result(
                role,
                f"{node_id} 报告",
                modified=[str(tmp_path / "changed.txt")] if role == "executor" else None,
            )

    monkeypatch.setattr(plan_module, "subagent_manager", FakeManager())
    payload = json.loads(await SubagentPlanManager().run(nodes=[
        {"id": "explore_game", "role": "explorer", "task": "检查游戏逻辑", "depends_on": []},
        {"id": "explore_tests", "role": "explorer", "task": "检查测试", "depends_on": []},
        {
            "id": "implement",
            "role": "executor",
            "task": "实现并测试",
            "depends_on": ["explore_game", "explore_tests"],
            "allowed_paths": ["src", "tests"],
        },
        {"id": "verify", "role": "verifier", "task": "独立验收", "depends_on": ["implement"]},
    ], context=ToolContext("ordered-plan", tmp_path, model=object())))

    assert payload["success"] is True
    assert set(started[:2]) == {"explore_game", "explore_tests"}
    assert started[2:] == ["implement", "verify"]
    assert dependencies == {
        "explore_game": [],
        "explore_tests": [],
        "implement": ["explore_game", "explore_tests"],
        "verify": ["implement"],
    }
    assert [item["id"] for item in handoffs["implement"]] == ["explore_game", "explore_tests"]
    assert [item["report"] for item in handoffs["implement"]] == [
        "explore_game 报告",
        "explore_tests 报告",
    ]
    assert [item["id"] for item in handoffs["verify"]] == ["implement"]
    returned = {node["id"]: node for node in payload["data"]["nodes"]}
    assert returned["implement"]["depends_on"] == ["explore_game", "explore_tests"]
    assert returned["verify"]["depends_on"] == ["implement"]


@pytest.mark.asyncio
async def test_plan_skips_failed_dependents_but_runs_independent_branch(tmp_path, monkeypatch):
    import agent.subagent_plan as plan_module

    called = []

    class FakeManager:
        async def run(self, *, role, task, node_id, **kwargs):
            called.append(node_id)
            if node_id == "failed":
                return result(role, "调查失败", status="error")
            return result(role, "调查完成")

    monkeypatch.setattr(plan_module, "subagent_manager", FakeManager())
    payload = json.loads(await SubagentPlanManager().run(nodes=[
        {"id": "failed", "role": "explorer", "task": "失败分支", "depends_on": []},
        {"id": "blocked", "role": "reviewer", "task": "依赖失败", "depends_on": ["failed"]},
        {"id": "independent", "role": "researcher", "task": "独立分支", "depends_on": []},
    ], context=ToolContext("partial", tmp_path, model=object())))

    states = {node["id"]: node["status"] for node in payload["data"]["nodes"]}
    assert payload["success"] is False
    assert states == {"failed": "error", "blocked": "skipped", "independent": "done"}
    assert "blocked" not in called
    assert "independent" in called


@pytest.mark.asyncio
async def test_plan_honors_parent_stop_before_starting_dependents(tmp_path, monkeypatch):
    import agent.subagent_plan as plan_module

    stop_event = asyncio.Event()
    called = []

    class FakeManager:
        async def run(self, *, node_id, **kwargs):
            called.append(node_id)
            stop_event.set()
            return result("explorer", "完成")

    monkeypatch.setattr(plan_module, "subagent_manager", FakeManager())
    payload = json.loads(await SubagentPlanManager().run(nodes=[
        {"id": "first", "role": "explorer", "task": "第一步", "depends_on": []},
        {"id": "second", "role": "reviewer", "task": "第二步", "depends_on": ["first"]},
    ], context=ToolContext("stop-plan", tmp_path, stop_event=stop_event, model=object())))

    states = {node["id"]: node["status"] for node in payload["data"]["nodes"]}
    assert called == ["first"]
    assert states == {"first": "done", "second": "stopped"}
