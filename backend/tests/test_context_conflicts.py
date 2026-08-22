from agent.context_conflicts import detect_context_conflicts
from agent.task_state import prepare_for_user_message, workspace_id


def test_context_conflicts_flag_stale_paths_indexes_and_foreign_memories(tmp_path):
    workspace = tmp_path / "project"
    workspace.mkdir()
    state = prepare_for_user_message({}, "继续实现功能", workspace)
    state["files_changed_by_agent"] = ["missing.py"]
    state["project_index"] = {"source_revision": "obsolete-revision"}
    other_workspace = tmp_path / "other-project"
    other_workspace.mkdir()

    report = detect_context_conflicts(workspace, state, [
        {
            "id": 1,
            "scope": "workspace",
            "workspace_path": str(other_workspace),
            "project_id": workspace_id(other_workspace),
            "auto_apply": 1,
            "verified_at": None,
        },
    ])
    kinds = {item["kind"] for item in report["conflicts"]}

    assert report["status"] == "conflict"
    assert "checkpoint_file_missing" in kinds
    assert "project_index_stale" in kinds
    assert "memory_workspace_mismatch" in kinds
    assert "memory_project_mismatch" in kinds
    assert "unverified_auto_memory" in kinds


def test_context_conflicts_flag_foreign_memory_even_when_task_is_clean(tmp_path):
    workspace = tmp_path / "project"
    workspace.mkdir()
    other_workspace = tmp_path / "other-project"
    other_workspace.mkdir()

    report = detect_context_conflicts(workspace, {}, [
        {
            "id": 2,
            "scope": "global",
            "project_id": workspace_id(other_workspace),
            "auto_apply": 0,
        },
    ])

    assert "memory_project_mismatch" in {item["kind"] for item in report["conflicts"]}
