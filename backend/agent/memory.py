from db.database import db
from config import settings
from datetime import datetime, timedelta
import json
import inspect
from pathlib import Path

MEMORY_KEYWORDS = ['记住', '我喜欢', '我不喜欢', '以后', '总是', '不要', '偏好', '习惯']
CONTEXT_TRIGGER_RATIO = 0.82
RECENT_CONTEXT_MESSAGES = 20
RUNTIME_CONTEXT_MESSAGES = 14
MAX_FALLBACK_SUMMARY_CHARS = 5000


class MemoryManager:
    def __init__(self, max_tokens=None, model=None):
        self.max_tokens = max_tokens or settings.MAX_CONTEXT_TOKENS
        self.model = model  # LLM adapter，用于摘要和记忆提取

    @staticmethod
    def _normalize_workspace(workspace_path):
        if not workspace_path:
            return None
        try:
            return str(Path(workspace_path).expanduser().resolve())
        except (OSError, TypeError, ValueError):
            value = str(workspace_path).strip()
            return value or None

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """估算 token 数：中文约 1.5 token/字，英文约 0.25 token/word"""
        if not text:
            return 0
        if isinstance(text, list):
            return MemoryManager._estimate_msgs_tokens(text)
        cn_chars = sum(1 for ch in text if '一' <= ch <= '鿿' or '　' <= ch <= '〿')
        other = len(text) - cn_chars
        return int(cn_chars * 1.5 + other * 0.25)

    @staticmethod
    def _estimate_msgs_tokens(messages: list) -> int:
        total = 0
        for msg in messages:
            content = msg.get('content', '')
            if isinstance(content, str):
                total += MemoryManager._estimate_tokens(content)
            # tool_calls 等结构也占 token
            if msg.get('tool_calls'):
                import json
                total += MemoryManager._estimate_tokens(json.dumps(msg['tool_calls']))
        return total + len(messages) * 4  # 每条消息有固定开销

    async def get_context(
        self,
        session_id,
        system_prompt='',
        max_history=None,
        max_context=None,
        max_output_tokens=None,
        compaction_callback=None,
        workspace_path=None,
    ):
        """按 token 预算构建上下文，max_history 仅作为兼容性的安全上限。"""
        max_ctx = max_context or self.max_tokens
        trigger_budget, hard_budget = self._context_budgets(max_ctx, max_output_tokens)
        messages = []

        # 1. system_prompt
        if system_prompt:
            messages.append({'role': 'system', 'content': system_prompt})

        # 2. 长期记忆先全部候选，最终由统一预算裁剪，避免固定条数直接挤占上下文。
        workspace_path = self._normalize_workspace(workspace_path)
        memories = await db.get_memories(limit=50, workspace_path=workspace_path)
        if memories:
            await db.mark_memories_used([memory.get("id") for memory in memories])
            def format_memory(memory):
                scope = memory.get('scope') or 'global'
                if scope == 'workspace':
                    location = memory.get('workspace_path') or workspace_path or '当前工作区'
                    return f'- [工作区: {location}] {memory["content"]}'
                return f'- [全局] {memory["content"]}'

            mem_text = '\n'.join(format_memory(memory) for memory in memories)
            messages.append({
                'role': 'system',
                'content': f'## 用户偏好与记忆\n{mem_text}'
            })

        # 3. 先注入持久摘要，再从摘要覆盖的位置之后读取全部原始历史。
        #    max_history 仅保留为旧调用方的兼容参数，不再参与上下文裁剪。
        summaries = await db.get_summaries(session_id)
        covered_to = 0
        for s in sorted(summaries, key=lambda item: (item.get('msg_to') or 0, item.get('id') or 0)):
            msg_to = int(s.get('msg_to') or 0)
            if msg_to <= covered_to:
                continue
            messages.append({
                'role': 'system',
                'content': f'## 对话摘要（第{s["msg_from"]+1}-{s["msg_to"]}轮）\n{s["content"]}'
            })
            covered_to = msg_to

        history = await db.get_history(session_id, limit=None, after_id=covered_to)

        # 4. 全部未摘要历史作为候选，真正保留多少由 token 预算决定。
        for msg in history:
            content = msg['content'] or ''
            m = {'role': msg['role'], 'content': content}
            # 保留 tool_calls（如果有）
            if msg.get('metadata'):
                import json
                try:
                    meta = json.loads(msg['metadata']) if isinstance(msg['metadata'], str) else msg['metadata']
                    if meta.get('tool_calls'):
                        m['tool_calls'] = meta['tool_calls']
                except Exception:
                    pass
            messages.append(m)

        # 5. 接近上下文上限时才压缩，避免短对话被过早摘要。
        estimated_tokens = self._estimate_msgs_tokens(messages)
        if estimated_tokens > trigger_budget:
            await self._notify_compaction(
                compaction_callback,
                {
                    "phase": "start",
                    "reason": "context_budget",
                    "before_tokens": estimated_tokens,
                },
            )
            try:
                messages = await self._compress_messages(messages, trigger_budget, hard_budget)
            except Exception as exc:
                await self._notify_compaction(
                    compaction_callback,
                    {"phase": "error", "message": str(exc)},
                )
                raise
            await self._notify_compaction(
                compaction_callback,
                {
                    "phase": "done",
                    "before_tokens": estimated_tokens,
                    "after_tokens": self._estimate_msgs_tokens(messages),
                },
            )

        return messages

    @staticmethod
    def _context_budgets(max_context, max_output_tokens=None):
        max_context = max(1, int(max_context or 1))
        default_reserve = max(1, int(max_context * 0.10))
        if max_output_tokens:
            reserve = min(max(1, int(max_context * 0.25)), int(max_output_tokens))
        else:
            reserve = default_reserve
        hard_budget = max(1, max_context - reserve)
        trigger_budget = max(1, int(hard_budget * CONTEXT_TRIGGER_RATIO))
        return trigger_budget, hard_budget

    async def _compress_messages(self, messages, trigger_budget, hard_budget):
        """保留系统指令和最近工作段，把较早历史压缩成一次性摘要。"""
        system_messages = [message for message in messages if message.get('role') == 'system']
        non_system = [message for message in messages if message.get('role') != 'system']
        if len(non_system) <= RECENT_CONTEXT_MESSAGES:
            return self._trim_runtime_system(system_messages, non_system, hard_budget)

        recent = self._recent_work_messages(non_system, RECENT_CONTEXT_MESSAGES)
        recent_count = len(recent)
        dropped = non_system[:-recent_count]
        summary_text = await self._generate_summary(dropped)
        if not summary_text:
            summary_text = self._fallback_summary(dropped)

        summary_message = {
            'role': 'system',
            'content': f'## 早期任务上下文（已压缩）\n{summary_text}',
        }
        result = system_messages + [summary_message] + recent
        if self._estimate_msgs_tokens(result) <= trigger_budget:
            return result

        # 摘要仍然过长时，逐步减少旧消息，只保留最近完整工作段。
        while len(recent) > 4 and self._estimate_msgs_tokens(result) > hard_budget:
            recent = recent[2:]
            result = system_messages + [summary_message] + recent
        return self._trim_runtime_system(system_messages + [summary_message], recent, hard_budget)

    def compact_runtime_messages(self, messages, max_context, max_output_tokens=None):
        """工具循环中使用的无网络轻量压缩，避免工具结果逐轮撑爆上下文。"""
        trigger_budget, hard_budget = self._context_budgets(max_context, max_output_tokens)
        if self._estimate_msgs_tokens(messages) <= trigger_budget:
            return messages

        system_messages = [message for message in messages if message.get('role') == 'system']
        non_system = [message for message in messages if message.get('role') != 'system']
        recent = self._recent_work_messages(non_system, RUNTIME_CONTEXT_MESSAGES)
        recent_count = len(recent)
        dropped = non_system[:-recent_count]
        if not dropped:
            return self._trim_runtime_system(system_messages, recent, hard_budget)

        summary_message = {
            'role': 'system',
            'content': '## 本轮早期工作记录（已压缩）\n' + self._fallback_summary(dropped),
        }
        result = system_messages + [summary_message] + recent
        while len(recent) > 4 and self._estimate_msgs_tokens(result) > hard_budget:
            recent = recent[2:]
            result = system_messages + [summary_message] + recent
        return self._trim_runtime_system(system_messages + [summary_message], recent, hard_budget)

    def needs_runtime_compaction(self, messages, max_context, max_output_tokens=None):
        trigger_budget, _ = self._context_budgets(max_context, max_output_tokens)
        return self._estimate_msgs_tokens(messages) > trigger_budget

    @staticmethod
    async def _notify_compaction(callback, event):
        if not callback:
            return
        result = callback(event)
        if inspect.isawaitable(result):
            await result

    @staticmethod
    def _recent_work_messages(messages, max_messages):
        """从末尾按完整工作单元取消息，避免拆开 tool call 与 tool result。"""
        if not messages:
            return []

        units = []
        index = len(messages) - 1
        while index >= 0:
            message = messages[index]
            role = message.get('role')
            unit = [message]

            if role == 'tool':
                # 一次 assistant tool_calls 后可能紧跟多个 tool 结果。
                index -= 1
                while index >= 0 and messages[index].get('role') == 'tool':
                    unit.insert(0, messages[index])
                    index -= 1
                if index >= 0 and messages[index].get('role') == 'assistant' and messages[index].get('tool_calls'):
                    unit.insert(0, messages[index])
                    index -= 1
            elif role == 'assistant' and not message.get('tool_calls') and index > 0:
                if messages[index - 1].get('role') == 'user':
                    unit.insert(0, messages[index - 1])
                    index -= 1
                index -= 1
            else:
                index -= 1

            units.insert(0, unit)

        selected = []
        count = 0
        for unit in reversed(units):
            if selected and count + len(unit) > max_messages:
                break
            selected[0:0] = unit
            count += len(unit)
        return selected

    def _trim_runtime_system(self, system_messages, recent, hard_budget):
        result = list(system_messages) + list(recent)
        if self._estimate_msgs_tokens(result) <= hard_budget:
            return result

        # 第一条通常是主系统提示，优先保留；只压缩辅助记忆/摘要系统消息。
        if system_messages:
            primary = system_messages[0]
            auxiliary = system_messages[1:]
            available = max(1, hard_budget - self._estimate_msgs_tokens([primary, *recent]))
            compact_auxiliary = []
            for message in auxiliary:
                content = str(message.get('content') or '')
                max_chars = max(200, int(available / max(1, len(auxiliary)) * 2.2))
                compact_auxiliary.append({**message, 'content': content[:max_chars]})
            result = [primary, *compact_auxiliary, *recent]

        while len(result) > 2 and self._estimate_msgs_tokens(result) > hard_budget:
            # 保留最后一条消息和主系统提示，逐步移除最旧的辅助内容。
            removable = next((index for index, item in enumerate(result)
                              if item.get('role') == 'system'
                              and index != 0
                              and not self._is_compressed_message(str(item.get('content', '')))), None)
            if removable is not None:
                result.pop(removable)
                continue

            compressed_index = next((index for index, item in enumerate(result)
                                     if item.get('role') == 'system' and index != 0), None)
            if compressed_index is not None:
                content = str(result[compressed_index].get('content') or '')
                heading = content.splitlines()[0].strip()
                minimum = max(16, len(heading))
                target = max(minimum, min(240, len(content) // 2))
                if self._is_compressed_message(content):
                    body_budget = max(0, target - len(heading) - 1)
                    shortened = heading + (
                        '\n' + content[len(heading) + 1:][:body_budget]
                        if body_budget else ''
                    )
                else:
                    shortened = self._truncate_middle(content, target)
                if shortened != content:
                    result[compressed_index] = {
                        **result[compressed_index],
                        'content': shortened,
                    }
                    continue
            # 最近两条通常构成一轮用户/助手消息或一次工具调用/结果，不能拆散。
            runtime_indices = [
                index for index, item in enumerate(result)
                if index != 0 and item.get('role') != 'system'
            ]
            if len(runtime_indices) <= 2:
                break
            oldest_runtime = next(
                (index for index, item in enumerate(result)
                 if index != 0 and item.get('role') != 'system'),
                None,
            )
            if oldest_runtime is None:
                break
            result.pop(oldest_runtime)

        # 极小预算或超大工具结果下，保留最近工作单元的首尾，而不是整条删除。
        while self._estimate_msgs_tokens(result) > hard_budget:
            candidates = []
            for index, item in enumerate(result):
                if index == 0:
                    continue
                content = item.get('content', '')
                if not isinstance(content, str):
                    continue
                minimum = 24
                if item.get('role') == 'system':
                    minimum = max(16, len(content.splitlines()[0].strip()))
                if len(content) > minimum:
                    candidates.append((len(content), index, minimum))
            if not candidates:
                break
            _, index, minimum = max(candidates)
            content = result[index].get('content', '')
            target = max(minimum, len(content) // 2)
            if result[index].get('role') == 'system' and self._is_compressed_message(content):
                heading = content.splitlines()[0].strip()
                body_budget = max(0, target - len(heading) - 1)
                shortened = heading + (
                    '\n' + content[len(heading) + 1:][:body_budget]
                    if body_budget else ''
                )
            else:
                shortened = self._truncate_middle(content, target)
            result[index] = {**result[index], 'content': shortened}
        return result

    @staticmethod
    def _is_compressed_message(content):
        return str(content or '').startswith((
            '## 早期任务上下文（已压缩）',
            '## 本轮早期工作记录（已压缩）',
        ))

    @staticmethod
    def _truncate_middle(content, max_chars):
        content = str(content or '')
        max_chars = max(1, int(max_chars))
        if len(content) <= max_chars:
            return content
        if max_chars < 12:
            return content[:max_chars]
        marker = ' ... '
        available = max_chars - len(marker)
        head = max(1, int(available * 0.7))
        tail = max(1, available - head)
        return content[:head] + marker + content[-tail:]

    @staticmethod
    def _fallback_summary(messages):
        lines = []
        for message in messages:
            role = message.get('role', 'unknown')
            content = message.get('content', '')
            if isinstance(content, list):
                content = json.dumps(content, ensure_ascii=False)
            content = str(content).replace('\x00', ' ').strip()
            if not content:
                continue
            if len(content) > 600:
                content = content[:360] + ' ... ' + content[-180:]
            lines.append(f'{role}: {content}')
        text = '\n'.join(lines)
        return text[:MAX_FALLBACK_SUMMARY_CHARS] or '早期工作记录为空。'

    async def _generate_summary(self, messages):
        """用 LLM 生成对话摘要"""
        if not self.model or len(messages) < 2:
            return None

        # 限制摘要输入长度
        dialog_parts = []
        total_len = 0
        for m in messages:
            content = m.get('content', '')[:500]
            line = f"{m['role']}: {content}"
            if total_len + len(line) > 8000:
                break
            dialog_parts.append(line)
            total_len += len(line)

        dialog = '\n'.join(dialog_parts)
        prompt = f"将以下对话压缩为简洁摘要，保留关键信息（任务、结论、用户需求）。不超过500字：\n{dialog}\n\n摘要："

        try:
            result = await self.model.chat([{"role": "user", "content": prompt}], stream=False, max_tokens=800)
            return result.content
        except Exception:
            return None

    async def add_message(self, session_id, role, content, persona='default', segments=None, metadata=None, client_message_id=None):
        await db.save_message(
            session_id,
            role,
            content,
            persona,
            metadata=metadata or {},
            segments=segments,
            client_message_id=client_message_id,
        )

    async def post_conversation(
        self,
        session_id,
        user_message,
        assistant_response,
        max_context=None,
        max_output_tokens=None,
        compaction_callback=None,
        workspace_path=None,
    ):
        """对话结束后调用：自动提取记忆 + 生成摘要"""
        await db.delete_expired_memories()
        await self._maybe_extract_memories(
            session_id,
            user_message,
            assistant_response,
            workspace_path=workspace_path,
        )
        await self._maybe_summarize(
            session_id,
            max_context=max_context,
            max_output_tokens=max_output_tokens,
            compaction_callback=compaction_callback,
        )

    async def _maybe_extract_memories(
        self,
        session_id,
        user_message,
        assistant_response,
        workspace_path=None,
    ):
        """规则过滤 + 批量提取记忆"""
        combined = user_message + assistant_response
        has_keyword = any(kw in combined for kw in MEMORY_KEYWORDS)
        if not has_keyword:
            return

        if not self.model:
            return

        workspace_path = self._normalize_workspace(workspace_path)
        memory_scope = 'workspace' if workspace_path else 'global'

        prompt = f"""判断以下对话中是否有值得长期记住的用户偏好、事实或指令。
只提取明确的、稳定的偏好，不要提取临时性需求。
返回 JSON 数组，每个元素 {{"memory": "内容", "category": "preference/fact/instruction"}}
如果没有值得记住的，返回空数组 []

用户：{user_message[:500]}
助手：{assistant_response[:500]}"""

        try:
            result = await self.model.chat([{"role": "user", "content": prompt}], stream=False)
            import json
            memories = json.loads(result.content)
            if not isinstance(memories, list):
                return

            for m in memories:
                content = m.get('memory')
                category = m.get('category', 'general')
                if not content:
                    continue
                dup_id = await db.check_duplicate_memory(
                    content,
                    scope=memory_scope,
                    workspace_path=workspace_path,
                )
                if dup_id:
                    continue
                expired_at = datetime.now() + timedelta(days=30)
                await db.save_memory(
                    content,
                    category=category,
                    source='auto',
                    expired_at=expired_at.isoformat(),
                    scope=memory_scope,
                    workspace_path=workspace_path,
                )
        except Exception:
            pass

    async def _maybe_summarize(
        self,
        session_id,
        max_context=None,
        max_output_tokens=None,
        compaction_callback=None,
    ):
        """仅在未摘要内容接近 token 水位时生成持久摘要。"""
        max_ctx = max_context or self.max_tokens
        trigger_budget, _ = self._context_budgets(max_ctx, max_output_tokens)
        uncovered_msgs = await db.get_uncovered_history(session_id, limit=None)
        if len(uncovered_msgs) < 4:
            return

        uncovered_tokens = self._estimate_msgs_tokens(uncovered_msgs)
        if uncovered_tokens < trigger_budget:
            return

        candidates = self._compression_candidates(uncovered_msgs)
        if len(candidates) < 4:
            return
        before_tokens = self._estimate_msgs_tokens(uncovered_msgs)
        await self._notify_compaction(
            compaction_callback,
            {
                "phase": "start",
                "reason": "persistent_summary",
                "before_tokens": before_tokens,
            },
        )
        try:
            saved = await self._do_summarize(session_id, candidates)
        except Exception as exc:
            await self._notify_compaction(
                compaction_callback,
                {"phase": "error", "reason": "persistent_summary", "message": str(exc)},
            )
            raise
        if saved:
            await self._notify_compaction(
                compaction_callback,
                {
                    "phase": "done",
                    "reason": "persistent_summary",
                    "before_tokens": before_tokens,
                    "after_tokens": self._estimate_msgs_tokens(uncovered_msgs) - self._estimate_msgs_tokens(candidates),
                },
            )

    @staticmethod
    def _compression_candidates(messages):
        """选择要归档的旧前缀，保留最近一段完整工作记录。"""
        if len(messages) < 8:
            return []
        keep_count = min(RECENT_CONTEXT_MESSAGES, max(4, len(messages) // 3))
        return messages[:-keep_count]

    async def compact_session(self, session_id):
        """手动压缩当前会话；无模型时使用本地摘要兜底。"""
        uncovered_msgs = await db.get_uncovered_history(session_id, limit=None)
        candidates = self._compression_candidates(uncovered_msgs)
        if len(candidates) < 4:
            return {
                "compressed": False,
                "message_count": len(uncovered_msgs),
                "reason": "没有足够的旧上下文可压缩",
            }

        summary = await self._generate_summary(candidates)
        summary = summary or self._fallback_summary(candidates)
        msg_from = candidates[0]["id"]
        msg_to = candidates[-1]["id"]
        await db.save_summary(session_id, summary, msg_from, msg_to, level=1)
        return {
            "compressed": True,
            "message_count": len(candidates),
            "remaining_messages": len(uncovered_msgs) - len(candidates),
            "msg_from": msg_from,
            "msg_to": msg_to,
        }

    async def _do_summarize(self, session_id, messages):
        """生成摘要"""
        if not self.model:
            return False

        if len(messages) < 4:
            return False

        dialog = '\n'.join(f"{m['role']}: {m['content'][:300]}" for m in messages)
        prompt = f"将以下对话压缩为简洁摘要，保留关键信息：\n{dialog}\n\n摘要："

        try:
            result = await self.model.chat([{"role": "user", "content": prompt}], stream=False, max_tokens=500)
            msg_from = messages[0]['id']
            msg_to = messages[-1]['id']
            await db.save_summary(session_id, result.content, msg_from, msg_to, level=1)
            return True
        except Exception:
            return False

    async def save_memory_manual(self, content, category='general', workspace_path=None):
        """手动保存记忆（永不过期）"""
        workspace_path = self._normalize_workspace(workspace_path)
        memory_scope = 'workspace' if workspace_path else 'global'
        dup_id = await db.check_duplicate_memory(
            content,
            scope=memory_scope,
            workspace_path=workspace_path,
        )
        if dup_id:
            return dup_id
        return await db.save_memory(
            content,
            category=category,
            source='manual',
            expired_at=None,
            scope=memory_scope,
            workspace_path=workspace_path,
        )
