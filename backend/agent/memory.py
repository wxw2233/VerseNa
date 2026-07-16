from db.database import db
from config import settings
from datetime import datetime, timedelta

MEMORY_KEYWORDS = ['记住', '我喜欢', '我不喜欢', '以后', '总是', '不要', '偏好', '习惯']

class MemoryManager:
    def __init__(self, max_tokens=None, model=None):
        self.max_tokens = max_tokens or settings.MAX_CONTEXT_TOKENS
        self.model = model  # LLM adapter，用于摘要和记忆提取

    def _estimate_tokens(self, messages):
        total = 0
        for msg in messages:
            total += len(msg.get('content', '')) // 2
        return total

    async def get_context(self, session_id, system_prompt=''):
        messages = []

        # 1. system_prompt
        if system_prompt:
            messages.append({'role': 'system', 'content': system_prompt})

        # 2. 长期记忆 Top-20
        memories = await db.get_memories(limit=20)
        if memories:
            mem_text = '\n'.join(f'- {m["content"]}' for m in memories)
            messages.append({
                'role': 'system',
                'content': f'## 用户偏好与记忆\n以下是关于用户的重要信息，请在回复时参考：\n{mem_text}'
            })

        # 3. 分层摘要（逐条注入）
        summaries = await db.get_summaries(session_id)
        for s in summaries:
            messages.append({
                'role': 'system',
                'content': f'## 对话摘要（第{s["msg_from"]+1}-{s["msg_to"]}轮）\n{s["content"]}'
            })

        # 4. 最近 20 轮原文
        history = await db.get_history(session_id, limit=20)
        for msg in history:
            messages.append({'role': msg['role'], 'content': msg['content']})

        # 5. token 裁剪（旧摘要 > 长期记忆 > system_prompt）
        while self._estimate_tokens(messages) > self.max_tokens and len(messages) > 3:
            removed = False
            for i in range(2, len(messages)):
                if messages[i]['role'] == 'system' and '对话摘要' in messages[i].get('content', ''):
                    messages.pop(i)
                    removed = True
                    break
            if not removed:
                if len(messages) > 3 and '用户偏好' in messages[1].get('content', ''):
                    messages.pop(1)
                else:
                    break

        return messages

    async def add_message(self, session_id, role, content, persona='default'):
        await db.save_message(session_id, role, content, persona)

    async def post_conversation(self, session_id, user_message, assistant_response):
        """对话结束后调用：自动提取记忆 + 生成摘要"""
        await db.delete_expired_memories()
        await self._maybe_extract_memories(session_id, user_message, assistant_response)
        await self._maybe_summarize(session_id)

    async def _maybe_extract_memories(self, session_id, user_message, assistant_response):
        """规则过滤 + 批量提取记忆"""
        # 规则过滤
        combined = user_message + assistant_response
        has_keyword = any(kw in combined for kw in MEMORY_KEYWORDS)
        if not has_keyword:
            return

        if not self.model:
            return

        # LLM 提取
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
                # 去重
                dup_id = await db.check_duplicate_memory(content)
                if dup_id:
                    continue
                # 保存（30天过期）
                expired_at = datetime.now() + timedelta(days=30)
                await db.save_memory(content, category=category, source='auto', expired_at=expired_at.isoformat())
        except Exception:
            pass  # 提取失败不影响主流程

    async def _maybe_summarize(self, session_id):
        """Token 阈值为主，10 轮兜底"""
        uncovered = await db.get_uncovered_message_count(session_id)

        # Token 阈值检查
        if uncovered >= 10:
            uncovered_msgs = await db.get_uncovered_history(session_id, uncovered)
            uncovered_tokens = self._estimate_tokens([{'content': m['content']} for m in uncovered_msgs])
            if uncovered_tokens >= self.max_tokens * 0.5:
                await self._do_summarize(session_id, min(uncovered, 10))
                return

        # 轮次兜底
        if uncovered >= 10:
            await self._do_summarize(session_id, 10)

        # 二级聚合检查
        await self._maybe_aggregate(session_id)

    async def _do_summarize(self, session_id, count):
        """生成摘要"""
        if not self.model:
            return

        messages = await db.get_uncovered_history(session_id, count)
        if len(messages) < 2:
            return

        dialog = '\n'.join(f"{m['role']}: {m['content']}" for m in messages)
        prompt = f"将以下对话压缩为一段简洁的摘要，保留关键信息（做了什么、结论、用户需求）：\n{dialog}\n\n摘要："

        try:
            result = await self.model.chat([{"role": "user", "content": prompt}], stream=False)
            msg_from = messages[0]['id']
            msg_to = messages[-1]['id']
            await db.save_summary(session_id, result.content, msg_from, msg_to, level=1)
        except Exception:
            pass

    async def _maybe_aggregate(self, session_id):
        """一级摘要达 10 条时聚合为二级"""
        if not self.model:
            return

        level1 = await db.get_summaries(session_id, level=1)
        if len(level1) < 10:
            return

        combined = '\n\n'.join(s['content'] for s in level1)
        prompt = f"将以下多段对话摘要聚合为一段更高级的摘要：\n{combined}\n\n聚合摘要："

        try:
            result = await self.model.chat([{"role": "user", "content": prompt}], stream=False)
            await db.save_summary(session_id, result.content, level1[0]['msg_from'], level1[-1]['msg_to'], level=2)
            await db.delete_summaries([s['id'] for s in level1])
        except Exception:
            pass

    async def save_memory_manual(self, content, category='general'):
        """手动保存记忆（永不过期）"""
        dup_id = await db.check_duplicate_memory(content)
        if dup_id:
            return dup_id
        await db.save_memory(content, category=category, source='manual', expired_at=None)
