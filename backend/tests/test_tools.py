import json
import asyncio

import httpx
import pytest
from tools.base import ToolContext
from tools.registry import ToolRegistry
from tools.web_utils import UnsafeUrlError, validate_public_http_url

def test_registry_loads_builtins():
    reg = ToolRegistry()
    reg.load_builtins()
    tools = reg.get_tools()
    names = [t["function"]["name"] for t in tools]
    assert "web_search" in names
    assert "code_exec" in names
    assert "load_skill" in names

def test_tool_format():
    reg = ToolRegistry()
    reg.load_builtins()
    tools = reg.get_tools()
    for t in tools:
        assert t["type"] == "function"
        assert "name" in t["function"]
        assert "parameters" in t["function"]


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
    context = ToolContext("test-session", tmp_path, lambda: False, stop_event)

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
