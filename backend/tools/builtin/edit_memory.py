from pathlib import Path

from tools.base import BaseTool, ToolContext
from tools.results import tool_error, tool_result
from db.database import db


class EditMemoryTool(BaseTool):
    name = "edit_memory"
    description = (
        "Edit a visible saved memory by memory_id. Only supplied fields change. "
        "When scope is workspace, the current workspace is used automatically."
    )
    parameters = {
        "type": "object",
        "properties": {
            "memory_id": {"type": "integer", "description": "Memory ID from list_memory."},
            "content": {"type": "string", "description": "Replacement memory content."},
            "category": {
                "type": "string",
                "enum": ["preference", "fact", "instruction", "general"],
                "description": "Replacement memory category.",
            },
            "scope": {
                "type": "string",
                "enum": ["global", "workspace"],
                "description": "Change visibility scope.",
            },
        },
        "required": ["memory_id"],
        "additionalProperties": False,
    }

    async def execute(
        self,
        memory_id: int | str | None = None,
        content: str | None = None,
        category: str | None = None,
        scope: str | None = None,
        _context: ToolContext | None = None,
        **kwargs,
    ) -> str:
        if _context is None:
            return tool_error("MISSING_CONTEXT", "Memory editing requires tool context.")
        try:
            memory_id = int(memory_id)
        except (TypeError, ValueError):
            return tool_error("INVALID_MEMORY_ID", "memory_id must be an integer.")
        if memory_id <= 0:
            return tool_error("INVALID_MEMORY_ID", "memory_id must be positive.")
        if content is not None and not str(content).strip():
            return tool_error("INVALID_CONTENT", "Memory content cannot be empty.")
        if scope is not None and scope not in {"global", "workspace"}:
            return tool_error("INVALID_SCOPE", "scope must be global or workspace.")
        if category is not None and category not in {"preference", "fact", "instruction", "general"}:
            return tool_error("INVALID_CATEGORY", "Unsupported memory category.")
        if content is None and category is None and scope is None:
            return tool_error("NO_CHANGES", "Provide content, category, or scope to edit.")

        workspace_path = str(Path(_context.workspace).resolve())
        visible = await db.get_memory(memory_id, workspace_path=workspace_path)
        if not visible:
            return tool_error(
                "MEMORY_NOT_FOUND",
                f"No visible memory found for memory_id={memory_id}.",
                data={"memory_id": memory_id},
            )
        updated = await db.update_memory(
            memory_id,
            content=str(content).strip() if content is not None else None,
            category=category,
            scope=scope,
            workspace_path=workspace_path,
        )
        if not updated:
            return tool_error("MEMORY_NOT_FOUND", f"No visible memory found for memory_id={memory_id}.")
        result = await db.get_memory(memory_id, workspace_path=workspace_path)
        return tool_result(True, data={"memory_id": memory_id, "memory": result})


def register(registry):
    registry.register(EditMemoryTool())
