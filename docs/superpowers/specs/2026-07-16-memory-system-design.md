# 次元人格 — 记忆系统设计（v2）

> 日期：2026-07-16

## 1. 概述

为 agent 添加长期记忆和上下文压缩能力。长期记忆跨会话共享，所有角色均可访问；上下文压缩采用分层摘要策略。

**核心原则：**
- 记忆全局共享，不关联特定角色
- 记忆对人格设定为软影响（参考，不覆盖）
- 规则过滤 + 批量提取（降低成本）
- 记忆有上限和过期机制

## 2. 数据模型

### 2.1 memories 表（长期记忆）

```sql
CREATE TABLE IF NOT EXISTS memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT NOT NULL,
    category TEXT DEFAULT 'general',  -- preference/fact/instruction/general
    source TEXT DEFAULT 'auto',       -- auto/manual
    expired_at TIMESTAMP DEFAULT NULL, -- 过期时间（NULL=永不过期）
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

- 手动记忆：expired_at = NULL（永不过期）
- 自动记忆：expired_at 默认 30 天后（临时性信息自动过期）

### 2.2 summaries 表（分层摘要）

```sql
CREATE TABLE IF NOT EXISTS summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    level INTEGER DEFAULT 1,         -- 摘要层级：1=原始摘要, 2=聚合摘要
    content TEXT NOT NULL,
    msg_from INTEGER,
    msg_to INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

- 去掉 persona 字段（会话已绑定角色，摘要按 session_id 隔离即可）
- 增加 level 字段（支持二级聚合）

---

## 3. 上下文加载流程

```python
async def get_context(self, session_id, system_prompt):
    messages = []

    # 1. system_prompt
    if system_prompt:
        messages.append({'role': 'system', 'content': system_prompt})

    # 2. 长期记忆注入（Top-N，最多 20 条，按时间倒序）
    memories = await self.get_memories(limit=20)
    if memories:
        mem_text = '\n'.join(f'- {m["content"]}' for m in memories)
        messages.append({
            'role': 'system',
            'content': f'## 用户偏好与记忆\n以下是关于用户的重要信息，请在回复时参考：\n{mem_text}'
        })

    # 3. 分层摘要注入（每条摘要独立为一条 system 消息）
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

    # 5. token 裁剪（优先级：旧摘要 > 旧记忆 > system_prompt）
    while self._estimate_tokens(messages) > self.max_tokens and len(messages) > 3:
        # 找到第一条摘要 system 消息并删除
        removed = False
        for i in range(2, len(messages)):
            if messages[i]['role'] == 'system' and '对话摘要' in messages[i].get('content', ''):
                messages.pop(i)
                removed = True
                break
        if not removed:
            # 没有摘要可删，删长期记忆
            if len(messages) > 3 and '用户偏好' in messages[1].get('content', ''):
                messages.pop(1)
            else:
                break

    return messages
```

**注入顺序：** system_prompt → 长期记忆 → 摘要（逐条）→ 近期原文

**裁剪优先级：** 旧摘要（逐条删）→ 长期记忆 → system_prompt

---

## 4. 长期记忆管理

### 4.1 自动提取（规则过滤 + 批量）

**触发条件：** 每 3-5 轮对话批量检查一次，先过规则过滤，再调 LLM。

```python
MEMORY_KEYWORDS = ['记住', '我喜欢', '我不喜欢', '以后', '总是', '不要', '偏好', '习惯']

async def _maybe_extract_memories(self, session_id):
    """每 3 轮检查一次"""
    msg_count = await db.get_message_count(session_id)
    if msg_count % 3 != 0:
        return

    # 获取最近 3 轮对话
    recent = await db.get_history(session_id, limit=6)
    if len(recent) < 2:
        return

    # 规则过滤：检查是否包含记忆关键词
    has_keyword = any(
        kw in msg.get('content', '')
        for msg in recent
        for kw in MEMORY_KEYWORDS
    )

    if not has_keyword:
        return  # 没有关键词，跳过 LLM 调用

    # 批量提取
    dialog = '\n'.join(f"{m['role']}: {m['content'][:300]}" for m in recent)
    prompt = f"""判断以下对话中是否有值得长期记住的用户偏好、事实或指令。
只提取明确的、稳定的偏好。返回 JSON 数组，每个元素 {{"memory": "内容", "category": "preference/fact/instruction"}}
如果没有值得记住的，返回空数组 []

对话：
{dialog}"""

    result = await self.model.chat([{"role": "user", "content": prompt}], stream=False)
    # 解析结果，去重后保存
```

