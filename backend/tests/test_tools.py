import json
import asyncio
import time

import httpx
import pytest
from tools.base import ToolContext
from tools.registry import ToolRegistry
from tools.builtin.verification_exec import _analyze_verification_output
from tools.web_utils import UnsafeUrlError, validate_public_http_url

def test_registry_loads_builtins():
    reg = ToolRegistry()
    reg.load_builtins()
    tools = reg.get_tools()
    names = [t["function"]["name"] for t in tools]
    assert "web_search" in names
    assert "code_exec" in names
    assert "load_skill" in names
    assert "ask_user_choice" in names
    assert "runtime_smoke" in names
    assert "task_checkpoint" in names
    assert "delegate_task" in names
    assert "delegate_tasks" in names
    assert "delegate_plan" in names
    assert "verification_exec" in names
    delegate = next(tool for tool in tools if tool["function"]["name"] == "delegate_task")
    assert "无需用户提醒" in delegate["function"]["description"]
    delegate_plan = next(tool for tool in tools if tool["function"]["name"] == "delegate_plan")
    node_schema = delegate_plan["function"]["parameters"]["properties"]["nodes"]["items"]
    assert "depends_on" in node_schema["required"]


def test_tool_catalog_exposes_groups_risk_and_role_profiles(registry):
    catalog = {item["name"]: item for item in registry.get_tool_catalog(role="main")}

    assert catalog["file_manager"]["group"] == "filesystem"
    assert catalog["code_exec"]["risk"] == "high"
    assert "main" in catalog["code_exec"]["roles"]
    assert "code_exec" not in {item["name"] for item in registry.get_tool_catalog(role="qq")}
    assert "file_manager" not in {item["name"] for item in registry.get_tool_catalog(role="qq")}
    assert "verification_exec" in {item["name"] for item in registry.get_tool_catalog(role="verifier")}


def test_role_profiles_keep_subagent_capabilities_separate(registry):
    explorer = {tool["function"]["name"] for tool in registry.get_tools(role="explorer")}
    researcher = {tool["function"]["name"] for tool in registry.get_tools(role="researcher")}
    executor = {tool["function"]["name"] for tool in registry.get_tools(role="executor")}

    assert "file_manager" in explorer
    assert "file_manager" in researcher
    assert "code_exec" not in explorer
    assert "code_exec" in executor
    assert "delegate_plan" not in executor


def test_tool_descriptions_are_grouped_for_agent_prompt(registry):
    descriptions = registry.format_tool_descriptions(role="main")

    assert "### 文件与执行" in descriptions
    assert "- file_manager:" in descriptions
    assert "### 记忆管理" in descriptions
    assert "- list_memory:" in descriptions


def test_tool_index_is_compact_and_keeps_tool_names(registry):
    index = registry.format_tool_index(role="main")

    assert "`file_manager`" in index
    assert "`code_exec`" in index
    assert "- file_manager:" not in index


@pytest.mark.asyncio
async def test_delegate_task_requires_model_context(registry, tool_context):
    result = json.loads(await registry.execute(
        "delegate_task",
        {"role": "explorer", "task": "检查项目结构"},
        context=tool_context,
    ))

    assert result["error"] == "SUBAGENT_UNAVAILABLE"


@pytest.mark.asyncio
async def test_verification_exec_runs_whitelisted_command_without_confirmation(registry, tool_context):
    result = json.loads(await registry.execute(
        "verification_exec",
        {"code": "python -m unittest", "check_id": "unit_tests", "timeout": 30},
        context=tool_context,
    ))

    assert result["success"] is True
    assert result["data"]["verification_kind"] == "python:unittest"
    assert result["data"]["exit_code"] == 0
    assert result["data"]["verification_quality"] == "empty"
    assert result["data"]["tests_discovered"] is False
    assert result["data"]["tests_executed"] == 0


