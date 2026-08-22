from tools.base import BaseTool, ToolContext
from tools.results import tool_error, tool_result
from db.database import db
from pathlib import Path
import inspect
from agent.task_state import workspace_id


class DeleteMemoryTool(BaseTool):
    name = "delete_memory"
    description = "Delete one saved memory by its memory_id. Use only when removal is requested or clearly necessary."
    parameters = {
        "type": "object",
        "properties": {
            "memory_id": {
                "type": "integer",
                "description": "The numeric ID returned by save_memory or memory listing.",
            },
        },
        "required": ["memory_id"],
        "additionalProperties": False,
    }

    @staticmethod
    def _supported_kwargs(function, values):
        """Adapt old database adapters without retrying a failed operation."""
        try:
            signature = inspect.signature(function)
        except (TypeError, ValueError):
            return dict(values)
        if any(
            parameter.kind == inspect.Parameter.VAR_KEYWORD
            for parameter in signature.parameters.values()
        ):
            return dict(values)
        return {
            key: value for key, value in values.items()
            if key in signature.parameters
        }

    async def execute(
        self,
        memory_id: int | str | None = None,
        _context: ToolContext | None = None,
        **kwargs,
    ) -> str:
        if _context is None:
            return tool_error("MISSING_CONTEXT", "Memory deletion requires tool context.")
        try:
            memory_id = int(memory_id)
        except (TypeError, ValueError):
            return tool_error("INVALID_MEMORY_ID", "memory_id must be an integer.")
        if memory_id <= 0:
            return tool_error("INVALID_MEMORY_ID", "memory_id must be positive.")

        workspace_path = str(Path(_context.workspace).resolve())
        current_project_id = workspace_id(workspace_path)
        visible = await db.get_memory(
            memory_id,
            **self._supported_kwargs(
                db.get_memory,
                {
                    "workspace_path": workspace_path,
                    "project_id": current_project_id,
                },
            ),
        )
        if not visible:
            return tool_error(
                "MEMORY_NOT_FOUND",
                f"No visible memory found for memory_id={memory_id}.",
                data={"memory_id": memory_id},
            )
        deleted = await db.delete_memory(
            memory_id,
            **self._supported_kwargs(
                db.delete_memory,
                {
                    "workspace_path": workspace_path,
                    "project_id": current_project_id,
                },
            ),
        )
        if not deleted:
            return tool_error(
                "MEMORY_NOT_FOUND",
                f"No memory found for memory_id={memory_id}.",
                data={"memory_id": memory_id},
            )
        return tool_result(True, data={"memory_id": memory_id, "deleted": True})


def register(registry):
    registry.register(DeleteMemoryTool())
