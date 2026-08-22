import importlib
import pkgutil
import copy
import json
import time
import uuid
import asyncio
from pathlib import Path
from config import settings
from .base import BaseTool, ToolContext
from .results import tool_error
from agent.context_protocol import encode_tool_payload
from security_utils import redact_sensitive_text


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
    "verification_exec": {"group": "verification", "risk": "medium", "roles": {"main", "reviewer", "verifier"}},
    "runtime_smoke": {"group": "verification", "risk": "medium", "roles": {"main", "executor", "verifier"}},
    "service_status": {"group": "verification", "risk": "low", "roles": {"main", "executor", "verifier"}},
    "task_checkpoint": {"group": "workflow", "risk": "low", "roles": {"main", "qq", "executor"}},
    "project_map": {"group": "workflow", "risk": "low", "roles": {"main", "qq", "explorer", "researcher", "reviewer", "verifier", "executor"}},
    "ask_user_choice": {"group": "workflow", "risk": "low", "roles": {"main", "qq"}},
    "load_skill": {"group": "workflow", "risk": "low", "roles": {"main", "qq"}},
    "record_skill_usage": {"group": "workflow", "risk": "low", "roles": {"main", "qq"}},
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

    def get_tools(
        self,
        role: str | None = None,
        *,
        include_groups: set[str] | None = None,
        exclude_names: set[str] | None = None,
    ) -> list[dict]:
        """Return OpenAI tool schemas filtered by role and optional groups."""
        tools = []
        for name, tool in self._tools.items():
            if exclude_names and name in exclude_names:
                continue
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

    def format_tool_descriptions(
        self,
        role: str | None = None,
        *,
        exclude_names: set[str] | None = None,
    ) -> str:
        """Format the visible tool catalog into compact capability groups."""
        grouped = {}
        for tool in self.get_tools(role=role, exclude_names=exclude_names):
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

    def format_tool_index(
        self,
        role: str | None = None,
        *,
        exclude_names: set[str] | None = None,
    ) -> str:
        """Return a compact prompt index; detailed descriptions stay in tool schemas."""
        grouped = {}
        for tool in self.get_tools(role=role, exclude_names=exclude_names):
            name = tool["function"]["name"]
            group = self.get_tool_metadata(name)["group"]
            grouped.setdefault(group, []).append(f"`{name}`")
        return "\n".join(
            f"- {TOOL_GROUP_LABELS[group]}: {', '.join(names)}"
            for group, names in grouped.items()
        )

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
        memory_manager=None,
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
            memory_manager=memory_manager,
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
            return encode_tool_payload(
                tool_error("TOOL_NOT_FOUND", f"工具不存在: {name}"),
                source=name,
            )
        try:
            safe_arguments = {
                key: value
                for key, value in (arguments or {}).items()
                if key not in {"confirmed", "_confirmed", "_context", "context"}
            }
            context = context or self.create_context("default")
            operation_id = str(getattr(context, "operation_id", "") or "")
            if not operation_id:
                context.operation_sequence = int(getattr(context, "operation_sequence", 0) or 0) + 1
                operation_id = f"op_{context.session_id}_{context.operation_sequence}_{uuid.uuid4().hex[:6]}"
            attempt = max(1, int(getattr(context, "operation_attempt", 1) or 1))
            side_effect = self._side_effect_level(name, safe_arguments)
            task_state = (getattr(context, "agent_config", {}) or {}).get("task_state")
            goal_mode = str((task_state or {}).get("goal_mode") or "")
            paused_mutations = {
                "code_exec", "delegate_task", "delegate_tasks", "delegate_plan",
                "save_memory", "edit_memory", "delete_memory",
            }
            if name == "file_manager" and safe_arguments.get("action") in {
                "write", "find_replace", "copy", "move", "delete", "mkdir",
            }:
                paused_mutations.add(name)
            if goal_mode in {"pause", "report_only"} and name in paused_mutations:
                return redact_sensitive_text(encode_tool_payload(
                    {
                        "success": False,
                        "error": "USER_SCOPE_PAUSED",
                        "message": "当前用户目标要求暂停或仅报告，已阻止可能改变外部状态的操作。",
                        "data": {"goal_mode": goal_mode, "tool": name},
                    },
                    source=name,
                    target=str(safe_arguments)[:1000],
                ))
            signature = self._operation_signature(name, safe_arguments)
            ledger = getattr(context, "operation_ledger", None)
            if not isinstance(ledger, dict):
                ledger = {}
                context.operation_ledger = ledger
            previous = ledger.get(signature)
            if side_effect in {"medium", "high"} and isinstance(previous, dict) and previous.get("status") == "uncertain":
                payload = {
                    "success": False,
                    "error": "OPERATION_RETRY_REQUIRES_REVIEW",
                    "message": "上一次有副作用的操作结果不确定，重试前必须先查询当前状态，避免重复执行。",
                    "data": {
                        "operation_id": operation_id,
                        "previous_operation_id": previous.get("operation_id", ""),
                        "attempt": attempt,
                        "side_effect_level": side_effect,
                        "signature": signature,
                    },
                }
                return redact_sensitive_text(encode_tool_payload(
                    payload, source=name, target=str(safe_arguments)[:1000], operation_id=operation_id,
                ))
            started_at = time.time()
            ledger[signature] = {
                "operation_id": operation_id,
                "attempt": attempt,
                "side_effect_level": side_effect,
                "status": "started",
                "started_at": started_at,
            }
            result = await tool.execute(
                **safe_arguments,
                _context=context,
                _confirmed=confirmed,
            )
            target = ""
            if isinstance(safe_arguments, dict):
                target = str(
                    safe_arguments.get("path")
                    or safe_arguments.get("url")
                    or safe_arguments.get("cwd")
                    or safe_arguments.get("code")
                    or ""
                )
            encoded = encode_tool_payload(
                result,
                source=name,
                target=target,
                operation_id=operation_id,
            )
            try:
                payload = json.loads(encoded)
            except (TypeError, json.JSONDecodeError):
                payload = {"success": False, "error": "INVALID_TOOL_RESULT", "message": encoded}
            payload["operation"] = {
                "operation_id": operation_id,
                "attempt": attempt,
                "side_effect_level": side_effect,
                "started_at": started_at,
                "completed_at": time.time(),
            }
            error = str(payload.get("error") or "")
            uncertain = error in {"TIMEOUT", "TOOL_TIMEOUT", "CANCELLED", "EXECUTION_FAILED", "CONNECTION_FAILED"}
            ledger[signature] = {
                **ledger[signature],
                "status": "uncertain" if uncertain else "completed" if payload.get("success") is True else "failed",
                "completed_at": time.time(),
                "error": error,
            }
            return redact_sensitive_text(json.dumps(payload, ensure_ascii=False))
        except asyncio.CancelledError:
            # ReAct cancels the registry task when a tool exceeds its outer
            # timeout or the user stops generation.  A mutating operation may
            # already have reached the host, so retain an explicit uncertain
            # ledger entry instead of leaving it as "started" and allowing a
            # blind retry on the next tool call.
            try:
                if 'ledger' in locals() and 'signature' in locals():
                    ledger[signature] = {
                        **ledger.get(signature, {}),
                        "status": "uncertain",
                        "completed_at": time.time(),
                        "error": "CANCELLED",
                    }
            finally:
                raise
        except Exception as e:
            try:
                if 'ledger' in locals() and 'signature' in locals():
                    ledger[signature] = {
                        **ledger.get(signature, {}),
                        "status": "uncertain",
                        "completed_at": time.time(),
                        "error": "TOOL_EXECUTION_FAILED",
                    }
            except Exception:
                pass
            return encode_tool_payload(
                tool_error(
                    "TOOL_EXECUTION_FAILED",
                    redact_sensitive_text(f"{name}: {type(e).__name__}: {e}"),
                ),
                source=name,
                operation_id=str(getattr(context, "operation_id", "") or ""),
            )

    @staticmethod
    def _operation_signature(name: str, arguments: dict) -> str:
        return json.dumps([name, arguments], ensure_ascii=False, sort_keys=True, default=str)

    @staticmethod
    def _side_effect_level(name: str, arguments: dict) -> str:
        if name == "file_manager":
            return "medium" if arguments.get("action") in {"write", "find_replace", "copy", "move", "delete", "mkdir"} else "low"
        if name in {"code_exec", "delegate_task", "delegate_tasks", "delegate_plan"}:
            return "high"
        if name in {"save_memory", "edit_memory", "delete_memory"}:
            return "medium"
        return "low"

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
