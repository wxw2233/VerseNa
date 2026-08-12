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

    def _chat_kwargs(
        self,
        tools,
        stream,
        temperature,
        top_p,
        max_tokens,
        reasoning_enabled=False,
        reasoning_effort="medium",
    ):
        """Only pass optional generation args supported by the adapter."""
        kwargs = {
            "tools": tools,
            "stream": stream,
            "temperature": temperature,
            "top_p": top_p,
            "max_tokens": max_tokens,
            "reasoning_enabled": reasoning_enabled,
            "reasoning_effort": reasoning_effort,
        }
        try:
            params = inspect.signature(self.model.chat).parameters
        except (TypeError, ValueError):
            return kwargs
        if any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values()):
            return kwargs
        return {k: v for k, v in kwargs.items() if k in params}

    async def run(self, session_id: str, user_message: str, system_prompt: str = "", tools: list = None, persona: str = "default", confirm_callback=None, image_url: str = None, stop_event=None, agent_config: dict = None, persist_user: bool = True, client_message_id: str = None, generation_id: str = None, progress_callback=None) -> AsyncGenerator[dict, None]:
        cfg = agent_config or {}
        max_steps = cfg.get("max_steps", self.max_steps)
        temperature = cfg.get("temperature", 0.8)
        top_p = cfg.get("top_p", 0.9)
        max_tokens = cfg.get("max_tokens", 4096)
        max_context = cfg.get("max_context", 4096)
        custom_instructions = cfg.get("custom_instructions", "")
        reasoning_requested = bool(cfg.get("reasoning_enabled", False))
        reasoning_effort = cfg.get("reasoning_effort", "medium")
        if reasoning_effort not in {"low", "medium", "high"}:
            reasoning_effort = "medium"
        reasoning_known_available = bool(getattr(self.model, "reasoning_available", False))
        reasoning_enabled = reasoning_requested

        async def notify_compaction(event):
            if not progress_callback:
                return
            try:
                payload = {
                    "type": "context_compaction",
                    "mode": "automatic",
                    **event,
                }
                result = progress_callback(payload)
                if inspect.isawaitable(result):
                    await result
            except Exception:
                # 状态提示不能影响 Agent 主流程。
                pass

        if custom_instructions and system_prompt:
            system_prompt += f"\n\n## 自定义指令\n{custom_instructions}"

        message_metadata = {"generation_id": generation_id} if generation_id else {}
        if reasoning_requested:
            message_metadata.update({
                "reasoning_enabled": True,
                "reasoning_effort": reasoning_effort,
                "reasoning_model": getattr(self.model, "model_name", ""),
                "reasoning_available": reasoning_known_available,
            })
        if persist_user:
            await self.memory.add_message(
                session_id,
                "user",
                user_message,
                persona=persona,
                metadata=message_metadata,
                client_message_id=client_message_id,
            )
        messages = await self.memory.get_context(
            session_id,
            system_prompt,
            max_context=max_context,
            max_output_tokens=max_tokens,
            compaction_callback=notify_compaction,
        )

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
        final_response = ""
        loops = 0
        tool_seq = 0  # 工具调用序号
        generation_stopped = False
        reasoning_duration_ms = 0
        reasoning_observed = False
        first_reasoning_id = None
        tool_result_cache = {}
        read_progress = {}
        waiting_for_user = False

        def cacheable_tool(tool_name: str) -> bool:
            # 代码执行和文件操作可能改变外部状态，不能复用旧结果，尤其是“写入后重新读取”。
            return tool_name not in {"code_exec", "file_manager"}
        tool_context = self.tool_registry.create_context(
            session_id,
            workspace=cfg.get("tool_workspace"),
            approval_mode=cfg.get("approval_mode", "ask"),
            stop_event=stop_event,
        ) if self.tool_registry else None

        async def execute_tool(tool_name, tool_args, confirmed=False):
            if stop_event and stop_event.is_set():
                return json.dumps({
                    "success": False,
                    "error": "CANCELLED",
                    "message": "操作已停止",
                }, ensure_ascii=False)

            execute_task = asyncio.create_task(self.tool_registry.execute(
                tool_name,
                tool_args,
                context=tool_context,
                confirmed=confirmed,
            ))
            if not stop_event:
                return await execute_task

            stop_wait = asyncio.create_task(stop_event.wait())
            try:
                completed, _ = await asyncio.wait(
                    {execute_task, stop_wait},
                    return_when=asyncio.FIRST_COMPLETED,
                )
                if execute_task in completed:
                    return execute_task.result()
                execute_task.cancel()
                await asyncio.gather(execute_task, return_exceptions=True)
                return json.dumps({
                    "success": False,
                    "error": "CANCELLED",
                    "message": "操作已停止",
                }, ensure_ascii=False)
            finally:
                stop_wait.cancel()
                await asyncio.gather(stop_wait, return_exceptions=True)

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
                reasoning_id = f"reasoning_{loops}"
                if first_reasoning_id is None:
                    first_reasoning_id = reasoning_id
                reasoning_open = False
                reasoning_started_at = None

                if reasoning_enabled:
                    reasoning_open = True
                    reasoning_started_at = time.monotonic()
                    yield {"type": "segment", "segment": {
                        "type": "reasoning",
                        "reasoning_id": reasoning_id,
                        "content": "",
                        "status": "running",
                        "model": getattr(self.model, "model_name", ""),
                    }}

                async def close_reasoning(status="done"):
                    nonlocal reasoning_open, reasoning_duration_ms
                    if not reasoning_open:
                        return None
                    reasoning_open = False
                    elapsed = int((time.monotonic() - reasoning_started_at) * 1000)
                    reasoning_duration_ms += elapsed
                    return {"type": "segment", "segment": {
                        "type": "reasoning",
                        "reasoning_id": reasoning_id,
                        "content": "",
                        "status": status,
                        "duration_ms": elapsed,
                        "model": getattr(self.model, "model_name", ""),
                    }}

                # LLM 调用（最多重试 3 次）
                llm_success = False
                last_error = None
                for attempt in range(3):
                    try:
                        chat_kwargs = self._chat_kwargs(
                            tools,
                            True,
                            temperature,
                            top_p,
                            max_tokens,
                            reasoning_enabled,
                            reasoning_effort,
                        )
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
                                reasoning_event = await close_reasoning("stopped")
                                if reasoning_event:
                                    yield reasoning_event
                                break

                            if stop_wait:
                                stop_wait.cancel()
                                await asyncio.gather(stop_wait, return_exceptions=True)

                            try:
                                chunk = next_chunk.result()
                            except StopAsyncIteration:
                                break
                            if chunk.reasoning_content and reasoning_enabled:
                                reasoning_observed = True
                                yield {"type": "segment", "segment": {
                                    "type": "reasoning",
                                    "reasoning_id": reasoning_id,
                                    "content": chunk.reasoning_content,
                                    "status": "running",
                                    "model": getattr(self.model, "model_name", ""),
                                }}
                            if chunk.content:
                                reasoning_event = await close_reasoning()
                                if reasoning_event:
                                    yield reasoning_event
                                chunk_content += chunk.content
                                yield {"type": "segment", "segment": {"type": "text", "content": chunk.content}}
                            if chunk.tool_calls:
                                reasoning_event = await close_reasoning()
                                if reasoning_event:
                                    yield reasoning_event
                                tool_calls.extend(chunk.tool_calls)

                        reasoning_event = await close_reasoning("stopped" if generation_stopped else "done")
                        if reasoning_event:
                            yield reasoning_event

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
                    final_response = chunk_content
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
                    if stop_event and stop_event.is_set():
                        generation_stopped = True
                        break
                    func = tc.get("function", {})
                    tool_name = func.get("name", "")
                    try:
                        tool_args = json.loads(func.get("arguments") or "{}")
                    except json.JSONDecodeError:
                        tool_args = {}

                    tool_seq += 1
                    tool_call_id = f"tc_{int(time.time() * 1000):013d}_{tool_seq:03d}"
                    tool_signature = json.dumps(
                        [tool_name, tool_args],
                        ensure_ascii=False,
                        sort_keys=True,
                        default=str,
                    )

                    is_choice_tool = tool_name == "ask_user_choice"
                    if not is_choice_tool:
                        yield {"type": "segment", "segment": {
                            "type": "tool",
                            "tool_call_id": tool_call_id,
                            "tool_name": tool_name,
                            "tool_args": tool_args,
                            "status": "running"
                        }}

                    read_error = self._validate_read_continuation(
                        tool_name,
                        tool_args,
                        read_progress,
                    )
                    if read_error:
                        result = read_error
                    else:
                        result = tool_result_cache.get(tool_signature) if cacheable_tool(tool_name) else None
                        if result is not None:
                            result = self._mark_result_reused(result)
                        else:
                            result = await execute_tool(tool_name, tool_args)

                    # 检查是否为 confirm
                    try:
                        result_data = json.loads(result)
                        if result_data.get("type") == "confirm" and confirm_callback:
                            yield {"type": "confirm", "data": result_data}
                            confirmed = await confirm_callback(result_data)
                            if confirmed:
                                result = await execute_tool(
                                    tool_name,
                                    tool_args,
                                    confirmed=True,
                                )
                                result_data = json.loads(result)
                            else:
                                result_data = {"success": False, "error": "USER_DENIED", "message": "用户取消了操作"}
                                result = json.dumps(result_data, ensure_ascii=False)
                    except (json.JSONDecodeError, TypeError):
                        result_data = {}

                    if (
                        is_choice_tool
                        and result_data.get("type") == "user_choice"
                        and result_data.get("success") is True
                    ):
                        choice = result_data.get("data") or {}
                        question = str(choice.get("question") or "").strip()
                        options = choice.get("options") or []
                        yield {"type": "segment", "segment": {
                            "type": "choice",
                            "choice_id": choice.get("choice_id") or tool_call_id,
                            "question": question,
                            "options": options,
                        }}
                        choice_lines = [chunk_content.strip(), question]
                        choice_lines.extend(
                            f"{option.get('id', '')}：{option.get('label', '')}"
                            for option in options
                        )
                        final_response = "\n".join(line for line in choice_lines if line)
                        waiting_for_user = True
                        break

                    if cacheable_tool(tool_name) and tool_signature not in tool_result_cache:
                        tool_result_cache[tool_signature] = result
                    self._update_read_progress(tool_name, tool_args, result_data, read_progress)

                    # 生成结果摘要
                    result_summary = self._make_summary(tool_name, result_data, result)
                    result_detail = self._result_detail(result_data, result)

                    if not is_choice_tool:
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
                    if self.memory.needs_runtime_compaction(
                        messages,
                        max_context=max_context,
                        max_output_tokens=max_tokens,
                    ):
                        before_tokens = self.memory._estimate_msgs_tokens(messages)
                        await notify_compaction({
                            "phase": "start",
                            "reason": "tool_loop",
                            "before_tokens": before_tokens,
                        })
                        messages = self.memory.compact_runtime_messages(
                            messages,
                            max_context=max_context,
                            max_output_tokens=max_tokens,
                        )
                        await notify_compaction({
                            "phase": "done",
                            "reason": "tool_loop",
                            "before_tokens": before_tokens,
                            "after_tokens": self.memory._estimate_msgs_tokens(messages),
                        })

                    if stop_event and stop_event.is_set():
                        generation_stopped = True
                        break

                if waiting_for_user:
                    break

                if generation_stopped:
                    yield {"type": "segment", "segment": {"type": "text", "content": "\n\n[已停止]"}}
                    break

        except Exception as e:
            yield {"type": "error", "message": str(e)}

        reasoning_available = reasoning_known_available or reasoning_observed
        if reasoning_requested and not reasoning_available and first_reasoning_id:
            yield {"type": "segment", "segment": {
                "type": "reasoning",
                "reasoning_id": first_reasoning_id,
                "content": "",
                "status": "unavailable",
                "model": getattr(self.model, "model_name", ""),
            }}
        if reasoning_requested:
            message_metadata["reasoning_available"] = reasoning_available

        # done 事件
        assistant_response = final_response or full_response
        await self.memory.add_message(
            session_id,
            "assistant",
            assistant_response,
            persona=persona,
            metadata=message_metadata,
        )
        await self.memory.post_conversation(
            session_id,
            user_message,
            assistant_response,
            max_context=max_context,
            max_output_tokens=max_tokens,
            compaction_callback=notify_compaction,
        )

        emotion = persona_manager.get_emotion_engine(persona) if hasattr(self, '_persona_manager') else None
        emoji = ""
        yield {
            "type": "done",
            "emoji": emoji,
            "reasoning_enabled": reasoning_requested,
            "reasoning_available": reasoning_available,
            "reasoning_effort": reasoning_effort if reasoning_requested else None,
            "reasoning_model": getattr(self.model, "model_name", "") if reasoning_requested else None,
            "reasoning_duration_ms": reasoning_duration_ms,
        }

    @staticmethod
    def _mark_result_reused(result):
        try:
            data = json.loads(result)
        except (json.JSONDecodeError, TypeError):
            return result
        data["reused"] = True
        data["message"] = "相同工具调用已执行过，已复用上次结果，请勿再次调用"
        return json.dumps(data, ensure_ascii=False)

    @staticmethod
    def _validate_read_continuation(tool_name, tool_args, read_progress):
        if tool_name != "file_manager" or tool_args.get("action") != "read":
            return None
        path = tool_args.get("path", "")
        state = read_progress.get(path)
        if not state:
            return None
        if state["eof"]:
            return json.dumps({
                "success": False,
                "error": "EOF_REACHED",
                "message": "此文件已读取完毕，请勿重复读取",
                "data": {"path": path, "eof": True, "next_offset": state["next_offset"]},
            }, ensure_ascii=False)
        try:
            requested_offset = int(tool_args.get("offset", 0) or 0)
        except (TypeError, ValueError):
            requested_offset = -1
        if requested_offset != state["next_offset"]:
            return json.dumps({
                "success": False,
                "error": "READ_CONTINUATION_REQUIRED",
                "message": f"续读 offset 必须等于上次返回的 next_offset={state['next_offset']}",
                "data": {
                    "path": path,
                    "expected_offset": state["next_offset"],
                    "received_offset": requested_offset,
                },
            }, ensure_ascii=False)
        return None

    @staticmethod
    def _update_read_progress(tool_name, tool_args, result_data, read_progress):
        if tool_name != "file_manager":
            return
        action = tool_args.get("action")
        path = tool_args.get("path", "")
        if action != "read":
            if action in {"write", "find_replace", "move", "delete"}:
                read_progress.pop(path, None)
            return
        data = result_data.get("data") or {}
        if result_data.get("success") and "next_offset" in data:
            read_progress[path] = {
                "next_offset": data["next_offset"],
                "eof": bool(data.get("eof", not data.get("truncated", False))),
            }

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
