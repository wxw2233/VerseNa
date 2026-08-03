import json
import time
import inspect
import asyncio
from typing import AsyncGenerator
from agent.models.base import BaseModelAdapter
from agent.memory import MemoryManager
from config import settings
from persona.manager import persona_manager

class ReActAgent:
    def __init__(self, model: BaseModelAdapter, memory: MemoryManager, tool_registry=None, max_steps: int = None):
        self.model = model
        self.memory = memory
        self.tool_registry = tool_registry
        self.max_steps = max_steps or settings.MAX_REACT_LOOPS

    def _chat_kwargs(self, tools, stream, temperature, top_p, max_tokens):
        """Only pass optional generation args supported by the adapter."""
        kwargs = {
            "tools": tools,
            "stream": stream,
            "temperature": temperature,
            "top_p": top_p,
            "max_tokens": max_tokens,
        }
        try:
            params = inspect.signature(self.model.chat).parameters
        except (TypeError, ValueError):
            return kwargs
        if any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values()):
            return kwargs
        return {k: v for k, v in kwargs.items() if k in params}

    async def run(self, session_id: str, user_message: str, system_prompt: str = "", tools: list = None, persona: str = "default", confirm_callback=None, image_url: str = None, stop_event=None, agent_config: dict = None, persist_user: bool = True, client_message_id: str = None, generation_id: str = None) -> AsyncGenerator[dict, None]:
        cfg = agent_config or {}
        max_steps = cfg.get("max_steps", self.max_steps)
        temperature = cfg.get("temperature", 0.8)
        top_p = cfg.get("top_p", 0.9)
        max_tokens = cfg.get("max_tokens", 4096)
        max_history = cfg.get("max_history", 20)
        max_context = cfg.get("max_context", 4096)
        custom_instructions = cfg.get("custom_instructions", "")

        if custom_instructions and system_prompt:
            system_prompt += f"\n\n## 自定义指令\n{custom_instructions}"

        message_metadata = {"generation_id": generation_id} if generation_id else {}
        if persist_user:
            await self.memory.add_message(
                session_id,
                "user",
                user_message,
                persona=persona,
                metadata=message_metadata,
                client_message_id=client_message_id,
            )
        messages = await self.memory.get_context(session_id, system_prompt, max_history=max_history, max_context=max_context)

        # 如果有图片，将最后一条用户消息替换为视觉格式
        if image_url and messages:
            for i in range(len(messages) - 1, -1, -1):
                if messages[i].get("role") == "user":
                    messages[i]["content"] = [
                        {"type": "text", "text": user_message},
                        {"type": "image_url", "image_url": {"url": image_url}},
                    ]
                    break

        full_response = ""
        loops = 0
        tool_seq = 0  # 工具调用序号
        generation_stopped = False
        tool_context = self.tool_registry.create_context(session_id, stop_event=stop_event) if self.tool_registry else None

        try:
            while loops < max_steps:
                # 检查停止信号
                if stop_event and stop_event.is_set():
                    yield {"type": "segment", "segment": {"type": "text", "content": "\n\n[已停止]"}}
                    break

                # 消息数保护：防止工具调用无限堆积（MiMo 百万上下文，放宽限制）
                if len(messages) > 200:
                    yield {"type": "segment", "segment": {"type": "text", "content": "\n\n[对话过长，自动结束]"}}
                    break

                loops += 1
                chunk_content = ""
                tool_calls = []

                # LLM 调用（最多重试 3 次）
                llm_success = False
                last_error = None
                for attempt in range(3):
                    try:
                        chat_kwargs = self._chat_kwargs(tools, True, temperature, top_p, max_tokens)
                        model_stream = self.model.chat(messages, **chat_kwargs).__aiter__()
                        while True:
                            next_chunk = asyncio.create_task(anext(model_stream))
                            stop_wait = asyncio.create_task(stop_event.wait()) if stop_event else None
                            wait_for = {next_chunk, stop_wait} if stop_wait else {next_chunk}
                            completed, _ = await asyncio.wait(wait_for, return_when=asyncio.FIRST_COMPLETED)

                            if stop_wait and stop_wait in completed and stop_event.is_set():
                                next_chunk.cancel()
                                await asyncio.gather(next_chunk, return_exceptions=True)
                                close_stream = getattr(model_stream, "aclose", None)
                                if close_stream:
                                    await close_stream()
                                generation_stopped = True
                                break

                            if stop_wait:
                                stop_wait.cancel()
                                await asyncio.gather(stop_wait, return_exceptions=True)

                            try:
                                chunk = next_chunk.result()
                            except StopAsyncIteration:
                                break
                            if chunk.content:
                                chunk_content += chunk.content
                                yield {"type": "segment", "segment": {"type": "text", "content": chunk.content}}
                            if chunk.tool_calls:
                                tool_calls.extend(chunk.tool_calls)

                        if generation_stopped:
                            yield {"type": "segment", "segment": {"type": "text", "content": "\n\n[已停止]"}}
                        llm_success = True
                        break
                    except Exception as e:
                        last_error = e
                        if attempt < 2:
                            wait = 2 ** attempt  # 1s, 2s
                            yield {"type": "segment", "segment": {"type": "text", "content": f"\n[重试中 {attempt+1}/3，等待 {wait}s...]"}}
                            await asyncio.sleep(wait)

                if not llm_success:
                    yield {"type": "segment", "segment": {"type": "text", "content": f"\n[连接失败，已重试3次: {last_error}]"}}
                    break

                full_response += chunk_content

                if generation_stopped:
                    break

                if not tool_calls:
                    break

                # 验证 tool_calls 的 arguments 是有效 JSON
                valid_tool_calls = []
                for tc in tool_calls:
                    func = tc.get("function", {})
                    args_str = func.get("arguments", "")
                    try:
                        json.loads(args_str) if args_str else {}
                        valid_tool_calls.append(tc)
                    except json.JSONDecodeError:
                        # arguments 不完整，跳过这个 tool call
                        yield {"type": "segment", "segment": {"type": "text", "content": f"\n[工具调用参数不完整，已跳过]"}}
                        continue

                if not valid_tool_calls:
                    break

                messages.append({"role": "assistant", "content": chunk_content, "tool_calls": valid_tool_calls})

                if not self.tool_registry:
                    yield {"type": "segment", "segment": {"type": "text", "content": "工具系统未配置"}}
                    break

                for tc in valid_tool_calls:
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

                    result = await self.tool_registry.execute(
                        tool_name,
                        tool_args,
                        context=tool_context,
                    )

                    # 检查是否为 confirm
                    try:
                        result_data = json.loads(result)
                        if result_data.get("type") == "confirm" and confirm_callback:
                            yield {"type": "confirm", "data": result_data}
                            confirmed = await confirm_callback(result_data)
                            if confirmed:
                                result = await self.tool_registry.execute(
                                    tool_name,
                                    tool_args,
                                    context=tool_context,
                                    confirmed=True,
                                )
                                result_data = json.loads(result)
                            else:
                                result_data = {"success": False, "error": "USER_DENIED", "message": "用户取消了操作"}
                                result = json.dumps(result_data, ensure_ascii=False)
                    except (json.JSONDecodeError, TypeError):
                        result_data = {}

                    # 生成结果摘要
                    result_summary = self._make_summary(tool_name, result_data, result)
                    result_detail = self._result_detail(result_data, result)

                    # 发送工具调用完成
                    yield {"type": "segment", "segment": {
                        "type": "tool",
                        "tool_call_id": tool_call_id,
                        "tool_name": tool_name,
                        "status": "done",
                        "result_summary": result_summary,
                        "result_detail": result_detail
                    }}

                    # MiMo 百万上下文，不截断 tool result
                    result_for_msg = result if isinstance(result, str) else str(result)
                    messages.append({"role": "tool", "tool_call_id": tc.get("id", ""), "content": result_for_msg})

        except Exception as e:
            yield {"type": "error", "message": str(e)}

        # done 事件
        await self.memory.add_message(
            session_id,
            "assistant",
            full_response,
            persona=persona,
            metadata=message_metadata,
        )
        await self.memory.post_conversation(session_id, user_message, full_response)

        emotion = persona_manager.get_emotion_engine(persona) if hasattr(self, '_persona_manager') else None
        emoji = ""
        yield {"type": "done", "emoji": emoji}

    def _make_summary(self, tool_name, result_data, result):
        """生成工具结果摘要"""
        if not result_data:
            return str(result)[:100] if result else ""

        if result_data.get("type") == "confirm":
            return "等待确认"
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

    @staticmethod
    def _result_detail(result_data, result):
        if not result_data:
            return (result if isinstance(result, str) else str(result))[:3000]
        data = result_data.get("data") or {}
        for key in ("output", "content", "display"):
            if key in data:
                return str(data[key])[:3000]
        if "results" in data:
            lines = []
            for item in data["results"]:
                lines.append(f"{item.get('title', '')}\n{item.get('snippet', '')}\n{item.get('url', '')}".strip())
            return "\n\n".join(lines)[:3000]
        if data:
            return json.dumps(data, ensure_ascii=False, indent=2)[:3000]
        return str(result_data.get("message") or result)[:3000]
