from db.database import db
from config import settings
from datetime import datetime, timedelta

MEMORY_KEYWORDS = ['记住', '我喜欢', '我不喜欢', '以后', '总是', '不要', '偏好', '习惯']


class MemoryManager:
    def __init__(self, max_tokens=None, model=None):
        self.max_tokens = max_tokens or settings.MAX_CONTEXT_TOKENS
        self.model = model  # LLM adapter，用于摘要和记忆提取

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

    async def get_context(self, session_id, system_prompt='', max_history=None, max_context=None):
        """构建上下文：system + 记忆 + 摘要 + 全部历史，超限时自动压缩"""
        max_ctx = max_context or self.max_tokens
        messages = []

        # 1. system_prompt
        if system_prompt:
            messages.append({'role': 'system', 'content': system_prompt})

        # 2. 长期记忆（全部，不截断）
        memories = await db.get_memories(limit=50)
        if memories:
            mem_text = '\n'.join(f'- {m["content"]}' for m in memories)
            messages.append({
                'role': 'system',
                'content': f'## 用户偏好与记忆\n{mem_text}'
            })

        # 3. 分层摘要
        summaries = await db.get_summaries(session_id)
        for s in summaries:
            messages.append({
                'role': 'system',
                'content': f'## 对话摘要（第{s["msg_from"]+1}-{s["msg_to"]}轮）\n{s["content"]}'
            })

        # 4. 全部历史（MiMo 百万上下文，尽量保留全部）
        limit = max_history or 500
        history = await db.get_history(session_id, limit=limit)
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

        # 5. 智能压缩：只在真的超限时才压缩
        total_tokens = self._estimate_msgs_tokens(messages)
        if total_tokens > max_ctx:
            messages = await self._compress_messages(session_id, messages, max_ctx)

        return messages

    async def _compress_messages(self, session_id, messages, max_ctx):
        """压缩策略：保留 system + 最近 20 轮，中间部分做摘要"""
        # 找到所有非 system 消息的位置
        non_system = [(i, m) for i, m in enumerate(messages) if m['role'] != 'system']
        if len(non_system) <= 20:
            # 消息不多，直接删旧的
            return messages

        # 保留最近 20 轮（40 条消息）
        keep_recent = 40
        split_idx = non_system[-keep_recent][0] if len(non_system) > keep_recent else 0

        if split_idx <= 0:
            return messages

        # 要压缩的部分（split_idx 之前的所有非 system 消息）
        to_compress = [m for i, m in enumerate(messages) if i < split_idx and m['role'] != 'system']
        to_keep = [m for i, m in enumerate(messages) if i >= split_idx or m['role'] == 'system']

        if len(to_compress) < 4:
            return messages

        # 生成摘要
        summary_text = await self._generate_summary(to_compress)
        if summary_text:
            # 插入摘要到 system 消息之后
            system_count = sum(1 for m in to_keep if m['role'] == 'system')
            to_keep.insert(system_count, {
                'role': 'system',
                'content': f'## 早期对话摘要\n{summary_text}'
            })

        # 保存摘要到数据库
        try:
            if to_compress:
                first_content = to_compress[0].get('content', '')
                last_content = to_compress[-1].get('content', '')
                await db.save_summary(
                    session_id, summary_text or '对话已压缩',
                    msg_from=0, msg_to=0, level=1
                )
        except Exception:
            pass

        return to_keep

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

    async def post_conversation(self, session_id, user_message, assistant_response):
        """对话结束后调用：自动提取记忆 + 生成摘要"""
        await db.delete_expired_memories()
        await self._maybe_extract_memories(session_id, user_message, assistant_response)
        await self._maybe_summarize(session_id)

    async def _maybe_extract_memories(self, session_id, user_message, assistant_response):
        """规则过滤 + 批量提取记忆"""
        combined = user_message + assistant_response
        has_keyword = any(kw in combined for kw in MEMORY_KEYWORDS)
        if not has_keyword:
            return

        if not self.model:
            return

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
                dup_id = await db.check_duplicate_memory(content)
                if dup_id:
                    continue
                expired_at = datetime.now() + timedelta(days=30)
                await db.save_memory(content, category=category, source='auto', expired_at=expired_at.isoformat())
        except Exception:
            pass

    async def _maybe_summarize(self, session_id):
        """检查是否需要生成摘要"""
        uncovered = await db.get_uncovered_message_count(session_id)

        # 20 轮（40 条消息）或 token 超过 60% 时摘要
        if uncovered >= 40:
            await self._do_summarize(session_id, min(uncovered, 40))
        elif uncovered >= 20:
            uncovered_msgs = await db.get_uncovered_history(session_id, uncovered)
            uncovered_tokens = self._estimate_msgs_tokens(uncovered_msgs)
            if uncovered_tokens >= self.max_tokens * 0.6:
                await self._do_summarize(session_id, min(uncovered, 20))

    async def _do_summarize(self, session_id, count):
        """生成摘要"""
        if not self.model:
            return

        messages = await db.get_uncovered_history(session_id, count)
        if len(messages) < 4:
            return

        dialog = '\n'.join(f"{m['role']}: {m['content'][:300]}" for m in messages)
        prompt = f"将以下对话压缩为简洁摘要，保留关键信息：\n{dialog}\n\n摘要："

        try:
            result = await self.model.chat([{"role": "user", "content": prompt}], stream=False, max_tokens=500)
            msg_from = messages[0]['id']
            msg_to = messages[-1]['id']
            await db.save_summary(session_id, result.content, msg_from, msg_to, level=1)
        except Exception:
            pass

    async def save_memory_manual(self, content, category='general'):
        """手动保存记忆（永不过期）"""
        dup_id = await db.check_duplicate_memory(content)
        if dup_id:
            return dup_id
        await db.save_memory(content, category=category, source='manual', expired_at=None)
