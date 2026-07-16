import json
from tools.base import BaseTool

class SaveMemoryTool(BaseTool):
    name = "save_memory"
    description = "保存一条长期记忆（用户偏好、事实或指令），记忆会跨会话保留"
    parameters = {
        "type": "object",
        "properties": {
            "content": {"type": "string", "description": "记忆内容，如'用户喜欢简洁的回答'"},
            "category": {
                "type": "string",
                "enum": ["preference", "fact", "instruction", "general"],
                "description": "分类：preference=偏好, fact=事实, instruction=指令"
            }
        },
        "required": ["content"]
    }

    def __init__(self, memory_manager=None):
        self._memory = memory_manager

    async def execute(self, content='', category='general', **kwargs):
        if not content:
            return json.dumps({"success": False, "error": "INVALID", "message": "记忆内容不能为空"}, ensure_ascii=False)
        if self._memory:
            await self._memory.save_memory_manual(content, category=category)
        return json.dumps({"success": True, "data": {"message": f"已记住：{content}"}}, ensure_ascii=False)

def register(registry):
    # 注意：需要在 main.py 中注入 memory_manager
    registry.register(SaveMemoryTool())