@pytest.mark.parametrize(("kind", "arguments", "output", "quality", "count"), [
    ("python:unittest", [], "Ran 3 tests in 0.004s\n\nOK", "meaningful", 3),
    ("python:unittest", [], "Ran 0 tests in 0.000s\n\nOK", "empty", 0),
    ("python:pytest", ["-q"], "5 passed, 1 skipped in 0.20s", "meaningful", 6),
    ("python:pytest", ["-q"], "no tests ran in 0.01s", "empty", None),
    ("npm", ["test"], "Tests  52 passed (52)", "meaningful", 52),
    ("npm", ["run", "test"], "Tests: 1 failed, 7 passed, 8 total", "meaningful", 8),
    ("npm", ["test"], "custom runner completed", "unknown", None),
    ("tsc", ["--noEmit"], "", "not_applicable", None),
])
def test_verification_output_quality_parsing(kind, arguments, output, quality, count):
    result = _analyze_verification_output(kind, arguments, output)

    assert result["verification_quality"] == quality
    assert result["test_count"] == count


@pytest.mark.asyncio
@pytest.mark.parametrize("command", [
    "npx tsc --noEmit; npm test",
    "npm run lint -- --fix",
    "python -c print(1)",
    "git status",
])
async def test_verification_exec_rejects_shell_control_and_non_verification_commands(
    registry, tool_context, command,
):
    result = json.loads(await registry.execute(
        "verification_exec", {"code": command, "check_id": "security_test"}, context=tool_context,
    ))

    assert result["error"] == "VERIFICATION_COMMAND_DENIED"


@pytest.mark.asyncio
async def test_verification_exec_returns_real_process_failure_for_whitelisted_check(
    registry, tool_context,
):
    result = json.loads(await registry.execute(
        "verification_exec",
        {
            "code": "python -m unittest definitely_missing_test_module",
            "check_id": "unit_tests",
        },
        context=tool_context,
    ))

    assert result["error"] == "PROCESS_EXIT"
    assert result["data"]["exit_code"] != 0
    assert result["data"]["check_id"] == "unit_tests"
    assert result["data"]["verification_kind"] == "python:unittest"


@pytest.mark.asyncio
async def test_runtime_smoke_rejects_public_service_url(registry, tool_context):
    result = json.loads(await registry.execute(
        "runtime_smoke",
        {"mode": "http", "url": "https://example.com/health"},
        context=tool_context,
    ))

    assert result["error"] == "INVALID_RUNTIME_URL"


@pytest.mark.asyncio
async def test_runtime_smoke_checks_service_identity(registry, tool_context, monkeypatch):
    import tools.builtin.runtime_smoke as runtime_smoke

    class Response:
        status = 200
        headers = {"content-type": "application/json"}

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self, size):
            return json.dumps({
                "status": "ok",
                "service": "OtherService",
                "version": "1.0.0",
                "instance_id": "other:1:8002",
            }).encode("utf-8")

    class Opener:
        def open(self, *args, **kwargs):
            return Response()

    monkeypatch.setattr(runtime_smoke, "build_opener", lambda *args, **kwargs: Opener())
    result = json.loads(await registry.execute(
        "runtime_smoke",
        {"mode": "http", "url": "http://127.0.0.1:8002/health"},
        context=tool_context,
    ))

    assert result["error"] == "WRONG_SERVICE_OR_UNHEALTHY"
    assert result["data"]["identity"]["service"] == "OtherService"


@pytest.mark.asyncio
async def test_task_checkpoint_persists_and_merges(registry, tool_context, monkeypatch):
    import tools.builtin.task_checkpoint as checkpoint_tool

    state = {"task_checkpoint": "{}"}

    class FakeDatabase:
        async def get_session_meta(self, session_id):
            return {"task_checkpoint": state["task_checkpoint"]}

        async def set_session_meta(self, session_id, **updates):
            state.update(updates)

    monkeypatch.setattr(checkpoint_tool, "db", FakeDatabase())
    first = json.loads(await registry.execute(
        "task_checkpoint",
        {
            "action": "update",
            "phase": "实现",
            "completed": ["接口已完成"],
            "next_step": "运行冒烟",
        },
        context=tool_context,
    ))
    second = json.loads(await registry.execute(
        "task_checkpoint",
        {"action": "update", "validation": "runtime_smoke 通过"},
        context=tool_context,
    ))
    loaded = json.loads(await registry.execute(
        "task_checkpoint", {"action": "read"}, context=tool_context
    ))

    assert first["success"] is True
    assert second["data"]["checkpoint"]["phase"] == "实现"
    assert loaded["data"]["checkpoint"]["validation"] == "runtime_smoke 通过"


