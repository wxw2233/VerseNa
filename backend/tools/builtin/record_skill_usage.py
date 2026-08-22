from db.database import db
from skills.manager import skill_manager
from tools.base import BaseTool, ToolContext
from tools.results import tool_error, tool_result


class RecordSkillUsageTool(BaseTool):
    name = "record_skill_usage"
    description = (
        "Record that an already loaded skill or slash command materially guided the current task. "
        "Do not call this merely because a skill appears in the index."
    )
    parameters = {
        "type": "object",
        "properties": {
            "skill_id": {
                "type": "string",
                "description": "Loaded skill ID or active slash command.",
            },
            "command": {
                "type": "string",
                "description": "Optional slash command that was actually adopted.",
            },
            "detail": {
                "type": "string",
                "description": "Short factual note about which instruction affected the work.",
            },
        },
        "required": ["skill_id"],
        "additionalProperties": False,
    }

    async def execute(
        self,
        skill_id: str,
        command: str = "",
        detail: str = "",
        _context: ToolContext | None = None,
        **kwargs,
    ) -> str:
        if _context is None:
            return tool_error("MISSING_CONTEXT", "Skill audit requires an active session context.")
        requested = str(skill_id or "").strip().lstrip("/")
        command_info = skill_manager.get_command(command or requested)
        skill = skill_manager.get_skill(requested)
        if command_info:
            canonical_skill_id = command_info["skill_id"]
            canonical_command = command_info["command"]
        elif skill:
            canonical_skill_id = skill["id"]
            canonical_command = ""
        else:
            return tool_error("SKILL_NOT_FOUND", f"Skill or command does not exist: {requested}")

        events = await db.list_skill_events(_context.session_id, limit=100)
        was_loaded = any(
            event.get("event_type") in {"loaded", "activated"}
            and event.get("skill_id") == canonical_skill_id
            for event in events
        )
        if not was_loaded:
            return tool_error(
                "SKILL_NOT_LOADED",
                "Only an explicitly loaded or activated skill can be recorded as adopted.",
                data={"skill_id": canonical_skill_id, "command": canonical_command},
            )
        event_id = await db.record_skill_event(
            _context.session_id,
            canonical_skill_id,
            "adopted",
            command=canonical_command,
            detail=str(detail or "")[:600],
        )
        return tool_result(True, data={
            "event_id": event_id,
            "skill_id": canonical_skill_id,
            "command": canonical_command,
            "event_type": "adopted",
        }, message="Skill adoption recorded.")


def register(registry):
    registry.register(RecordSkillUsageTool())
