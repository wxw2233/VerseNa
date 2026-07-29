import pytest
from tools.registry import ToolRegistry

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
