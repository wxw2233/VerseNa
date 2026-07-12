import json
from typing import AsyncGenerator
from agent.models.base import BaseModelAdapter
from agent.memory import MemoryManager
from config import settings

class ReActAgent:
    def __init__(self, model: BaseModelAdapter, memory: MemoryManager):
        self.model = model
        self.memory = memory

    async def run(self, session_id: str, user_message: str, system_prompt: str = "", tools: list = None) -> AsyncGenerator[dict, None]:
        await self.memory.add_message(session_id, "user", user_message)
        messages = await self.memory.get_context(session_id, system_prompt)

        full_response = ""
        loops = 0

        while loops < settings.MAX_REACT_LOOPS:
            loops += 1
            chunk_content = ""
            tool_calls = []

            async for chunk in self.model.chat(messages, tools=tools, stream=True):
                if chunk.content:
                    chunk_content += chunk.content
                    yield {"type": "answer", "content": chunk.content}
                if chunk.tool_calls:
                    tool_calls.extend(chunk.tool_calls)

            full_response += chunk_content

            if not tool_calls:
                break

            messages.append({"role": "assistant", "content": chunk_content, "tool_calls": tool_calls})
            for tc in tool_calls:
                yield {"type": "tool_call", "content": json.dumps(tc, ensure_ascii=False)}

            yield {"type": "thinking", "content": "需要调用工具，但工具系统尚未实现，停止循环。"}
            break

        await self.memory.add_message(session_id, "assistant", full_response)