@pytest.mark.asyncio
async def test_ask_user_choice_normalizes_clickable_options(registry, tool_context):
    result = json.loads(await registry.execute(
        "ask_user_choice",
        {
            "question": "主要用途是什么？",
            "options": [
                {"label": "自己学习", "description": "快速查看函数图像"},
                {"label": "课堂演示"},
                {"label": "代码调试"},
            ],
        },
        context=tool_context,
    ))

    assert result["type"] == "user_choice"
    assert result["success"] is True
    assert [option["id"] for option in result["data"]["options"]] == ["A", "B", "C"]
    assert result["data"]["question"] == "主要用途是什么？"

def test_tool_format():
    reg = ToolRegistry()
    reg.load_builtins()
    tools = reg.get_tools()
    for t in tools:
        assert t["type"] == "function"
        assert "name" in t["function"]
        assert "parameters" in t["function"]


@pytest.mark.asyncio
async def test_code_exec_blocks_broad_git_stage(registry, tool_context):
    result = json.loads(await registry.execute(
        "code_exec",
        {"language": "shell", "code": "git add -A"},
        context=tool_context,
        confirmed=True,
    ))

    assert result["error"] == "BROAD_REPO_STAGE_BLOCKED"


def test_code_exec_decodes_windows_legacy_output():
    from tools.builtin.code_exec import _decode_output

    raw = "中文输出".encode("gb18030")
    assert _decode_output(raw) == "中文输出"


@pytest.fixture
def registry():
    value = ToolRegistry()
    value.load_builtins()
    return value


@pytest.fixture
def tool_context(tmp_path):
    return ToolContext("test-session", tmp_path, lambda: False)


@pytest.mark.asyncio
async def test_file_manager_rejects_model_supplied_confirmation(registry, tool_context):
    result = json.loads(await registry.execute(
        "file_manager",
        {
            "action": "write",
            "path": "note.txt",
            "content": "hello",
            "confirmed": True,
        },
        context=tool_context,
    ))

    assert result["type"] == "confirm"
    assert not tool_context.workspace.joinpath("note.txt").exists()


@pytest.mark.asyncio
async def test_file_manager_confirmed_write_and_read(registry, tool_context):
    written = json.loads(await registry.execute(
        "file_manager",
        {"action": "write", "path": "notes/note.txt", "content": "hello"},
        context=tool_context,
        confirmed=True,
    ))
    read = json.loads(await registry.execute(
        "file_manager",
        {"action": "read", "path": "notes/note.txt"},
        context=tool_context,
    ))

    assert written["success"] is True
    assert read["data"]["content"] == "hello"
    assert read["data"]["eof"] is True
    assert read["data"]["remaining_bytes"] == 0


@pytest.mark.asyncio
async def test_file_manager_read_does_not_block_stop_event(registry, tmp_path, monkeypatch):
    target = tmp_path / "slow.txt"
    target.write_text("content", encoding="utf-8")
    stop_event = asyncio.Event()
    context = ToolContext("stop-file-read", tmp_path, stop_event=stop_event)
    tool = registry.get_tool("file_manager")

    def slow_read(cancel_event, *args):
        while not cancel_event.is_set():
            time.sleep(0.01)
        return json.dumps({"success": False, "error": "CANCELLED"})

    monkeypatch.setattr(tool, "_read", slow_read)
    operation = asyncio.create_task(registry.execute(
        "file_manager",
        {"action": "read", "path": "slow.txt"},
        context=context,
    ))

    await asyncio.sleep(0.05)
    assert operation.done() is False
    stop_event.set()
    result = json.loads(await asyncio.wait_for(operation, timeout=1))

    assert result["error"] == "CANCELLED"


@pytest.mark.asyncio
async def test_file_manager_trust_mode_is_dynamic(registry, tmp_path):
    state = {"enabled": False}
    context = ToolContext("test-session", tmp_path, lambda: state["enabled"])

    first = json.loads(await registry.execute(
        "file_manager",
        {"action": "write", "path": "note.txt", "content": "first"},
        context=context,
    ))
    state["enabled"] = True
    second = json.loads(await registry.execute(
        "file_manager",
        {"action": "write", "path": "note.txt", "content": "second"},
        context=context,
    ))

    assert first["type"] == "confirm"
    assert second["success"] is True
    assert tmp_path.joinpath("note.txt").read_text(encoding="utf-8") == "second"


