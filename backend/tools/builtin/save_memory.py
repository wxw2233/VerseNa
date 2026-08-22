from pathlib import Path
import inspect

from db.database import db
from tools.base import BaseTool, ToolContext
from tools.results import tool_error, tool_result


class SaveMemoryTool(BaseTool):
    name = "save_memory"
    description = (
        "Save a durable user preference, fact, or instruction. "
        "Use global scope for information that applies everywhere, or workspace "
        "scope for information specific to the current workspace."
    )
    parameters = {
        "type": "object",
        "properties": {
            "content": {
                "type": "string",
                "description": "The durable memory content to save.",
            },
            "category": {
                "type": "string",
                "enum": ["preference", "fact", "instruction", "general"],
                "description": "Memory category.",
            },
            "scope": {
                "type": "string",
                "enum": ["global", "workspace"],
                "description": (
                    "global applies to all workspaces; workspace applies only to "
                    "the current tool workspace. Defaults to global."
                ),
            },
            "auto_apply": {
                "type": "boolean",
                "description": (
                    "Whether this explicit memory may be used as an automatic preference. "
                    "Automatically extracted memories always default to false."
                ),
            },
        },
        "required": ["content"],
        "additionalProperties": False,
    }

    def __init__(self, memory_manager=None):
        self._memory = memory_manager

    async def execute(
        self,
        content: str = "",
        category: str = "general",
        scope: str = "global",
        auto_apply: bool = True,
        _context: ToolContext | None = None,
        **kwargs,
    ) -> str:
        content = str(content or "").strip()
        if not content:
            return tool_error("INVALID", "Memory content cannot be empty.")
        if scope not in {"global", "workspace"}:
            return tool_error("INVALID_SCOPE", "scope must be global or workspace.")
        if scope == "workspace" and _context is None:
            return tool_error("MISSING_CONTEXT", "Workspace-scoped memory requires tool context.")

        workspace_path = str(Path(_context.workspace).resolve()) if scope == "workspace" else None
        memory = getattr(_context, "memory_manager", None) if _context else None
        memory = memory or self._memory
        if not memory:
            return tool_error("MEMORY_UNAVAILABLE", "Memory service is not available.")
        try:
            signature = inspect.signature(memory.save_memory_manual)
            supports_governance = (
                "auto_apply" in signature.parameters
                or any(
                    parameter.kind == inspect.Parameter.VAR_KEYWORD
                    for parameter in signature.parameters.values()
                )
            )
        except (TypeError, ValueError):
            supports_governance = True
        if supports_governance:
            memory_id = await memory.save_memory_manual(
                content,
                category=category,
                workspace_path=workspace_path,
                auto_apply=bool(auto_apply),
            )
        else:
            # Older plugin MemoryManager implementations may not expose the
            # governance argument yet.  Keep them usable while preferring the
            # session-scoped implementation above.
            memory_id = await memory.save_memory_manual(
                content,
                category=category,
                workspace_path=workspace_path,
            )
            if not auto_apply:
                await db.update_memory(
                    memory_id,
                    workspace_path=str(_context.workspace.resolve()) if _context else None,
                    auto_apply=False,
                )
        return tool_result(
            True,
            data={
                "memory_id": memory_id,
                "message": f"Remembered: {content}",
                "scope": scope,
                "workspace_path": workspace_path,
                "auto_apply": bool(auto_apply),
            },
        )


def register(registry):
    # The active MemoryManager is supplied through ToolContext per session.
    registry.register(SaveMemoryTool())