### 4.2 去重

保存前检查是否有内容相似的记忆（简单字符串匹配：`new_content in existing or existing in new_content`），有则跳过。

### 4.3 优先级

- 手动记忆 > 自动记忆（手动不可被自动覆盖）
- 新记忆 > 旧记忆（冲突时保留新的）

### 4.4 过期清理

定期清理 expired_at 已过期的记忆。

### 4.5 手动触发

- 用户说"记住xxx" → agent 调用 `save_memory` 工具（source=manual, expired_at=NULL）
- agent 主动判断 → 调用 `save_memory`（source=auto, expired_at=30天后）

### 4.6 管理接口

```
GET    /api/memories              — 获取所有记忆（支持 ?category=xxx 筛选）
POST   /api/memories              — 手动添加记忆
PUT    /api/memories/{id}         — 编辑记忆
DELETE /api/memories/{id}         — 删除记忆
```

---

## 5. 分层摘要

### 5.1 触发策略（Token 阈值为主，轮次为辅）

```python
async def _maybe_summarize(self, session_id):
    uncovered = await self._get_uncovered_message_count(session_id)
    uncovered_tokens = await self._estimate_uncovered_tokens(session_id)

    # Token 阈值触发（主）
    if uncovered_tokens >= self.max_tokens * 0.5:
        await self._do_summarize(session_id, uncovered)
        return

    # 轮次兜底（辅）
    if uncovered >= 10:
        await self._do_summarize(session_id, min(uncovered, 10))
```

### 5.2 生成摘要

```python
async def _do_summarize(self, session_id, count):
    messages = await db.get_uncovered_history(session_id, count)
    dialog = '\n'.join(f"{m['role']}: {m['content']}" for m in messages)  # 不截断

    prompt = f"""将以下对话压缩为一段简洁的摘要，保留关键信息（做了什么、结论、用户需求）：
{dialog}

摘要："""
    result = await self.model.chat([{"role": "user", "content": prompt}], stream=False)

    msg_from = messages[0]['id']
    msg_to = messages[-1]['id']
    await db.save_summary(session_id, result.content, msg_from, msg_to, level=1)
```

### 5.3 二级聚合

当一级摘要数量达到 10 条时，将它们聚合为一条二级摘要：

```python
async def _maybe_aggregate(self, session_id):
    level1 = await db.get_summaries(session_id, level=1)
    if len(level1) >= 10:
        combined = '\n\n'.join(s['content'] for s in level1)
        prompt = f"将以下多段对话摘要聚合为一段更高级的摘要：\n{combined}\n\n聚合摘要："
        result = await self.model.chat([{"role": "user", "content": prompt}], stream=False)
        # 保存二级摘要，删除被聚合的一级摘要
        await db.save_summary(session_id, result.content, level1[0]['msg_from'], level1[-1]['msg_to'], level=2)
        await db.delete_summaries([s['id'] for s in level1])
```

---

## 6. 记忆工具

```python
class SaveMemoryTool(BaseTool):
    name = "save_memory"
    description = "保存一条长期记忆（用户偏好、事实或指令）"
    parameters = {
        "type": "object",
        "properties": {
            "content": {"type": "string", "description": "记忆内容"},
            "category": {"type": "string", "enum": ["preference", "fact", "instruction", "general"]}
        },
        "required": ["content"]
    }
```

---

## 7. 前端改动

### 7.1 设置页"记忆管理" tab

- 分类筛选（全部/偏好/事实/指令）
- 关键词搜索
- 记忆列表（内容 + 分类 + 来源 + 过期时间）
- 手动添加输入框
- 编辑/删除按钮

---

## 8. 开发阶段

| 阶段 | 内容 |
|------|------|
| M0 | 数据库扩展（memories + summaries 表）+ MemoryManager 重构 |
| M1 | 长期记忆：规则过滤 + 批量提取 + 去重 + 过期 + save_memory 工具 |
| M2 | 分层摘要：Token 阈值触发 + 逐条注入 + 二级聚合 |
| M3 | 前端记忆管理 tab（分类筛选 + 搜索 + 编辑） |