@pytest.mark.asyncio
async def test_file_manager_rejects_workspace_escape_and_sensitive_files(registry, tool_context):
    escaped = json.loads(await registry.execute(
        "file_manager",
        {"action": "read", "path": "../outside.txt"},
        context=tool_context,
    ))
    sensitive = json.loads(await registry.execute(
        "file_manager",
        {"action": "read", "path": ".env"},
        context=tool_context,
    ))

    assert escaped["error"] == "WORKSPACE_VIOLATION"
    assert sensitive["error"] == "WORKSPACE_VIOLATION"


@pytest.mark.asyncio
async def test_code_exec_requires_confirmation_and_runs_python(registry, tool_context):
    arguments = {"language": "python", "code": "print('hello')"}
    confirmation = json.loads(await registry.execute(
        "code_exec", arguments, context=tool_context
    ))
    executed = json.loads(await registry.execute(
        "code_exec", arguments, context=tool_context, confirmed=True
    ))

    assert confirmation["type"] == "confirm"
    assert executed["success"] is True
    assert executed["data"]["output"] == "hello"


@pytest.mark.asyncio
async def test_auto_approval_applies_to_file_changes_and_code_execution(registry, tmp_path):
    context = ToolContext(
        "auto-session",
        tmp_path,
        approval_mode="auto",
    )
    written = json.loads(await registry.execute(
        "file_manager",
        {"action": "write", "path": "auto.txt", "content": "ok"},
        context=context,
    ))
    executed = json.loads(await registry.execute(
        "code_exec",
        {"language": "python", "code": "print('auto')"},
        context=context,
    ))

    assert written["success"] is True
    assert executed["success"] is True
    assert executed["data"]["output"] == "auto"


@pytest.mark.asyncio
async def test_code_exec_timeout_terminates_process(registry, tool_context):
    result = json.loads(await registry.execute(
        "code_exec",
        {"language": "python", "code": "import time; time.sleep(10)", "timeout": 1},
        context=tool_context,
        confirmed=True,
    ))

    assert result["error"] == "TIMEOUT"
    assert result["data"]["exit_code"] != 0


@pytest.mark.asyncio
async def test_code_exec_honors_stop_event(registry, tmp_path):
    stop_event = asyncio.Event()
    context = ToolContext(
        "test-session",
        tmp_path,
        lambda: False,
        stop_event,
    )

    async def stop_soon():
        await asyncio.sleep(0.2)
        stop_event.set()

    stopper = asyncio.create_task(stop_soon())
    result = json.loads(await registry.execute(
        "code_exec",
        {"language": "python", "code": "import time; time.sleep(10)", "timeout": 20},
        context=context,
        confirmed=True,
    ))
    await stopper

    assert result["error"] == "CANCELLED"


@pytest.mark.asyncio
async def test_code_exec_caps_captured_output(registry, tool_context):
    result = json.loads(await registry.execute(
        "code_exec",
        {"language": "python", "code": "print('x' * 20000)"},
        context=tool_context,
        confirmed=True,
    ))

    assert result["success"] is True
    assert result["data"]["truncated"] is True
    assert "输出已截断" in result["data"]["output"]
    assert result["data"]["output"].endswith("x" * 100)
    assert len(result["data"]["output"].encode("utf-8")) <= 12000


@pytest.mark.asyncio
@pytest.mark.parametrize("url", [
    "http://127.0.0.1:8002/health",
    "http://localhost/",
    "http://169.254.169.254/latest/meta-data/",
    "file:///etc/passwd",
])
async def test_web_fetch_rejects_non_public_urls(url):
    with pytest.raises(UnsafeUrlError):
        await validate_public_http_url(url)


