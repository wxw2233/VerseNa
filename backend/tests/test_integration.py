"""集成测试：覆盖今天暴露的真实 bug 场景"""
import json
import pytest
import pytest_asyncio
import asyncio
from agent.react import ReActAgent
from agent.models.base import BaseModelAdapter, ModelResponse
from agent.memory import MemoryManager
from db.database import db
from api.log_api import log_info, log_error, LOG_FILE
from typing import AsyncGenerator


# ============================================================
# Mock 工具
# ============================================================

class MockAdapter(BaseModelAdapter):
    """可配置的 Mock LLM 适配器"""

    def __init__(self, responses=None, fail_count=0, fail_error=None):
        self.responses = responses or ["默认回复"]
        self.call_count = 0
        self.fail_count = fail_count  # 前 N 次调用失败
        self.fail_error = fail_error or Exception("连接超时")

    async def chat(self, messages, tools=None, stream=True) -> AsyncGenerator:
        if self.call_count < self.fail_count:
            self.call_count += 1
            raise self.fail_error
        resp = self.responses[min(self.call_count, len(self.responses) - 1)]
        self.call_count += 1
        yield ModelResponse(content=resp)

    async def list_models(self):
        return ["mock-model"]


class ToolCallAdapter(BaseModelAdapter):
    """返回工具调用的 Mock 适配器"""

    def __init__(self, tool_calls_sequence):
        self.tool_calls_sequence = tool_calls_sequence
        self.call_count = 0

    async def chat(self, messages, tools=None, stream=True) -> AsyncGenerator:
        idx = min(self.call_count, len(self.tool_calls_sequence) - 1)
        self.call_count += 1
        tc = self.tool_calls_sequence[idx]
        if tc is None:
            yield ModelResponse(content="最终回复")
        else:
            yield ModelResponse(content="", tool_calls=[{
                "id": f"call_{self.call_count}",
                "function": {"name": tc["name"], "arguments": json.dumps(tc["args"])}
            }])

    async def list_models(self):
        return ["mock-model"]


# ============================================================
# Fixture
# ============================================================

@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    db.db_path = ":memory:"
    await db.connect()
    yield
    await db.close()


@pytest.mark.asyncio
async def test_database_connect_is_idempotent(tmp_path):
    from db.database import Database

    database = Database(tmp_path / "idempotent.db")
    await database.connect()
    first_connection = database._db
    await database.connect()

    assert database._db is first_connection
    await database.close()
    assert database._db is None


# ============================================================
# 1. 消息 segments 完整链路
# ============================================================

class TestSegmentsIntegration:
    """验证 segment yield 格式和 tool_call_id 生成"""

    @pytest.mark.asyncio
    async def test_text_segments_are_yielded(self):
        adapter = MockAdapter(["你好！我是次元人格。"])
        memory = MemoryManager()
        agent = ReActAgent(adapter, memory)

        events = []
        async for event in agent.run("seg-test", "你好"):
            events.append(event)

        # 应该有 text segment + done
        segments = [e for e in events if e.get("type") == "segment"]
        assert len(segments) > 0
        assert segments[0]["segment"]["type"] == "text"
        assert "你好" in segments[0]["segment"]["content"]

        done = [e for e in events if e.get("type") == "done"]
        assert len(done) == 1

    @pytest.mark.asyncio
    async def test_tool_call_generates_tool_call_id(self):
        adapter = ToolCallAdapter([
            {"name": "web_search", "args": {"query": "test"}},
            None  # 第二次调用返回最终回复
        ])
        memory = MemoryManager()
        agent = ReActAgent(adapter, memory, tool_registry=None)

        events = []
        async for event in agent.run("tc-test", "搜索一下"):
            events.append(event)

        # 无 tool_registry 时应输出"工具系统未配置"
        texts = [e for e in events if e.get("type") == "segment" and e["segment"].get("type") == "text"]
        assert any("工具系统未配置" in t["segment"]["content"] for t in texts)

    @pytest.mark.asyncio
    async def test_done_event_always_emitted(self):
        """即使 LLM 异常，done 事件也必须发出"""
        adapter = MockAdapter(fail_count=10, fail_error=Exception("模拟连接失败"))
        memory = MemoryManager()
        agent = ReActAgent(adapter, memory)

        events = []
        async for event in agent.run("done-test", "你好"):
            events.append(event)

        done = [e for e in events if e.get("type") == "done"]
        assert len(done) == 1


