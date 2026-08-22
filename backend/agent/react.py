import json
import time
import inspect
import asyncio
from pathlib import Path
from typing import AsyncGenerator
from agent.models.base import BaseModelAdapter
from agent.memory import MemoryManager
from persona.manager import persona_manager
from agent.diagnostics import runtime_diagnostics
from security_utils import redact_sensitive_text
from agent.context_protocol import (
    CORE_CONTEXT_RULES,
    format_user_request,
    format_untrusted_tool_output,
    normalize_tool_payload,
)
from agent.task_state import (
    compact_task_state,
    finalize_task_state,
    normalize_task_state,
    record_subagent_result,
    record_tool_result,
    build_acceptance_report,
    refresh_self_check,
)

DEFAULT_TOOL_RESULT_CONTEXT_CHARS = 100_000
MIN_TOOL_RESULT_CONTEXT_CHARS = 8_000
MAX_TOOL_RESULT_CONTEXT_CHARS = 500_000
MAX_DELEGATE_TIMEOUT_SECONDS = 900

class ReActAgent:
    def __init__(self, model: BaseModelAdapter, memory: MemoryManager, tool_registry=None, max_steps: int = None):
        self.model = model
        self.memory = memory
        self.tool_registry = tool_registry
        # Kept in the signature for compatibility with older callers. Runtime
        # progress is bounded by stop signals, tool timeouts, and compaction.
        self.max_steps = None

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
        work_started_at = time.monotonic()
        cfg = agent_config or {}
        temperature = cfg.get("temperature", 0.8)
        top_p = cfg.get("top_p", 0.9)
        max_tokens = cfg.get("max_tokens", 100_000)
        max_context = cfg.get("max_context", 1_000_000)
        tool_timeout = cfg.get("tool_timeout", 120)
        tool_result_max_chars = self._tool_result_context_limit(cfg)
        workspace_path = cfg.get("tool_workspace") or None
        task_state = cfg.get("task_state")
        if isinstance(task_state, dict):
            task_state = normalize_task_state(task_state, workspace_path)
            cfg["task_state"] = task_state
        custom_instructions = cfg.get("custom_instructions", "")
        reasoning_requested = bool(cfg.get("reasoning_enabled", False))
        reasoning_effort = cfg.get("reasoning_effort", "medium")
        if reasoning_effort not in {"low", "medium", "high"}:
            reasoning_effort = "medium"
        reasoning_known_available = bool(getattr(self.model, "reasoning_available", False))
        reasoning_enabled = reasoning_requested

        async def notify_compaction(event):
            if isinstance(task_state, dict):
                if event.get("phase") in {"start", "done", "error"}:
                    task_state["last_compaction"] = {
                        key: event.get(key)
                        for key in (
                            "phase", "reason", "message", "before_tokens", "after_tokens",
                            "before_messages", "after_messages",
                        )
                        if event.get(key) is not None
                    }
            runtime_diagnostics.record_compaction(session_id, event)
            if event.get("phase") == "done" and event.get("after_tokens") is not None:
                runtime_diagnostics.update_context(
                    session_id,
                    event.get("after_tokens"),
                    event.get("after_messages"),
                )
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
        runtime_diagnostics.start_generation(
            session_id,
            generation_id or "",
            workspace=workspace_path,
            max_context=max_context,
            max_steps=0,
            subagent_max_steps=cfg.get("subagent_max_steps", 0),
            subagent_max_tokens=cfg.get("subagent_max_tokens", 0),
            subagent_timeout=cfg.get("subagent_timeout", 0),
        )
        messages = await self.memory.get_context(
            session_id,
            system_prompt,
            max_context=max_context,
            max_output_tokens=max_tokens,
            compaction_callback=notify_compaction,
            workspace_path=workspace_path,
            task_state=task_state,
            current_user_message=user_message,
        )

        # Keep the persisted conversation format stable, but mark the active
        # turn explicitly so a compacted historical message cannot masquerade
        # as the current instruction.
        for index in range(len(messages) - 1, -1, -1):
            if messages[index].get("role") == "user":
                if image_url:
                    messages[index]["content"] = [
                        {"type": "text", "text": format_user_request(user_message)},
                        {"type": "image_url", "image_url": {"url": image_url}},
                    ]
                else:
                    messages[index]["content"] = format_user_request(user_message)
                break

        # 如果有图片，将最后一条用户消息替换为视觉格式
        if image_url and messages:
            for i in range(len(messages) - 1, -1, -1):
                if messages[i].get("role") == "user":
                    messages[i]["content"] = [
                        {"type": "text", "text": format_user_request(user_message)},
                        {"type": "image_url", "image_url": {"url": image_url}},
                    ]
                    break

        full_response = ""
        final_response = ""
        loops = 0
        tool_seq = 0  # 工具调用序号
        generation_stopped = False
        finish_reason = "completed"
        reasoning_duration_ms = 0
        reasoning_observed = False
        first_reasoning_id = None
        tool_result_cache = {}
        read_progress = {}
        waiting_for_user = False
        executor_verification_required = False
        executor_verification_prompts = 0
        executor_modified_files = set()
        plan_repair_attempts = 0
        plan_repair_pending = False
        tool_attempts = {}
        tool_failures = {}

        def cacheable_tool(tool_name: str) -> bool:
            # 代码执行和文件操作可能改变外部状态，不能复用旧结果，尤其是“写入后重新读取”。
            return tool_name not in {"code_exec", "file_manager", "delegate_task", "delegate_tasks", "delegate_plan"}
        tool_context = self.tool_registry.create_context(
            session_id,
            workspace=cfg.get("tool_workspace"),
            approval_mode=cfg.get("approval_mode", "ask"),
            stop_event=stop_event,
            model=self.model,
            progress_callback=progress_callback,
            agent_config=cfg,
            confirm_callback=confirm_callback,
            memory_manager=self.memory,
        ) if self.tool_registry else None

        async def execute_tool(tool_name, tool_args, confirmed=False):
            if stop_event and stop_event.is_set():
                return json.dumps({
                    "success": False,
                    "error": "CANCELLED",
                    "message": "操作已停止",
                }, ensure_ascii=False)

            timeout_seconds = self._tool_timeout_seconds(tool_name, tool_args, cfg, tool_timeout)
            execute_task = asyncio.create_task(self.tool_registry.execute(
                tool_name,
                tool_args,
                context=tool_context,
                confirmed=confirmed,
            ))
            timeout_task = asyncio.create_task(asyncio.sleep(timeout_seconds))
            stop_wait = asyncio.create_task(stop_event.wait()) if stop_event else None
            try:
                pending = {execute_task, timeout_task}
                if stop_wait:
                    pending.add(stop_wait)
                completed, _ = await asyncio.wait(
                    pending,
                    return_when=asyncio.FIRST_COMPLETED,
                )
                if execute_task in completed:
                    return execute_task.result()
                execute_task.cancel()
                await asyncio.gather(execute_task, return_exceptions=True)
                if timeout_task in completed:
                    return json.dumps({
                        "success": False,
                        "error": "TOOL_TIMEOUT",
                        "message": f"工具执行超过 {timeout_seconds} 秒，已自动终止。",
                    }, ensure_ascii=False)
                return json.dumps({
                    "success": False,
                    "error": "CANCELLED",
                    "message": "操作已停止",
                }, ensure_ascii=False)
            finally:
                if stop_wait:
                    stop_wait.cancel()
                timeout_task.cancel()
                await asyncio.gather(
                    *(task for task in (stop_wait, timeout_task) if task is not None),
                    return_exceptions=True,
                )

        runtime_diagnostics.update_context(
            session_id,
            self.memory._estimate_msgs_tokens(messages),
            len(messages),
        )

        try:
            while True:
                # 检查停止信号
                if stop_event and stop_event.is_set():
                    finish_reason = "stopped"
                    yield {"type": "segment", "segment": {"type": "text", "content": "\n\n[已停止]"}}
                    break

                compaction_reason = self.memory.runtime_compaction_reason(
                    messages,
                    max_context=max_context,
                    max_output_tokens=max_tokens,
                )
                if compaction_reason:
                    before_tokens = self.memory._estimate_msgs_tokens(messages)
                    await notify_compaction({
                        "phase": "start",
                        "reason": f"tool_loop_{compaction_reason}",
                        "before_tokens": before_tokens,
                        "before_messages": len(messages),
                    })
                    messages = self.memory.compact_runtime_messages(
                        messages,
                        max_context=max_context,
                        max_output_tokens=max_tokens,
                        task_state=task_state,
                    )
                    await notify_compaction({
                        "phase": "done",
                        "reason": f"tool_loop_{compaction_reason}",
                        "before_tokens": before_tokens,
                        "after_tokens": self.memory._estimate_msgs_tokens(messages),
                        "after_messages": len(messages),
                    })

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
                            finish_reason = "stopped"
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
                    finish_reason = "model_connection_failed"
                    yield {"type": "segment", "segment": {"type": "text", "content": f"\n[连接失败，已重试3次: {last_error}]"}}
                    break

                full_response += chunk_content

                if generation_stopped:
                    finish_reason = "stopped"
                    break

                if not tool_calls and executor_verification_required:
                    if executor_verification_prompts >= 2:
                        final_response = (
                            chunk_content.rstrip()
                            + "\n\n[执行子代理的修改尚未由主代理独立验收，本轮不能确认任务已完成。]"
                        )
                        break
                    executor_verification_prompts += 1
                    messages.append({"role": "assistant", "content": chunk_content})
                    messages.append({
                        "role": "user",
                        "content": (
                            "系统验收门：executor 已返回修改结果，但你尚未独立核对。"
                            "请立即使用 file_manager 读取关键改动、运行 code_exec/runtime_smoke 验证，"
                            "或委派 reviewer 静态审查、verifier 动态验收；完成验收后再给最终结论。"
                        ),
                    })
                    continue

                if not tool_calls and plan_repair_pending:
                    final_response = (
                        chunk_content.rstrip()
                        + "\n\n[任务计划校验失败，自动修正计划未完成。]"
                    )
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
                    finish_reason = "invalid_tool_call"
                    yield {"type": "segment", "segment": {"type": "text", "content": "\n[工具调用参数无效，本轮已停止]"}}
                    break

                messages.append({"role": "assistant", "content": chunk_content, "tool_calls": valid_tool_calls})

                if not self.tool_registry:
                    finish_reason = "tool_registry_unavailable"
                    yield {"type": "segment", "segment": {"type": "text", "content": "工具系统未配置"}}
                    break

                pending_plan_repair_prompt = ""
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

                    if pending_plan_repair_prompt:
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc.get("id", ""),
                            "content": json.dumps({
                                "success": False,
                                "error": "SKIPPED_DUE_TO_PLAN_REPAIR",
                                "message": "同批次前序 delegate_plan 校验失败，本工具未执行；请先重新提交完整计划",
                            }, ensure_ascii=False),
                        })
                        continue

                    tool_seq += 1
                    tool_call_id = f"tc_{int(time.time() * 1000):013d}_{tool_seq:03d}"
                    tool_signature = json.dumps(
                        [tool_name, tool_args],
                        ensure_ascii=False,
                        sort_keys=True,
                        default=str,
                    )

                    is_choice_tool = tool_name == "ask_user_choice"
                    is_delegate_tool = tool_name in {"delegate_task", "delegate_tasks", "delegate_plan"}
                    tool_attempts[tool_signature] = tool_attempts.get(tool_signature, 0) + 1
                    operation_id = f"op_{generation_id or session_id}_{tool_seq}"
                    if tool_context is not None:
                        try:
                            tool_context.operation_id = operation_id
                            tool_context.operation_attempt = tool_attempts[tool_signature]
                        except (AttributeError, TypeError):
                            # Test/plugin registries may return an opaque
                            # context object.  Operation metadata is an audit
                            # enhancement and must not break those adapters.
                            pass
                    repeated_blocked = (
                        tool_attempts[tool_signature] >= 3
                        and not is_choice_tool
                        and not is_delegate_tool
                    )
                    if not is_choice_tool and not is_delegate_tool:
                        yield {"type": "segment", "segment": {
                            "type": "tool",
                            "tool_call_id": tool_call_id,
                            "tool_name": tool_name,
                            "tool_args": tool_args,
                            "status": "running"
                        }}

                    read_error = self._validate_read_continuation(
                        tool_name, tool_args, read_progress,
                    )
                    tool_started = time.monotonic()
                    if repeated_blocked:
                        result = json.dumps({
                            "success": False,
                            "error": "REPEATED_TOOL_CALL",
                            "message": "检测到相同工具和参数已连续调用多次，已阻止重复执行。请使用已有结果或调整方案。",
                        }, ensure_ascii=False)
                    elif read_error:
                        result = read_error
                    else:
                        result = tool_result_cache.get(tool_signature) if cacheable_tool(tool_name) else None
                        if result is not None:
                            result = self._mark_result_reused(result)
                        else:
                            result = await execute_tool(tool_name, tool_args)

                    # 检查是否为 confirm
                    try:
                        result_data = normalize_tool_payload(
                            result,
                            source=tool_name,
                            target=json.dumps(tool_args, ensure_ascii=False, default=str)[:1000],
                            operation_id=operation_id,
                        )
                        result = json.dumps(result_data, ensure_ascii=False)
                        if result_data.get("type") == "confirm" and confirm_callback:
                            yield {"type": "confirm", "data": result_data}
                            confirmed = await confirm_callback(result_data)
                            if confirmed:
                                result = await execute_tool(
                                    tool_name,
                                    tool_args,
                                    confirmed=True,
                                )
                                result_data = normalize_tool_payload(
                                    result,
                                    source=tool_name,
                                    target=json.dumps(tool_args, ensure_ascii=False, default=str)[:1000],
                                    operation_id=operation_id,
                                )
                                result = json.dumps(result_data, ensure_ascii=False)
                            else:
                                result_data = normalize_tool_payload(
                                    {"success": False, "error": "USER_DENIED", "message": "用户取消了操作"},
                                    source=tool_name,
                                    operation_id=operation_id,
                                )
                                result = json.dumps(result_data, ensure_ascii=False)
                    except (TypeError, ValueError):
                        result_data = normalize_tool_payload(
                            result,
                            source=tool_name,
                            operation_id=operation_id,
                        )
                        result = json.dumps(result_data, ensure_ascii=False)

                    tool_duration_ms = int((time.monotonic() - tool_started) * 1000)
                    runtime_diagnostics.record_tool(
                        session_id,
                        tool_name,
                        tool_duration_ms,
                        result_data.get("success") is True,
                        result_data.get("error", ""),
                        blocked=repeated_blocked,
                    )
                    if result_data.get("success") is not True and not repeated_blocked:
                        tool_failures[tool_signature] = tool_failures.get(tool_signature, 0) + 1
                    if tool_failures.get(tool_signature, 0) >= 3:
                        result_data = {
                            **result_data,
                            "error": result_data.get("error") or "TOOL_FAILURE_LOOP",
                            "message": "同一工具调用已连续失败多次，请停止重复尝试并重新评估方案。",
                        }
                        result = json.dumps(result_data, ensure_ascii=False)

                    if isinstance(task_state, dict):
                        if tool_name in {"delegate_task", "delegate_tasks", "delegate_plan"}:
                            record_subagent_result(task_state, result_data)
                        record_tool_result(
                            task_state,
                            tool_name,
                            tool_args,
                            result_data,
                            duration_ms=tool_duration_ms,
                        )

                    if tool_name == "delegate_plan":
                        repair = (result_data.get("data") or {}).get("repair") or {}
                        if result_data.get("success") is True:
                            plan_repair_pending = False
                            plan_repair_attempts = 0
                        elif repair.get("retryable") is True:
                            if plan_repair_attempts < int(repair.get("max_retries") or 1):
                                plan_repair_attempts += 1
                                plan_repair_pending = True
                                requirements = repair.get("requirements") or []
                                pending_plan_repair_prompt = (
                                    "系统计划修正门：delegate_plan 校验失败。"
                                    f"错误代码：{repair.get('failed_error') or result_data.get('error') or 'UNKNOWN'}。"
                                    "请根据工具返回的 repair 数据重新构建并立即提交完整计划。"
                                    "这是本次计划唯一一次自动修正机会；不要解释错误，不要继续执行其他工具。"
                                )
                                if requirements:
                                    pending_plan_repair_prompt += "\n修正要求：\n" + "\n".join(
                                        f"- {item}" for item in requirements
                                    )
                            else:
                                plan_repair_pending = False

                    if (
                        tool_name == "delegate_task"
                        and (result_data.get("data") or {}).get("role") == "executor"
                    ):
                        evidence = (result_data.get("data") or {}).get("evidence") or {}
                        executor_modified_files = {
                            str(Path(path).resolve())
                            for path in evidence.get("modified_files") or []
                            if path
                        }
                        if executor_modified_files:
                            executor_verification_required = True
                            executor_verification_prompts = 0
                    elif tool_name == "delegate_plan":
                        plan_evidence = (result_data.get("data") or {}).get("evidence") or {}
                        executor_modified_files = {
                            str(Path(path).resolve())
                            for path in plan_evidence.get("modified_files") or []
                            if path
                        }
                        if executor_modified_files:
                            executor_verification_required = True
                            executor_verification_prompts = 0
                    elif executor_verification_required and result_data.get("success") is True:
                        is_file_check = False
                        if tool_name == "file_manager" and tool_args.get("action") in {"read", "info"}:
                            check_path = Path(tool_args.get("path") or "")
                            if not check_path.is_absolute() and tool_context:
                                check_path = tool_context.workspace / check_path
                            is_file_check = str(check_path.resolve()) in executor_modified_files
                        is_runtime_check = tool_name in {"code_exec", "runtime_smoke"}
                        is_review = (
                            tool_name == "delegate_task"
                            and tool_args.get("role") in {"reviewer", "verifier"}
                        )
                        if is_file_check or is_runtime_check or is_review:
                            executor_verification_required = False

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

                    if not is_choice_tool and not is_delegate_tool:
                        yield {"type": "segment", "segment": {
                            "type": "tool",
                            "tool_call_id": tool_call_id,
                            "tool_name": tool_name,
                            "status": "done",
                            "result_summary": result_summary,
                            "result_detail": result_detail,
                            "duration_ms": tool_duration_ms,
                        }}

                    result_for_msg = format_untrusted_tool_output(
                        result,
                        source=tool_name,
                        target=json.dumps(tool_args, ensure_ascii=False, default=str)[:1000],
                        operation_id=operation_id,
                        max_chars=tool_result_max_chars,
                    )
                    messages.append({"role": "tool", "tool_call_id": tc.get("id", ""), "content": result_for_msg})
                    compaction_reason = self.memory.runtime_compaction_reason(
                        messages,
                        max_context=max_context,
                        max_output_tokens=max_tokens,
                    )
                    if compaction_reason:
                        before_tokens = self.memory._estimate_msgs_tokens(messages)
                        await notify_compaction({
                            "phase": "start",
                            "reason": f"tool_loop_{compaction_reason}",
                            "before_tokens": before_tokens,
                            "before_messages": len(messages),
                        })
                        messages = self.memory.compact_runtime_messages(
                            messages,
                            max_context=max_context,
                            max_output_tokens=max_tokens,
                            task_state=task_state,
                        )
                        await notify_compaction({
                            "phase": "done",
                            "reason": f"tool_loop_{compaction_reason}",
                            "before_tokens": before_tokens,
                            "after_tokens": self.memory._estimate_msgs_tokens(messages),
                            "after_messages": len(messages),
                        })

                    if stop_event and stop_event.is_set():
                        generation_stopped = True
                        break

                if pending_plan_repair_prompt and not generation_stopped and not waiting_for_user:
                    messages.append({
                        "role": "user",
                        "content": pending_plan_repair_prompt,
                    })

                if waiting_for_user:
                    break

                if generation_stopped:
                    finish_reason = "stopped"
                    yield {"type": "segment", "segment": {"type": "text", "content": "\n\n[已停止]"}}
                    break

        except Exception as e:
            finish_reason = "error"
            yield {"type": "error", "message": redact_sensitive_text(e)}

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
        if isinstance(task_state, dict):
            try:
                task_state = refresh_self_check(task_state, workspace_path)
            except Exception:
                pass
            task_state = finalize_task_state(task_state, finish_reason)
            cfg["task_state"] = task_state
        assistant_response = redact_sensitive_text(final_response or full_response)
        user_message = redact_sensitive_text(user_message)
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
            workspace_path=workspace_path,
            task_state=task_state,
        )
        runtime_diagnostics.finish_generation(session_id)

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
            "work_duration_ms": max(0, int((time.monotonic() - work_started_at) * 1000)),
            "finish_reason": finish_reason,
            "task_state_snapshot": compact_task_state(task_state) if isinstance(task_state, dict) else None,
            "task_state": {
                "task_id": task_state.get("task_id"),
                "phase": task_state.get("phase"),
                "pending_count": len(task_state.get("pending") or []),
                "verified_count": len(task_state.get("verified") or []),
                "unverified_count": len(task_state.get("unverified") or []),
            } if isinstance(task_state, dict) else None,
            "acceptance_report": build_acceptance_report(task_state) if isinstance(task_state, dict) else None,
        }

    @staticmethod
    def _tool_timeout_seconds(tool_name, tool_args, cfg, default_timeout):
        """Delegated work has its own budget and must not inherit a short tool timeout."""
        try:
            timeout = int(default_timeout or 120)
        except (TypeError, ValueError):
            timeout = 120
        timeout = max(10, min(timeout, 300))
        if tool_name not in {"delegate_task", "delegate_tasks", "delegate_plan"}:
            return timeout

        requested = [cfg.get("subagent_timeout", 300)]
        if isinstance(tool_args, dict):
            requested.append(tool_args.get("timeout", 0))
            for node in tool_args.get("nodes", []) if isinstance(tool_args.get("nodes"), list) else []:
                if isinstance(node, dict):
                    requested.append(node.get("timeout", 0))
            for task in tool_args.get("tasks", []) if isinstance(tool_args.get("tasks"), list) else []:
                if isinstance(task, dict):
                    requested.append(task.get("timeout", 0))
        for value in requested:
            try:
                timeout = max(timeout, int(value or 0))
            except (TypeError, ValueError):
                continue
        return max(10, min(timeout, MAX_DELEGATE_TIMEOUT_SECONDS))

    @staticmethod
    def _tool_result_context_limit(cfg):
        try:
            value = int((cfg or {}).get("tool_result_max_chars", DEFAULT_TOOL_RESULT_CONTEXT_CHARS))
        except (TypeError, ValueError):
            value = DEFAULT_TOOL_RESULT_CONTEXT_CHARS
        return max(MIN_TOOL_RESULT_CONTEXT_CHARS, min(value, MAX_TOOL_RESULT_CONTEXT_CHARS))

    @staticmethod
    def _tool_result_for_context(result, max_chars=MIN_TOOL_RESULT_CONTEXT_CHARS):
        """Keep tool evidence useful without letting one result consume a whole turn."""
        content = result if isinstance(result, str) else str(result)
        try:
            limit = int(max_chars)
        except (TypeError, ValueError):
            limit = DEFAULT_TOOL_RESULT_CONTEXT_CHARS
        limit = max(MIN_TOOL_RESULT_CONTEXT_CHARS, min(limit, MAX_TOOL_RESULT_CONTEXT_CHARS))
        if len(content) <= limit:
            return content
        head = int(limit * 0.75)
        tail = limit - head
        omitted = len(content) - head - tail
        return (
            content[:head]
            + f"\n\n[tool result truncated for context: {omitted} characters omitted]\n\n"
            + content[-tail:]
        )

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
