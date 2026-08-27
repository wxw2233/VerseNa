from agent.task_state import (
    capture_workspace_snapshot,
    classify_user_message,
    diff_workspace_snapshots,
    build_self_check,
    prepare_for_user_message,
    reconcile_recovery_warnings,
    record_tool_result,
    recovery_check,
)
from config import settings


def test_workspace_snapshot_reports_created_modified_and_deleted_files(tmp_path):
    original = tmp_path / "original.py"
    removed = tmp_path / "removed.py"
    original.write_text("value = 1\n", encoding="utf-8")
    removed.write_text("remove me\n", encoding="utf-8")
    before = capture_workspace_snapshot(tmp_path)

    original.write_text("value = 2\n", encoding="utf-8")
    removed.unlink()
    (tmp_path / "created.py").write_text("created\n", encoding="utf-8")
    after = capture_workspace_snapshot(tmp_path)
    delta = diff_workspace_snapshots(before, after)

    assert delta["complete"] is True
    assert delta["created"] == ["created.py"]
    assert delta["modified"] == ["original.py"]
    assert delta["deleted"] == ["removed.py"]
    assert delta["changed"] == ["created.py", "original.py", "removed.py"]


def test_file_mutation_marks_project_index_stale_and_requires_readback(tmp_path):
    state = prepare_for_user_message({}, "修改配置并验证", tmp_path)
    state["project_index"] = {"source_revision": "before", "stale": False}

    record_tool_result(
        state,
        "file_manager",
        {"action": "write", "path": "src/config.py"},
        {"success": True, "data": {"path": "src/config.py"}},
    )

    assert state["project_index"]["stale"] is True
    assert state["files_changed_by_agent"] == ["src/config.py"]
    assert any("src/config.py" in item for item in state["pending"])

    record_tool_result(
        state,
        "file_manager",
        {"action": "read", "path": "src/config.py"},
        {"success": True, "complete": True, "data": {"path": "src/config.py"}},
    )

    assert any("已回读修改文件：src/config.py" == item for item in state["verified"])
    assert not any("src/config.py" in item for item in state["pending"])


def test_user_goal_modes_clear_obsolete_pending_work(tmp_path):
    state = prepare_for_user_message({}, "实现一个网页功能", tmp_path)
    state["pending"] = ["旧实现计划"]
    state["unverified"] = ["旧验证"]
    state["acceptance_matrix"] = [{"kind": "old", "status": "verified"}]

    assert classify_user_message("先别改，只看看", state)["mode"] == "pause"
    replaced = prepare_for_user_message(state, "换成只做后端接口", tmp_path)

    assert replaced["goal_mode"] in {"replace", "shrink"}
    assert replaced["pending"] == []
    assert replaced["unverified"] == []
    assert replaced["acceptance_matrix"] == []
    assert replaced["superseded_goals"]
    assert replaced["boundary_cases"]


def test_self_check_separates_agent_and_unknown_workspace_changes(tmp_path):
    (tmp_path / "user.txt").write_text("before\n", encoding="utf-8")
    state = prepare_for_user_message({}, "修改项目并验证", tmp_path)
    (tmp_path / "agent.txt").write_text("agent\n", encoding="utf-8")
    state["files_changed_by_agent"] = ["agent.txt"]
    (tmp_path / "user.txt").write_text("user changed\n", encoding="utf-8")

    check = build_self_check(state, tmp_path)

    assert "agent.txt" in check["agent_changes"]
    assert "user.txt" in check["blocking_reasons"][0] or check["has_user_changes"]
    assert check["safe_to_continue"] is False


def test_read_only_project_map_cache_is_not_an_unknown_workspace_change(tmp_path, monkeypatch):
    from agent.project_map import build_project_map, clear_project_map_cache

    workspace = tmp_path / "project"
    workspace.mkdir()
    (workspace / "package.json").write_text(
        '{"name":"snapshot-test","scripts":{"test":"pytest"}}',
        encoding="utf-8",
    )
    data_dir = workspace / "backend" / "data"
    monkeypatch.setattr(settings, "DATA_DIR", data_dir)
    clear_project_map_cache()

    state = prepare_for_user_message({}, "读取项目结构", workspace)
    build_project_map(workspace, refresh=True)

    recovery = recovery_check(state, workspace)

    assert not any(
        item["kind"] in {"concurrent_workspace_change", "worktree_changed"}
        for item in recovery["findings"]
    )


def test_real_project_change_after_read_only_index_is_still_reported(tmp_path, monkeypatch):
    from agent.project_map import build_project_map, clear_project_map_cache

    workspace = tmp_path / "project"
    workspace.mkdir()
    (workspace / "main.py").write_text("print('before')\n", encoding="utf-8")
    data_dir = workspace / "backend" / "data"
    monkeypatch.setattr(settings, "DATA_DIR", data_dir)
    clear_project_map_cache()

    state = prepare_for_user_message({}, "读取项目结构", workspace)
    build_project_map(workspace, refresh=True)
    (workspace / "main.py").write_text("print('after')\n", encoding="utf-8")

    recovery = recovery_check(state, workspace)

    conflict = next(
        item for item in recovery["findings"]
        if item["kind"] == "concurrent_workspace_change"
    )
    assert "main.py" in conflict["paths"]


def test_resolved_workspace_warning_is_removed_from_checkpoint_state():
    state = {
        "unverified": [
            "任务开始后检测到新的工作区改动，继续前需重新读取相关文件",
            "仍需确认 API 行为",
        ],
    }

    reconcile_recovery_warnings(state, {"findings": []})

    assert state["unverified"] == ["仍需确认 API 行为"]