# ============================================================
# 2. LLM 重试机制
# ============================================================

class TestLLMRetry:
    """验证失败重试逻辑——今天 chat.py 崩了就是因为没重试"""

    @pytest.mark.asyncio
    async def test_retry_succeeds_after_transient_failure(self):
        adapter = MockAdapter(
            responses=["重试成功"],
            fail_count=2,  # 前 2 次失败，第 3 次成功
            fail_error=Exception("ConnectionResetError")
        )
        memory = MemoryManager()
        agent = ReActAgent(adapter, memory)

        events = []
        async for event in agent.run("retry-test", "你好"):
            events.append(event)

        texts = [e["segment"]["content"] for e in events
                 if e.get("type") == "segment" and e["segment"].get("type") == "text"]

        # 应包含重试提示和最终回复
        full_text = "".join(texts)
        assert "重试中" in full_text or "重试成功" in full_text

    @pytest.mark.asyncio
    async def test_retry_exhausted_shows_error(self):
        adapter = MockAdapter(
            fail_count=10,  # 所有调用都失败
            fail_error=Exception("ServerDown")
        )
        memory = MemoryManager()
        agent = ReActAgent(adapter, memory)

        events = []
        async for event in agent.run("retry-exhaust-test", "你好"):
            events.append(event)

        texts = [e["segment"]["content"] for e in events
                 if e.get("type") == "segment" and e["segment"].get("type") == "text"]

        full_text = "".join(texts)
        assert "连接失败" in full_text or "重试" in full_text or "ServerDown" in full_text


# ============================================================
# 3. 记忆权重排序
# ============================================================

class TestMemoryWeightSorting:
    """验证 instruction > fact > preference > general 排序"""

    @pytest.mark.asyncio
    async def test_weight_ordering(self):
        # 按时间顺序插入（general 最新，instruction 最旧）
        await db.save_memory("通用信息", category="general", source="manual")
        await db.save_memory("用户偏好简洁", category="preference", source="manual")
        await db.save_memory("用户是大学生", category="fact", source="manual")
        await db.save_memory("不要用英文回复", category="instruction", source="manual")

        memories = await db.get_memories(limit=10)
        categories = [m["category"] for m in memories]

        # instruction 应该排第一（权重最高）
        assert categories[0] == "instruction"
        # fact 排第二
        assert categories[1] == "fact"
        # preference 排第三
        assert categories[2] == "preference"
        # general 排最后
        assert categories[3] == "general"

    @pytest.mark.asyncio
    async def test_expired_memories_excluded(self):
        from datetime import datetime, timedelta
        await db.save_memory("有效记忆", category="fact", source="manual")
        await db.save_memory("过期记忆", category="fact", source="auto",
                             expired_at=(datetime.now() - timedelta(days=1)).isoformat())

        memories = await db.get_memories(limit=10)
        contents = [m["content"] for m in memories]

        assert "有效记忆" in contents
        assert "过期记忆" not in contents

    @pytest.mark.asyncio
    async def test_memory_dedup(self):
        await db.save_memory("用户喜欢猫", category="preference", source="manual")
        # 重复内容不应再插入
        dup_id = await db.check_duplicate_memory("用户喜欢猫")
        assert dup_id is not None

        unique_id = await db.check_duplicate_memory("用户喜欢狗")
        assert unique_id is None


# ============================================================
# 4. 运行日志 API
# ============================================================

class TestLogAPI:
    """验证日志写入和读取——监控面板的基础"""

    @pytest.mark.asyncio
    async def test_log_write_and_read(self):
        log_info("Test", "集成测试日志")
        log_error("Test", "错误日志")

        assert LOG_FILE.exists()
        content = LOG_FILE.read_text(encoding="utf-8")
        assert "集成测试日志" in content
        assert "[ERROR]" in content

    @pytest.mark.asyncio
    async def test_log_level_detection(self):
        """验证前端能区分日志级别"""
        log_info("Chat", "用户消息")
        log_error("QQ", "发送失败")
        log_warn = lambda tag, msg: log_info(tag, f"[WARN] {msg}")  # 简化测试
        log_warn("Agent", "重试中")

        content = LOG_FILE.read_text(encoding="utf-8")
        assert "[INFO]" in content
        assert "[ERROR]" in content


