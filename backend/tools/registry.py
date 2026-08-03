import importlib
import pkgutil
from pathlib import Path
from config import settings
from .base import BaseTool, ToolContext
from .results import tool_error

class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool):
        self._tools[tool.name] = tool

    def get_tool(self, name: str) -> BaseTool | None:
        return self._tools.get(name)

    def get_tools(self) -> list[dict]:
        return [t.to_openai_tool() for t in self._tools.values()]

    def create_context(self, session_id: str, *, stop_event=None) -> ToolContext:
        workspace = settings.TOOL_WORKSPACE
        workspace.mkdir(parents=True, exist_ok=True)
        return ToolContext(
            session_id=session_id,
            workspace=workspace,
            trust_mode_getter=lambda: bool(getattr(settings, "TRUST_MODE", False)),
            stop_event=stop_event,
        )

    async def execute(
        self,
        name: str,
        arguments: dict,
        *,
        context: ToolContext | None = None,
        confirmed: bool = False,
    ) -> str:
        tool = self._tools.get(name)
        if not tool:
            return tool_error("TOOL_NOT_FOUND", f"工具不存在: {name}")
        try:
            safe_arguments = {
                key: value
                for key, value in (arguments or {}).items()
                if key not in {"confirmed", "_confirmed", "_context", "context"}
            }
            context = context or self.create_context("default")
            return await tool.execute(
                **safe_arguments,
                _context=context,
                _confirmed=confirmed,
            )
        except Exception as e:
            return tool_error("TOOL_EXECUTION_FAILED", f"{name}: {type(e).__name__}: {e}")

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