@pytest.mark.asyncio
async def test_web_fetch_extracts_html_and_limits_text(registry, tool_context, monkeypatch):
    import tools.builtin.web_fetch as web_fetch_module

    async def allow_test_url(url):
        return None

    body = "<html><title>Example</title><script>ignore me</script><body>" + ("content " * 500) + "</body></html>"
    transport = httpx.MockTransport(lambda request: httpx.Response(
        200,
        headers={"content-type": "text/html; charset=utf-8"},
        content=body.encode(),
        request=request,
    ))
    real_client = httpx.AsyncClient
    monkeypatch.setattr(web_fetch_module, "validate_public_http_url", allow_test_url)
    monkeypatch.setattr(
        web_fetch_module.httpx,
        "AsyncClient",
        lambda *args, **kwargs: real_client(transport=transport),
    )

    result = json.loads(await registry.execute(
        "web_fetch",
        {"url": "https://example.com/article", "max_length": 500},
        context=tool_context,
    ))

    assert result["success"] is True
    assert result["data"]["title"] == "Example"
    assert "ignore me" not in result["data"]["content"]
    assert len(result["data"]["content"]) == 500
    assert result["data"]["truncated"] is True


@pytest.mark.asyncio
async def test_web_search_reports_missing_explicit_provider_key(registry, tool_context, monkeypatch):
    tool = registry.get_tool("web_search")

    async def empty_config():
        return {}

    monkeypatch.setattr(tool, "_get_search_config", empty_config)
    result = json.loads(await registry.execute(
        "web_search",
        {"query": "VerseNa", "provider": "serpapi"},
        context=tool_context,
    ))

    assert result["error"] == "MISSING_API_KEY"


@pytest.mark.asyncio
async def test_web_search_does_not_expose_api_key_in_errors(registry, tool_context, monkeypatch):
    tool = registry.get_tool("web_search")
    secret = "secret-api-key"

    async def configured():
        return {"serpapi_key": secret}

    async def fail_provider(provider, query, api_key):
        request = httpx.Request("GET", f"https://serpapi.com/search?api_key={api_key}")
        response = httpx.Response(401, request=request)
        raise httpx.HTTPStatusError("unauthorized", request=request, response=response)

    monkeypatch.setattr(tool, "_get_search_config", configured)
    monkeypatch.setattr(tool, "_search_provider", fail_provider)
    raw_result = await registry.execute(
        "web_search",
        {"query": "VerseNa", "provider": "serpapi"},
        context=tool_context,
    )

    assert secret not in raw_result
    assert json.loads(raw_result)["error"] == "SEARCH_PROVIDER_FAILED"


def test_qq_does_not_expose_local_execution_tools():
    from api.qq_api import _qq_tools

    names = {tool["function"]["name"] for tool in _qq_tools()}
    assert "code_exec" not in names
    assert "file_manager" not in names


def test_memory_tools_expose_scope_and_delete_schema(registry):
    tools = {tool["function"]["name"]: tool["function"] for tool in registry.get_tools()}

    assert "save_memory" in tools
    assert "delete_memory" in tools
    save_parameters = tools["save_memory"]["parameters"]
    assert save_parameters["properties"]["scope"]["enum"] == ["global", "workspace"]
    assert tools["delete_memory"]["parameters"]["required"] == ["memory_id"]
    assert "list_memory" in tools
    assert "edit_memory" in tools
    assert tools["edit_memory"]["parameters"]["required"] == ["memory_id"]


@pytest.mark.asyncio
async def test_save_memory_uses_current_workspace_for_workspace_scope(registry, tmp_path):
    class FakeMemoryManager:
        def __init__(self):
            self.calls = []

        async def save_memory_manual(self, content, category="general", workspace_path=None):
            self.calls.append((content, category, workspace_path))
            return 42

    memory = FakeMemoryManager()
    registry.get_tool("save_memory")._memory = memory
    context = ToolContext("memory-session", tmp_path)

    result = json.loads(await registry.execute(
        "save_memory",
        {"content": "workspace-only fact", "category": "fact", "scope": "workspace"},
        context=context,
    ))

    assert result["success"] is True
    assert result["data"]["memory_id"] == 42
    assert result["data"]["scope"] == "workspace"
    assert result["data"]["workspace_path"] == str(tmp_path.resolve())
    assert memory.calls == [("workspace-only fact", "fact", str(tmp_path.resolve()))]


@pytest.mark.asyncio
async def test_save_memory_defaults_to_global_scope(registry, tmp_path):
    class FakeMemoryManager:
        async def save_memory_manual(self, content, category="general", workspace_path=None):
            assert workspace_path is None
            return 43

    registry.get_tool("save_memory")._memory = FakeMemoryManager()
    result = json.loads(await registry.execute(
        "save_memory",
        {"content": "global fact"},
        context=ToolContext("memory-session", tmp_path),
    ))

    assert result["success"] is True
    assert result["data"]["memory_id"] == 43
    assert result["data"]["scope"] == "global"
    assert result["data"]["workspace_path"] is None


