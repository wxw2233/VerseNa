import importlib
import pkgutil
import copy
from pathlib import Path
from config import settings
from .base import BaseTool, ToolContext
from .results import tool_error


# Centralized capability metadata keeps tool exposure rules in one place. The
# tool implementations remain independent so their execution and approval
# behavior does not change when the catalog changes.
TOOL_METADATA = {
    "file_manager": {"group": "filesystem", "risk": "medium", "roles": {"main", "explorer", "researcher", "reviewer", "verifier", "executor"}},
    "code_exec": {"group": "filesystem", "risk": "high", "roles": {"main", "executor"}},
    "web_search": {"group": "web", "risk": "low", "roles": {"main", "qq", "explorer", "researcher", "reviewer", "executor"}},
    "web_fetch": {"group": "web", "risk": "low", "roles": {"main", "qq", "explorer", "researcher", "reviewer", "executor"}},
    "save_memory": {"group": "memory", "risk": "low", "roles": {"main", "qq"}},
    "list_memory": {"group": "memory", "risk": "low", "roles": {"main", "qq", "explorer", "researcher", "reviewer", "verifier", "executor"}},
    "edit_memory": {"group": "memory", "risk": "medium", "roles": {"main", "qq"}},
    "delete_memory": {"group": "memory", "risk": "medium", "roles": {"main", "qq"}},
    "delegate_task": {"group": "delegation", "risk": "medium", "roles": {"main", "qq"}},
    "delegate_tasks": {"group": "delegation", "risk": "medium", "roles": {"main", "qq"}},
    "delegate_plan": {"group": "delegation", "risk": "medium", "roles": {"main", "qq"}},
    "verification_exec": {"group": "verification", "risk": "medium", "roles": {"main", "qq", "reviewer", "verifier"}},
    "runtime_smoke": {"group": "verification", "risk": "medium", "roles": {"main", "qq", "executor", "verifier"}},
    "task_checkpoint": {"group": "workflow", "risk": "low", "roles": {"main", "qq", "executor"}},
    "ask_user_choice": {"group": "workflow", "risk": "low", "roles": {"main", "qq"}},
    "load_skill": {"group": "workflow", "risk": "low", "roles": {"main", "qq"}},
    "calculator": {"group": "utility", "risk": "low", "roles": {"main", "qq", "executor"}},
    "datetime": {"group": "utility", "risk": "low", "roles": {"main", "qq", "executor"}},
}

TOOL_GROUP_LABELS = {
    "filesystem": "文件与执行",
    "web": "网络访问",
    "memory": "记忆管理",
    "delegation": "子代理",
    "verification": "验证与诊断",
    "workflow": "交互与工作流",
    "utility": "基础能力",
    "other": "其他",
}


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool):
        self._tools[tool.name] = tool

    def get_tool(self, name: str) -> BaseTool | None:
        return self._tools.get(name)

    def get_tools(self, role: str | None = None, *, include_groups: set[str] | None = None) -> list[dict]:
        """Return OpenAI tool schemas filtered by role and optional groups."""
        tools = []
        for name, tool in self._tools.items():
            metadata = TOOL_METADATA.get(name, {})
            if role and role not in metadata.get("roles", {"main"}):
                continue
            if include_groups and metadata.get("group") not in include_groups:
                continue
            tools.append(tool.to_openai_tool())
        return tools

    def get_tool_metadata(self, name: str) -> dict:
        metadata = TOOL_METADATA.get(name, {})
        return {
            "group": metadata.get("group", "other"),
            "risk": metadata.get("risk", "unknown"),
            "roles": sorted(metadata.get("roles", {"main"})),
        }

    def get_tool_catalog(self, role: str | None = None) -> list[dict]:
        """Return UI/API-facing tool information without exposing schemas."""
        tools = []
        for tool in self.get_tools(role=role):
            name = tool["function"]["name"]
            tools.append({
                "name": name,
                "description": tool["function"]["description"],
                **self.get_tool_metadata(name),
            })
        return tools

    def format_tool_descriptions(self, role: str | None = None) -> str:
        """Format the visible tool catalog into compact capability groups."""
        grouped = {}
        for tool in self.get_tools(role=role):
            function = tool["function"]
            group = self.get_tool_metadata(function["name"])["group"]
            grouped.setdefault(group, []).append(
                f"- {function['name']}: {function['description']}"
            )
        sections = []
        for group in TOOL_GROUP_LABELS:
            if group in grouped:
                sections.append(f"### {TOOL_GROUP_LABELS[group]}\n" + "\n".join(grouped[group]))
        return "\n\n".join(sections)

    def create_context(
        self,
        session_id: str,
        *,
        workspace: Path | str | None = None,
        approval_mode: str = "ask",
        stop_event=None,
        model=None,
        progress_callback=None,
        agent_config: dict | None = None,
        confirm_callback=None,
    ) -> ToolContext:
        workspace = Path(workspace or settings.TOOL_WORKSPACE).expanduser().resolve()
        workspace.mkdir(parents=True, exist_ok=True)
        return ToolContext(
            session_id=session_id,
            workspace=workspace,
            stop_event=stop_event,
            approval_mode=approval_mode if approval_mode in {"ask", "auto"} else "ask",
            model=model,
            progress_callback=progress_callback,
            agent_config=dict(agent_config or {}),
            confirm_callback=confirm_callback,
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

    def subset(self, names: set[str]) -> "ToolRegistry":
        registry = ToolRegistry()
        for name in names:
            tool = self._tools.get(name)
            if tool:
                registry.register(copy.copy(tool))
        return registry

    def for_role(self, role: str) -> "ToolRegistry":
        """Create a registry containing only tools intended for a role."""
        names = {
            name for name, metadata in TOOL_METADATA.items()
            if role in metadata.get("roles", set()) and name in self._tools
        }
        return self.subset(names)

tool_registry = ToolRegistry()
tool_registry.load_builtins()
