import json
from typing import AsyncGenerator
from agent.models.base import BaseModelAdapter
from agent.memory import MemoryManager
from config import settings

class ReActAgent:
    def __init__(self, model: BaseModelAdapter, memory: MemoryManager, tool_registry=None):
        self.model = model
        self.memory = memory
        self.tool_registry = tool_registry

    async def run(self, session_id: str, user_message: str, system_prompt: str = "", tools: list = None) -> AsyncGenerator[dict, None]:
        await self.memory.add_message(session_id, "user", user_message)
        messages = await self.memory.get_context(session_id, system_prompt)

        full_response = ""
        loops = 0

        while loops < settings.MAX_REACT_LOOPS:
            loops += 1
            chunk_content = ""
            tool_calls = []

            try:
                async for chunk in self.model.chat(messages, tools=tools, stream=True):
                    if chunk.content:
                        chunk_content += chunk.content
                        yield {"type": "answer", "content": chunk.content}
                    if chunk.tool_calls:
                        tool_calls.extend(chunk.tool_calls)
            except Exception as e:
                yield {"type": "answer", "content": f"\n[连接错误] {e}"}
                break

            full_response += chunk_content

            if not tool_calls:
                break

            messages.append({"role": "assistant", "content": chunk_content, "tool_calls": tool_calls})

            if not self.tool_registry:
                yield {"type": "thinking", "content": "工具系统未配置"}
                break

            for tc in tool_calls:
                func = tc.get("function", {})
                tool_name = func.get("name", "")
                tool_args = json.loads(func.get("arguments", "{}"))
                yield {"type": "tool_call", "content": json.dumps({"name": tool_name, "args": tool_args}, ensure_ascii=False)}

                result = await self.tool_registry.execute(tool_name, tool_args)
                messages.append({"role": "tool", "tool_call_id": tc.get("id", ""), "content": result})
                yield {"type": "tool_result", "content": result}

        await self.memory.add_message(session_id, "assistant", full_response)
