# 记忆系统实现计划

**Goal:** 为 agent 添加长期记忆和分层摘要能力。

## M0: 数据库扩展 + MemoryManager 重构

### Task 1

**Files:**
- Modify: `backend/db/database.py`
- Modify: `backend/agent/memory.py`

- [ ] memories 表创建（id, content, category, source, expired_at, created_at）
- [ ] summaries 表创建（id, session_id, level, content, msg_from, msg_to, created_at）
- [ ] DB 方法：get_memories, save_memory, delete_memory, update_memory
- [ ] DB 方法：get_summaries, save_summary, delete_summaries, get_summary_count
- [ ] DB 方法：get_uncovered_history, get_uncovered_message_count
- [ ] MemoryManager.get_context 重构（长期记忆 Top-20 + 摘要逐条注入 + 裁剪）
- [ ] 测试 + 提交

## M1: 长期记忆自动提取 + save_memory 工具

### Task 2

**Files:**
- Modify: `backend/agent/memory.py`
- Modify: `backend/agent/react.py`
- Create: `backend/tools/builtin/save_memory.py`
- Modify: `backend/api/config_api.py`

- [ ] _maybe_extract_memories（规则过滤 + 批量 LLM 提取）
- [ ] 记忆关键词列表：['记住', '我喜欢', '我不喜欢', '以后', '总是', '不要', '偏好', '习惯']
- [ ] 去重逻辑（字符串包含匹配）
- [ ] 过期清理（expired_at 已过期的自动删除）
- [ ] save_memory 工具（手动触发）
- [ ] react.py 中调用 _maybe_extract_memories
- [ ] API：GET/POST/PUT/DELETE /api/memories
- [ ] 测试 + 提交

## M2: 分层摘要

### Task 3

**Files:**
- Modify: `backend/agent/memory.py`

- [ ] _maybe_summarize（Token 阈值 50% + 10 轮兜底）
- [ ] _do_summarize（LLM 压缩，不截断内容）
- [ ] _maybe_aggregate（一级达 10 条时聚合为二级）
- [ ] react.py 中调用 _maybe_summarize
- [ ] 测试 + 提交

## M3: 前端记忆管理

### Task 4

**Files:**
- Modify: `frontend/src/views/SettingsView.vue`

- [ ] "记忆管理" tab
- [ ] 分类筛选（全部/偏好/事实/指令）
- [ ] 关键词搜索
- [ ] 记忆列表（内容 + 分类 + 来源 + 过期时间）
- [ ] 手动添加输入框
- [ ] 编辑/删除按钮
- [ ] 构建 + 提交
