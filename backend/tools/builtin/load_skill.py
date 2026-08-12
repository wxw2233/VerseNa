import json

from skills.manager import skill_manager
from tools.base import BaseTool
from db.database import db


class LoadSkillTool(BaseTool):
    name = "load_skill"
    description = "按技能 ID 加载完整技能指令和知识。使用任何可用技能前必须先调用此工具。"
    parameters = {
        "type": "object",
        "properties": {
            "skill_id": {
                "type": "string",
                "description": "可用技能列表中的技能 ID",
            },
        },
        "required": ["skill_id"],
    }

    async def execute(
        self,
        skill_id: str,
        _context=None,
        _confirmed: bool = False,
    ) -> str:
        try:
            context = skill_manager.get_skill_context(skill_id)
            command = skill_manager.get_command(skill_id)
            if _context is not None and command:
                try:
                    await db.set_session_meta(
                        _context.session_id,
                        active_skill_command=command["command"],
                        active_skill_arguments="",
                    )
                except Exception:
                    # Skill loading must still work if session persistence is unavailable.
                    pass
            return json.dumps(
                {
                    "success": True,
                    "skill_id": skill_id,
                    "active_command": command["command"] if command else "",
                    "context": context,
                },
                ensure_ascii=False,
            )
        except ValueError as exc:
            return json.dumps(
                {
                    "success": False,
                    "error": str(exc),
                    "available_skill_ids": [skill["id"] for skill in skill_manager.list_skills()],
                    "available_command_ids": [
                        command["command"] for command in skill_manager.list_commands()
                    ],
                },
                ensure_ascii=False,
            )


def register(registry):
    registry.register(LoadSkillTool())
