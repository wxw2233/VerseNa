import importlib
import pkgutil
from pathlib import Path
from .base import BaseTool

class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool):
        self._tools[tool.name] = tool

    def get_tool(self, name: str) -> BaseTool | None:
        return self._tools.get(name)

    def get_tools(self) -> list[dict]:
        return [t.to_openai_tool() for t in self._tools.values()]

    async def execute(self, name: str, arguments: dict) -> str:
        tool = self._tools.get(name)
        if not tool:
            return f"Error: tool '{name}' not found"
        try:
            return await tool.execute(**arguments)
        except Exception as e:
            return f"Error executing {name}: {e}"

    def load_builtins(self):
        builtin_dir = Path(__file__).parent / "builtin"
        for _, module_name, _ in pkgutil.iter_modules([str(builtin_dir)]):
            if module_name.startswith("_"):
                continue
            module = importlib.import_module(f"tools.builtin.{module_name}")
            if hasattr(module, "register"):
                module.register(self)

tool_registry = ToolRegistry()
tool_registry.load_builtins()
