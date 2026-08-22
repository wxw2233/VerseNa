from agent.task_state import (
    capture_workspace_snapshot,
    classify_user_message,
    diff_workspace_snapshots,
    build_self_check,
    prepare_for_user_message,
    record_tool_result,
)


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
