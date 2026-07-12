from db.database import db
from config import settings

class MemoryManager:
    def __init__(self, max_tokens: int = None):
        self.max_tokens = max_tokens or settings.MAX_CONTEXT_TOKENS

    def _estimate_tokens(self, messages: list[dict]) -> int:
        total = 0
        for msg in messages:
            total += len(msg.get("content", "")) // 2
        return total

    async def get_context(self, session_id: str, system_prompt: str = "") -> list[dict]:
        history = await db.get_history(session_id, limit=100)
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        for msg in history:
            messages.append({"role": msg["role"], "content": msg["content"]})

        while self._estimate_tokens(messages) > self.max_tokens and len(messages) > 2:
            if messages[0]["role"] == "system":
                messages.pop(1)
            else:
                messages.pop(0)

        return messages

    async def add_message(self, session_id: str, role: str, content: str, persona: str = "default"):
        await db.save_message(session_id, role, content, persona)
