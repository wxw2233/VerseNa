import json
import time
from typing import AsyncGenerator
from agent.models.base import BaseModelAdapter
from agent.memory import MemoryManager
from config import settings
from persona.manager import persona_manager

class ReActAgent:
    def __init__(self, model: BaseModelAdapter, memory: MemoryManager, tool_registry=None):
        self.model = model
        self.memory = memory
        self.tool_registry = tool_registry

    async def run(self, session_id: str, user_message: str, system_prompt: str = "", tools: list = None, persona: str = "default", confirm_callback=None) -> AsyncGenerator[dict, None]:
        await self.memory.add_message(session_id, "user", user_message, persona=persona)
        messages = await self.memory.get_context(session_id, system_prompt)

        full_response = ""
        loops = 0
        tool_seq = 0  # 工具调用序号

        try:
            while loops < settings.MAX_REACT_LOOPS:
                loops += 1
                chunk_content = ""
                tool_calls = []

                try:
                    async for chunk in self.model.chat(messages, tools=tools, stream=True):
                        if chunk.content:
                            chunk_content += chunk.content
                            yield {"type": "segment", "segment": {"type": "text", "content": chunk.content}}
                        if chunk.tool_calls:
                            tool_calls.extend(chunk.tool_calls)
                except Exception as e:
                    yield {"type": "segment", "segment": {"type": "text", "content": f"\n[连接错误] {e}"}}
                    break

                full_response += chunk_content

                if not tool_calls:
                    break

                messages.append({"role": "assistant", "content": chunk_content, "tool_calls": tool_calls})

                if not self.tool_registry:
                    yield {"type": "segment", "segment": {"type": "text", "content": "工具系统未配置"}}
                    break

                for tc in tool_calls:
                    func = tc.get("function", {})
                    tool_name = func.get("name", "")
                    try:
                        tool_args = json.loads(func.get("arguments") or "{}")
                    except json.JSONDecodeError:
                        tool_args = {}

                    tool_seq += 1
                    tool_call_id = f"tc_{int(time.time() * 1000):013d}_{tool_seq:03d}"

                    # 发送工具调用开始
                    yield {"type": "segment", "segment": {
                        "type": "tool",
                        "tool_call_id": tool_call_id,
                        "tool_name": tool_name,
                        "tool_args": tool_args,
                        "status": "running"
                    }}

                    result = await self.tool_registry.execute(tool_name, tool_args)

                    # 检查是否为 confirm
                    try:
                        result_data = json.loads(result)
                        if result_data.get("type") == "confirm" and confirm_callback:
                            yield {"type": "confirm", "data": result_data}
                            confirmed = await confirm_callback(result_data)
                            if confirmed:
                                tool_args["confirmed"] = True
                                result = await self.tool_registry.execute(tool_name, tool_args)
                                result_data = json.loads(result)
                            else:
                                result_data = {"success": False, "error": "USER_DENIED", "message": "用户取消了操作"}
                                result = json.dumps(result_data, ensure_ascii=False)
                    except (json.JSONDecodeError, TypeError):
                        result_data = {}

                    # 生成结果摘要
                    result_summary = self._make_summary(tool_name, result_data, result)
                    result_detail = result[:3000] if isinstance(result, str) else str(result)[:3000]

                    # 发送工具调用完成
                    yield {"type": "segment", "segment": {
                        "type": "tool",
                        "tool_call_id": tool_call_id,
                        "tool_name": tool_name,
                        "status": "done",
                        "result_summary": result_summary,
                        "result_detail": result_detail
                    }}

                    messages.append({"role": "tool", "tool_call_id": tc.get("id", ""), "content": result})

        except Exception as e:
            yield {"type": "error", "message": str(e)}

        # done 事件
        emotion = persona_manager.get_emotion_engine(persona) if hasattr(self, '_persona_manager') else None
        emoji = ""
        yield {"type": "done", "emoji": emoji}

        await self.memory.add_message(session_id, "assistant", full_response, persona=persona)
        await self.memory.post_conversation(session_id, user_message, full_response)

    def _make_summary(self, tool_name, result_data, result):
        """生成工具结果摘要"""
        if not result_data:
            return str(result)[:100] if result else ""

        if tool_name == "web_search":
            count = result_data.get("data", {}).get("count", 0)
            return f"找到 {count} 条结果" if count else "搜索完成"
        elif tool_name == "code_exec":
            return "执行完成" if result_data.get("success") else "执行出错"
        elif tool_name == "file_manager":
            action = result_data.get("data", {})
            if "content" in str(action):
                return "读取完成"
            return "操作完成" if result_data.get("success") else "操作失败"
        else:
            return "完成" if result_data.get("success") else "失败"