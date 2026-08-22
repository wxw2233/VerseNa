import json

import pytest
from agent.memory import MemoryManager

def test_estimate_tokens():
    mm = MemoryManager()
    messages = [{"role": "user", "content": "你好啊"}]
    tokens = mm._estimate_tokens(messages)
    assert tokens > 0
    assert tokens < 10

def test_estimate_tokens_empty():
    mm = MemoryManager()
    assert mm._estimate_tokens([]) == 0

def test_runtime_compaction_uses_message_count_when_context_budget_is_large():
    memory = MemoryManager()
    messages = [{"role": "system", "content": "system"}]
    for index in range(25):
        messages.extend([
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [{"id": f"call-{index}", "function": {"name": "read"}}],
            },
            {"role": "tool", "tool_call_id": f"call-{index}", "content": f"result {index}"},
        ])

    assert memory.runtime_compaction_reason(messages, max_context=1_000_000) == "message_count"

    compacted = memory.compact_runtime_messages(messages, max_context=1_000_000)

    assert len(compacted) < len(messages)
    assert memory.runtime_compaction_reason(compacted, max_context=1_000_000) is None
    assert any(message["role"] == "system" and "工作记录" in message["content"] for message in compacted)


def test_runtime_compaction_ignores_plain_chat_message_count():
    memory = MemoryManager()
    messages = [{"role": "system", "content": "system"}]
    messages.extend(
        {"role": "user" if index % 2 == 0 else "assistant", "content": f"message {index}"}
        for index in range(60)
    )

    assert memory.runtime_compaction_reason(messages, max_context=1_000_000) is None


def test_context_trim_respects_hard_budget_with_large_system_prompt():
    memory = MemoryManager()
    messages = [
        {"role": "system", "content": "system rules " * 20_000},
        {"role": "user", "content": "keep this request"},
    ]

    _, hard_budget = memory._context_budgets(2_000, 1_000)
    compacted = memory._trim_runtime_system(
        [messages[0]], messages[1:], hard_budget,
    )
    assert memory._estimate_msgs_tokens(compacted) <= hard_budget
    assert compacted[0]["role"] == "system"


def test_runtime_compaction_keeps_task_state_negative_evidence():
    memory = MemoryManager()
    state = {
        "active_goal": "修复长任务恢复",
        "goal_mode": "refine",
        "pending": ["尚未验证浏览器交互"],
        "do_not_do": ["不要删除用户已有文件"],
        "files_changed_by_agent": ["backend/app.py"],
        "boundary_cases": [{"kind": "interrupt_recovery", "status": "unverified"}],
    }
    messages = [{"role": "system", "content": "system"}]
    for index in range(30):
        messages.extend([
            {"role": "assistant", "content": f"step {index}"},
            {"role": "tool", "content": json.dumps({"success": True, "data": {"index": index}})},
        ])

    compacted = memory.compact_runtime_messages(
        messages,
        max_context=1_000_000,
        task_state=state,
        current_user_message="继续修复长任务恢复",
    )
    text = "\n".join(str(message.get("content", "")) for message in compacted)

    assert "修复长任务恢复" in text
    assert "不要删除用户已有文件" in text
    assert "backend/app.py" in text
    assert "interrupt_recovery" in text


@pytest.mark.asyncio
async def test_first_turn_system_prompt_does_not_emit_compaction_notice(monkeypatch):
    memory = MemoryManager()
    events = []

    async def get_memories(*args, **kwargs):
        return []

    async def get_summaries(*args, **kwargs):
        return []

    async def get_history(*args, **kwargs):
        return [{"role": "user", "content": "hello", "metadata": {}}]

    monkeypatch.setattr("agent.memory.db.get_memories", get_memories)
    monkeypatch.setattr("agent.memory.db.get_summaries", get_summaries)
    monkeypatch.setattr("agent.memory.db.get_history", get_history)

    await memory.get_context(
        "first-turn",
        "large system prompt " * 500,
        max_context=120,
        max_output_tokens=20,
        compaction_callback=events.append,
    )

    assert events == []
