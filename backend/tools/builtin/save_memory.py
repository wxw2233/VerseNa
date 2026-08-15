from pathlib import Path

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
        _context: ToolContext | None = None,
        **kwargs,
    ) -> str:
        content = str(content or "").strip()
        if not content:
            return tool_error("INVALID", "Memory content cannot be empty.")
        if scope not in {"global", "workspace"}:
            return tool_error("INVALID_SCOPE", "scope must be global or workspace.")
        if not self._memory:
            return tool_error("MEMORY_UNAVAILABLE", "Memory service is not available.")
        if scope == "workspace" and _context is None:
            return tool_error("MISSING_CONTEXT", "Workspace-scoped memory requires tool context.")

        workspace_path = str(Path(_context.workspace).resolve()) if scope == "workspace" else None
        memory_id = await self._memory.save_memory_manual(
            content,
            category=category,
            workspace_path=workspace_path,
        )
        return tool_result(
            True,
            data={
                "memory_id": memory_id,
                "message": f"Remembered: {content}",
                "scope": scope,
                "workspace_path": workspace_path,
            },
        )


def register(registry):
    # The chat API injects the active MemoryManager when an agent is created.
    registry.register(SaveMemoryTool())
