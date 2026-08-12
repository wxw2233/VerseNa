import json
import uuid

from tools.base import BaseTool


MAX_OPTIONS = 6


class AskUserChoiceTool(BaseTool):
    name = "ask_user_choice"
    description = (
        "向用户展示可直接点击的单选项并暂停等待选择。"
        "当需要用户从 2 到 6 个明确选项中选择时必须使用。"
        "即使技能要求列出 A/B/C/D，也不要把选项写成普通文本；应调用本工具。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": "需要用户回答的单个问题",
            },
            "options": {
                "type": "array",
                "minItems": 2,
                "maxItems": MAX_OPTIONS,
                "description": "按显示顺序排列的候选项",
                "items": {
                    "type": "object",
                    "properties": {
                        "label": {
                            "type": "string",
                            "description": "简短、可独立理解的选项名称",
                        },
                        "description": {
                            "type": "string",
                            "description": "可选的补充说明",
                        },
                    },
                    "required": ["label"],
                },
            },
        },
        "required": ["question", "options"],
    }

    async def execute(
        self,
        question: str,
        options: list,
        _context=None,
        _confirmed: bool = False,
    ) -> str:
        question = str(question or "").strip()[:500]
        if not question:
            return json.dumps({
                "type": "user_choice",
                "success": False,
                "error": "QUESTION_REQUIRED",
                "message": "选项问题不能为空",
            }, ensure_ascii=False)

        normalized = []
        for item in options or []:
            if isinstance(item, dict):
                label = str(item.get("label") or "").strip()[:160]
                description = str(item.get("description") or "").strip()[:300]
            elif isinstance(item, str):
                label = item.strip()[:160]
                description = ""
            else:
                continue
            if not label:
                continue
            normalized.append({
                "id": chr(ord("A") + len(normalized)),
                "label": label,
                "description": description,
            })
            if len(normalized) >= MAX_OPTIONS:
                break

        if len(normalized) < 2:
            return json.dumps({
                "type": "user_choice",
                "success": False,
                "error": "OPTIONS_REQUIRED",
                "message": "至少需要两个有效选项",
            }, ensure_ascii=False)

        return json.dumps({
            "type": "user_choice",
            "success": True,
            "data": {
                "choice_id": f"choice_{uuid.uuid4().hex}",
                "question": question,
                "options": normalized,
            },
        }, ensure_ascii=False)


def register(registry):
    registry.register(AskUserChoiceTool())