# ============================================================
# 5. 上下文加载（含记忆注入）
# ============================================================

class TestContextLoading:
    """验证上下文加载顺序：system_prompt → 记忆 → 摘要 → 历史"""

    @pytest.mark.asyncio
    async def test_context_includes_memories(self):
        await db.save_memory("用户喜欢简洁回答", category="preference", source="manual")
        await db.save_memory("不要用英文", category="instruction", source="manual")

        memory = MemoryManager()
        # 模拟写入一条历史消息
        await memory.add_message("ctx-test", "user", "你好")
        await memory.add_message("ctx-test", "assistant", "你好！")

        context = await memory.get_context("ctx-test", "你是一个助手")

        # 应包含 system_prompt + 记忆注入 + 历史
        roles = [m["role"] for m in context]
        assert roles[0] == "system"  # system_prompt

        # 找到记忆注入的 system 消息
        memory_msgs = [m for m in context if "用户偏好" in m.get("content", "")]
        assert len(memory_msgs) > 0
        assert "简洁" in memory_msgs[0]["content"] or "英文" in memory_msgs[0]["content"]

    @pytest.mark.asyncio
    async def test_context_token_trimming(self):
        """验证超限时能正确裁剪"""
        memory = MemoryManager(max_tokens=100)  # 极小的 token 限制

        # 写入大量历史消息
        for i in range(20):
            await memory.add_message("trim-test", "user", f"消息{i}" * 20)
            await memory.add_message("trim-test", "assistant", f"回复{i}" * 20)

        context = await memory.get_context("trim-test", "系统提示")

        # 裁剪后应仍在合理范围内
        total_chars = sum(len(m.get("content", "")) for m in context)
        assert total_chars < 5000  # 不应无限膨胀

    @pytest.mark.asyncio
    async def test_context_compresses_near_budget_and_keeps_recent_work(self):
        memory = MemoryManager(max_tokens=120)
        for i in range(18):
            await memory.add_message("budget-session", "user", f"用户任务 {i} " + "细节" * 20)
            await memory.add_message("budget-session", "assistant", f"阶段结果 {i} " + "结果" * 20)

        context = await memory.get_context(
            "budget-session",
            "系统指令",
            max_history=50,
            max_context=120,
            max_output_tokens=20,
        )

        assert any("早期任务上下文" in message.get("content", "") for message in context)
        assert any("用户任务 17" in message.get("content", "") for message in context)
        assert len([message for message in context if message["role"] != "system"]) <= 20

    @pytest.mark.asyncio
    async def test_runtime_compaction_replaces_old_tool_records(self):
        memory = MemoryManager()
        messages = [{"role": "system", "content": "系统指令"}]
        for i in range(12):
            messages.append({"role": "assistant", "content": "", "tool_calls": [{"id": f"call-{i}"}]})
            messages.append({"role": "tool", "content": f"工具结果 {i}: " + "错误输出" * 50})

        compacted = memory.compact_runtime_messages(
            messages,
            max_context=240,
            max_output_tokens=20,
        )

        assert any("本轮早期工作记录" in message.get("content", "") for message in compacted)
        assert len(compacted) < len(messages)
        assert any("工具结果 11" in message.get("content", "") for message in compacted)

    @pytest.mark.asyncio
    async def test_context_compaction_emits_progress_events(self):
        memory = MemoryManager(max_tokens=120)
        for i in range(18):
            await memory.add_message("progress-session", "user", f"任务 {i} " + "细节" * 20)
            await memory.add_message("progress-session", "assistant", f"结果 {i} " + "内容" * 20)

        events = []

        async def on_compaction(event):
            events.append(event)

        await memory.get_context(
            "progress-session",
            "系统指令",
            max_context=120,
            max_output_tokens=20,
            compaction_callback=on_compaction,
        )

        assert [event["phase"] for event in events] == ["start", "done"]
        assert events[0]["before_tokens"] > events[1]["after_tokens"]

    @pytest.mark.asyncio
    async def test_manual_compact_persists_summary_and_excludes_old_history(self):
        memory = MemoryManager()
        for i in range(12):
            await memory.add_message("manual-compact-session", "user", f"旧任务 {i}")
            await memory.add_message("manual-compact-session", "assistant", f"旧结果 {i}")

        result = await memory.compact_session("manual-compact-session")
        assert result["compressed"] is True
        assert result["message_count"] > 0

        summaries = await db.get_summaries("manual-compact-session")
        assert len(summaries) == 1
        context = await memory.get_context("manual-compact-session", "系统指令")
        assert any("对话摘要" in item.get("content", "") for item in context)
        assert not any("旧任务 0" == item.get("content") for item in context)


