# 次元人格 — 记忆系统设计

> 日期：2026-07-16

## 1. 概述

为 agent 添加长期记忆和上下文压缩能力。长期记忆跨会话共享，所有角色均可访问；上下文压缩采用分层摘要策略，每 10 轮对话自动生成摘要。

**核心原则：**
- 记忆全局共享，不关联特定角色
- 记忆对人格设定为软影响（参考，不覆盖）
- 自动提取 + 手动管理

## 2. 数据模型

### 2.1 memories 表（长期记忆）

```sql
CREATE TABLE IF NOT EXISTS memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT NOT NULL,
    category TEXT DEFAULT 'general',  -- preference/fact/instruction/general
    source TEXT DEFAULT 'auto',       -- auto/manual
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

### 2.2 summaries 表（分层摘要）

```sql
CREATE TABLE IF NOT EXISTS summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    persona TEXT DEFAULT 'default',
    content TEXT NOT NULL,
    msg_from INTEGER,
    msg_to INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

---

## 3. 上下文加载流程

```python
async def get_context(self, session_id, system_prompt, persona='default'):
    messages = []

    # 1. system_prompt（角色人设 + 工具描述）
    if system_prompt:
        messages.append({'role': 'system', 'content': system_prompt})

    # 2. 长期记忆注入（全局共享）
    memories = await self.get_memories()
    if memories:
        mem_text = '\n'.join(f'- {m}' for m in memories)
        messages.append({
            'role': 'system',
            'content': f'## 用户偏好与记忆\n以下是关于用户的重要信息，请在回复时参考：\n{mem_text}'
        })

    # 3. 分层摘要注入
    summaries = await db.get_summaries(session_id, persona)
    if summaries:
        summary_text = '\n\n'.join(s['content'] for s in summaries)
        messages.append({
            'role': 'system',
            'content': f'## 之前的对话摘要\n{summary_text}'
        })

    # 4. 最近 20 轮原文
    history = await db.get_history(session_id, limit=20)
    for msg in history:
        messages.append({'role': msg['role'], 'content': msg['content']})

    # 5. token 裁剪（优先级：摘要 > 长期记忆 > system_prompt）
    while self._estimate_tokens(messages) > self.max_tokens and len(messages) > 3:
        if len(messages) > 4:
            messages.pop(2)  # 删除最旧的摘要
        else:
            messages.pop(1)  # 删除长期记忆

    return messages
```

**注入顺序：** system_prompt → 长期记忆 → 摘要 → 近期原文

---

## 4. 长期记忆管理

### 4.1 自动提取

每轮对话结束后，用 LLM 判断是否有值得记住的信息：

```python
async def _auto_extract(self, user_message, assistant_response):
    prompt = f"""判断以下对话中是否有值得长期记住的用户偏好、事实或指令。
只提取明确的、稳定的偏好，不要提取临时性需求。

用户：{user_message}
助手：{assistant_response}

如果有值得记住的内容，返回 JSON：{{"memory": "记忆内容", "category": "preference/fact/instruction"}}
如果没有，返回：{{"memory": null}}"""

    result = await self.model.chat([{"role": "user", "content": prompt}], stream=False)
    # 解析结果，保存到 memories 表
```

**category 分类：**
- `preference` — 用户偏好（"我喜欢简洁的回答"）
- `fact` — 用户事实（"我是大学生"）
- `instruction` — 指令（"不要用英文回复"）
- `general` — 其他

### 4.2 手动触发

- 用户发消息包含"记住"关键词 → agent 调用 `save_memory` 工具
- agent 主动判断重要信息 → 调用 `save_memory` 工具

### 4.3 管理接口

```
GET    /api/memories          — 获取所有记忆
POST   /api/memories          — 手动添加记忆
DELETE /api/memories/{id}     — 删除记忆
```

前端设置页新增"记忆管理"tab，显示所有记忆列表，可手动添加/删除。

---

## 5. 分层摘要

### 5.1 生成时机

每 10 轮对话自动触发：

```python
async def _maybe_summarize(self, session_id, persona):
    msg_count = await db.get_message_count(session_id)
    existing_count = await db.get_summary_count(session_id, persona)
    covered = existing_count * 10
    uncovered = msg_count - covered

    if uncovered >= 10:
        messages = await db.get_history_range(session_id, covered, covered + 10)
        summary = await self._generate_summary(messages)
        await db.save_summary(session_id, persona, summary, covered, covered + 10)
```

### 5.2 摘要生成

```python
async def _generate_summary(self, messages):
    dialog = '\n'.join(f"{m['role']}: {m['content'][:200]}" for m in messages)
    prompt = f"""将以下对话压缩为一段简洁的摘要，保留关键信息（做了什么、结论、用户需求）：
{dialog}

摘要："""
    result = await self.model.chat([{"role": "user", "content": prompt}], stream=False)
    return result.content
```

---

## 6. 记忆工具

新增 `save_memory` 工具，供 agent 调用：

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

- 记忆列表（卡片形式，显示内容 + 分类 + 来源 + 时间）
- 手动添加记忆输入框
- 删除按钮

### 7.2 ChatView

- 无需改动，记忆通过 system prompt 自动注入

---

## 8. 开发阶段

| 阶段 | 内容 |
|------|------|
| M0 | 数据库扩展（memories + summaries 表）+ MemoryManager 重构 |
| M1 | 长期记忆自动提取 + save_memory 工具 |
| M2 | 分层摘要生成 |
| M3 | 前端记忆管理 tab |
