import json

from skills.manager import skill_manager
from tools.base import BaseTool


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

    async def execute(self, skill_id: str) -> str:
        try:
            context = skill_manager.get_skill_context(skill_id)
            return json.dumps(
                {"success": True, "skill_id": skill_id, "context": context},
                ensure_ascii=False,
            )
        except ValueError as exc:
            return json.dumps(
                {
                    "success": False,
                    "error": str(exc),
                    "available_skill_ids": [skill["id"] for skill in skill_manager.list_skills()],
                },
                ensure_ascii=False,
            )


def register(registry):
    registry.register(LoadSkillTool())
