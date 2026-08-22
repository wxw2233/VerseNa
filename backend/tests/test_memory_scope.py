import pytest
import pytest_asyncio

from agent.memory import MemoryManager
from db.database import db


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    db.db_path = ":memory:"
    await db.connect()
    yield
    await db.close()


@pytest.mark.asyncio
async def test_workspace_memory_isolated_from_other_workspace():
    workspace_a = r"E:\projects\alpha"
    workspace_b = r"E:\projects\beta"
    await db.save_memory("global preference", source="manual")
    await db.save_memory(
        "alpha decision",
        source="manual",
        scope="workspace",
        workspace_path=workspace_a,
    )
    await db.save_memory(
        "beta decision",
        source="manual",
        scope="workspace",
        workspace_path=workspace_b,
    )

    memories = await db.get_memories(limit=20, workspace_path=workspace_a)
    contents = [item["content"] for item in memories]

    assert "global preference" in contents
    assert "alpha decision" in contents
    assert "beta decision" not in contents
    assert memories[0]["scope"] == "workspace"


@pytest.mark.asyncio
async def test_memory_context_marks_scope_and_workspace():
    workspace = r"E:\projects\alpha"
    await db.save_memory("global preference", source="manual")
    await db.save_memory(
        "alpha decision",
        source="auto",
        scope="workspace",
        workspace_path=workspace,
    )

    context = await MemoryManager().get_context(
        "memory-scope-session",
        "system prompt",
        workspace_path=workspace,
    )
    memory_messages = [
        message for message in context
        if "用户偏好与记忆" in message.get("content", "")
    ]

    assert len(memory_messages) == 1
    assert "[全局] global preference" in memory_messages[0]["content"]
    assert f"[工作区: {workspace}] alpha decision" in memory_messages[0]["content"]


@pytest.mark.asyncio
async def test_workspace_duplicate_check_does_not_cross_project_boundary():
    await db.save_memory(
        "same decision",
        source="manual",
        scope="workspace",
        workspace_path=r"E:\projects\alpha",
    )

    assert await db.check_duplicate_memory(
        "same decision",
        scope="workspace",
        workspace_path=r"E:\projects\alpha",
    ) is not None
    assert await db.check_duplicate_memory(
        "same decision",
        scope="workspace",
        workspace_path=r"E:\projects\beta",
    ) is None


@pytest.mark.asyncio
async def test_memory_usage_count_is_updated_when_context_is_built():
    memory_id = await db.save_memory("remembered fact", source="manual")

    await MemoryManager().get_context("memory-usage-session", "system prompt")
    memories = await db.get_memories(limit=20)
    memory = next(item for item in memories if item["id"] == memory_id)

    assert memory["use_count"] == 1
    assert memory["last_used_at"]


@pytest.mark.asyncio
async def test_memory_edit_and_lookup_respect_workspace_visibility():
    workspace_a = r"E:projectsalpha"
    workspace_b = r"E:projectseta"
    global_id = await db.save_memory("global fact", source="manual")
    alpha_id = await db.save_memory(
        "alpha fact",
        source="manual",
        scope="workspace",
        workspace_path=workspace_a,
    )

    assert (await db.get_memory(global_id, workspace_path=workspace_b))["content"] == "global fact"
    assert await db.get_memory(alpha_id, workspace_path=workspace_b) is None
    assert await db.update_memory(alpha_id, content="blocked", workspace_path=workspace_b) is False
    assert await db.update_memory(alpha_id, content="updated", workspace_path=workspace_a) is True
    assert (await db.get_memory(alpha_id, workspace_path=workspace_a))["content"] == "updated"


@pytest.mark.asyncio
async def test_manual_and_auto_memories_have_distinct_governance_defaults():
    manual_id = await MemoryManager().save_memory_manual("manual preference")
    auto_id = await db.save_memory("automatic inference", source="auto", auto_apply=False)

    memories = {item["id"]: item for item in await db.get_memories(limit=20)}

    assert memories[manual_id]["auto_apply"] == 1
    assert memories[manual_id]["verified_at"]
    assert memories[auto_id]["auto_apply"] == 0
    assert memories[auto_id]["verified_at"] is None


@pytest.mark.asyncio
async def test_project_scoped_workspace_memory_is_hidden_from_other_project_id():
    workspace = r"E:\projects\shared"
    project_a = "project-a"
    project_b = "project-b"
    memory_id = await db.save_memory(
        "project-specific fact",
        source="manual",
        scope="workspace",
        workspace_path=workspace,
        project_id=project_a,
    )

    visible = await db.get_memories(
        limit=20, workspace_path=workspace, project_id=project_a,
    )
    hidden = await db.get_memories(
        limit=20, workspace_path=workspace, project_id=project_b,
    )

    assert any(item["id"] == memory_id for item in visible)
    assert all(item["id"] != memory_id for item in hidden)


@pytest.mark.asyncio
async def test_update_memory_uses_current_project_for_visibility_before_target_project():
    workspace = r"E:\projects\shared"
    stored_project = "project-a"
    memory_id = await db.save_memory(
        "project-a fact",
        source="manual",
        scope="workspace",
        workspace_path=workspace,
        project_id=stored_project,
    )

    # A caller may provide a target project value, but it must not turn that
    # value into an authorization grant for the current workspace.
    assert await db.update_memory(
        memory_id,
        content="must remain unchanged",
        workspace_path=workspace,
        # This is the value that the old implementation incorrectly reused
        # as the visibility boundary. It must be treated as a target value.
        project_id=stored_project,
    ) is False
    record = await db.get_memory(
        memory_id,
        workspace_path=workspace,
        project_id=stored_project,
    )
    assert record["content"] == "project-a fact"


@pytest.mark.asyncio
async def test_update_memory_honors_explicit_visibility_project_id():
    workspace = r"E:\projects\shared"
    project_a = "project-a"
    project_b = "project-b"
    memory_id = await db.save_memory(
        "project-a fact",
        source="manual",
        scope="workspace",
        workspace_path=workspace,
        project_id=project_a,
    )

    assert await db.update_memory(
        memory_id,
        content="updated from authorized boundary",
        workspace_path=workspace,
        project_id=project_b,
        visibility_project_id=project_a,
    ) is True
    record = await db.get_memory(
        memory_id,
        workspace_path=workspace,
        project_id=project_b,
    )
    assert record["content"] == "updated from authorized boundary"
    assert record["project_id"] == project_b


@pytest.mark.asyncio
async def test_history_restores_persisted_acceptance_report_metadata():
    report = {
        "phase": "validating",
        "modified_files": ["src/app.py"],
        "verified": ["python -m pytest"],
        "unverified": ["browser smoke test"],
    }
    await db.save_message(
        "acceptance-history",
        "assistant",
        "Implementation report",
        metadata={"acceptance_report": report, "finish_reason": "completed"},
    )

    history = await db.get_history("acceptance-history")

    assert history[0]["acceptance_report"] == report
    assert history[0]["finish_reason"] == "completed"
