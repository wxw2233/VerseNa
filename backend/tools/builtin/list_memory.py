from tools.base import BaseTool, ToolContext
from tools.results import tool_error, tool_result
from db.database import db


class ListMemoryTool(BaseTool):
    name = "list_memory"
    description = (
        "List saved memories visible in the current workspace. This includes global "
        "memories and memories belonging to the current workspace. Use memory_id "
        "from the result before editing or deleting a memory."
    )
    parameters = {
        "type": "object",
        "properties": {
            "category": {
                "type": "string",
                "enum": ["preference", "fact", "instruction", "general"],
                "description": "Optional category filter.",
            },
            "limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": 100,
                "description": "Maximum number of memories to return. Defaults to 20.",
            },
        },
        "additionalProperties": False,
    }

    async def execute(
        self,
        category: str | None = None,
        limit: int = 20,
        _context: ToolContext | None = None,
        **kwargs,
    ) -> str:
        if _context is None:
            return tool_error("MISSING_CONTEXT", "Listing memories requires tool context.")
        try:
            limit = max(1, min(int(limit), 100))
        except (TypeError, ValueError):
            return tool_error("INVALID_LIMIT", "limit must be an integer between 1 and 100.")
        memories = await db.get_memories(
            limit=limit,
            category=category,
            workspace_path=str(_context.workspace.resolve()),
        )
        return tool_result(True, data={"memories": memories, "count": len(memories)})


def register(registry):
    registry.register(ListMemoryTool())
