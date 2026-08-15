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