@pytest.mark.asyncio
async def test_save_memory_rejects_workspace_scope_without_context(registry):
    tool = registry.get_tool("save_memory")
    tool._memory = object()

    result = json.loads(await tool.execute(
        content="workspace fact",
        scope="workspace",
        _context=None,
    ))

    assert result["error"] == "MISSING_CONTEXT"


@pytest.mark.asyncio
async def test_delete_memory_deletes_by_id(registry, tool_context, monkeypatch):
    import tools.builtin.delete_memory as delete_memory_module

    calls = []

    async def get_memory(memory_id, workspace_path=None):
        return {"id": memory_id, "scope": "global"}

    async def delete(memory_id):
        calls.append(memory_id)
        return True

    monkeypatch.setattr(delete_memory_module.db, "get_memory", get_memory)
    monkeypatch.setattr(delete_memory_module.db, "delete_memory", delete)
    result = json.loads(await registry.execute(
        "delete_memory",
        {"memory_id": 7},
        context=tool_context,
    ))

    assert result["success"] is True
    assert result["data"] == {"memory_id": 7, "deleted": True}
    assert calls == [7]


@pytest.mark.asyncio
async def test_delete_memory_reports_missing_id(registry, tool_context, monkeypatch):
    import tools.builtin.delete_memory as delete_memory_module

    async def get_memory(memory_id, workspace_path=None):
        return None

    async def delete(memory_id):
        return False

    monkeypatch.setattr(delete_memory_module.db, "get_memory", get_memory)
    monkeypatch.setattr(delete_memory_module.db, "delete_memory", delete)
    result = json.loads(await registry.execute(
        "delete_memory",
        {"memory_id": 999},
        context=tool_context,
    ))

    assert result["error"] == "MEMORY_NOT_FOUND"


@pytest.mark.asyncio
async def test_list_memory_returns_visible_memories(registry, tool_context, monkeypatch):
    import tools.builtin.list_memory as list_memory_module

    calls = []

    async def get_memories(limit=20, category=None, workspace_path=None):
        calls.append((limit, category, workspace_path))
        return [{"id": 1, "content": "visible", "scope": "global"}]

    monkeypatch.setattr(list_memory_module.db, "get_memories", get_memories)
    result = json.loads(await registry.execute(
        "list_memory",
        {"category": "fact", "limit": 12},
        context=tool_context,
    ))

    assert result["success"] is True
    assert result["data"]["count"] == 1
    assert calls == [(12, "fact", str(tool_context.workspace.resolve()))]


@pytest.mark.asyncio
async def test_edit_memory_updates_only_supplied_fields(registry, tool_context, monkeypatch):
    import tools.builtin.edit_memory as edit_memory_module

    calls = []
    current = {"id": 7, "content": "old", "category": "fact", "scope": "global"}

    async def get_memory(memory_id, workspace_path=None):
        return current.copy() if memory_id == 7 else None

    async def update_memory(memory_id, **fields):
        calls.append((memory_id, fields))
        return True

    monkeypatch.setattr(edit_memory_module.db, "get_memory", get_memory)
    monkeypatch.setattr(edit_memory_module.db, "update_memory", update_memory)
    result = json.loads(await registry.execute(
        "edit_memory",
        {"memory_id": 7, "content": "new content", "scope": "workspace"},
        context=tool_context,
    ))

    assert result["success"] is True
    assert calls == [
        (7, {
            "content": "new content",
            "category": None,
            "scope": "workspace",
            "workspace_path": str(tool_context.workspace.resolve()),
        })
    ]


@pytest.mark.asyncio
async def test_edit_memory_rejects_invisible_memory(registry, tool_context, monkeypatch):
    import tools.builtin.edit_memory as edit_memory_module

    async def get_memory(memory_id, workspace_path=None):
        return None

    monkeypatch.setattr(edit_memory_module.db, "get_memory", get_memory)
    result = json.loads(await registry.execute(
        "edit_memory",
        {"memory_id": 99, "content": "should not change"},
        context=tool_context,
    ))

    assert result["error"] == "MEMORY_NOT_FOUND"