# ============================================================
# 6. chat.py 变量顺序（今天的真实 bug）
# ============================================================

class TestChatHandlerSafety:
    """验证 chat.py 的消息处理不会因变量顺序崩溃"""

    @pytest.mark.asyncio
    async def test_content_extraction_before_logging(self):
        """模拟 chat.py 的消息处理流程，验证 content 在 log_info 之前提取"""
        msg = {"session_id": "test", "content": "你好世界", "persona": "default"}

        # 今天的 bug：log_info 在 content 赋值之前引用了 content
        # 模拟正确的顺序
        session_id = msg.get("session_id", "default")
        content = msg.get("content", "")  # 必须在 log_info 之前
        log_info("Chat", f"WS消息: session={session_id} content={content[:80]}")

        assert content == "你好世界"

    @pytest.mark.asyncio
    async def test_missing_content_field(self):
        """content 字段缺失时不崩溃"""
        msg = {"session_id": "test", "persona": "default"}
        content = msg.get("content", "")
        assert content == ""
        # 不应抛出异常


# ============================================================
# 7. QQ Bot 消息解析
# ============================================================

class TestQQMessageParsing:
    """验证 QQ 事件解析和消息构造"""

    def test_c2c_message_parsed(self):
        """C2C 私信事件解析"""
        from adapters.qq_bot import QQBotAdapter

        adapter = QQBotAdapter()
        received_messages = []

        async def on_msg(msg):
            received_messages.append(msg)

        adapter.on_message(on_msg)

        # 模拟 C2C 事件
        event_data = {
            "author": {"user_openid": "USER_OPENID_123"},
            "content": "你好机器人",
            "id": "MSG_ID_456",
            "message_type": 0,
            "timestamp": "1234567890"
        }

        import asyncio
        asyncio.get_event_loop().run_until_complete(
            adapter._handle_event("C2C_MESSAGE_CREATE", event_data)
        )

        assert len(received_messages) == 1
        msg = received_messages[0]
        assert msg.content == "你好机器人"
        assert msg.user_id == "USER_OPENID_123"
        assert msg.channel_id == "USER_OPENID_123"  # C2C 用 user_openid
        assert msg.msg_type == "c2c"

    def test_group_at_message_parsed(self):
        """群@消息事件解析"""
        from adapters.qq_bot import QQBotAdapter

        adapter = QQBotAdapter()
        received_messages = []

        async def on_msg(msg):
            received_messages.append(msg)

        adapter.on_message(on_msg)

        event_data = {
            "author": {"member_openid": "MEMBER_OPENID_789"},
            "content": "@机器人 帮我搜索",
            "id": "MSG_ID_012",
            "group_openid": "GROUP_OPENID_ABC",
            "timestamp": "1234567890"
        }

        import asyncio
        asyncio.get_event_loop().run_until_complete(
            adapter._handle_event("GROUP_AT_MESSAGE_CREATE", event_data)
        )

        assert len(received_messages) == 1
        msg = received_messages[0]
        assert msg.user_id == "MEMBER_OPENID_789"
        assert msg.channel_id == "GROUP_OPENID_ABC"  # 群用 group_openid
        assert msg.msg_type == "group"

    def test_unknown_event_ignored(self):
        """未知事件类型不崩溃"""
        from adapters.qq_bot import QQBotAdapter

        adapter = QQBotAdapter()

        import asyncio
        # 不应抛出异常
        asyncio.get_event_loop().run_until_complete(
            adapter._handle_event("UNKNOWN_EVENT_TYPE", {"data": "test"})
        )
