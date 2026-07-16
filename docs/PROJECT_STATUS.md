# 次元人格（CiYuan Persona）— 项目进度总结

> 最后更新：2026-07-16
> 技术栈：FastAPI + Vue 3 + SQLite + WebSocket

---

## 一、项目概述

面向二次元用户的 AI Agent 平台，核心卖点是高度可自定义的图形化界面（换肤系统）和完整的 Agent 能力。

**运行环境：**
- 后端：FastAPI，端口 8001
- 前端：Vue 3 + Vite，端口 5173
- 数据库：SQLite（aiosqlite）
- 模型：OpenAI 兼容接口（当前使用 mimo-v2.5）

---

## 二、功能模块完成状态

### 2.1 核心 Agent 系统 ✅

| 功能 | 状态 | 说明 |
|------|------|------|
| ReAct 循环 | ✅ | 支持多轮工具调用 + 流式输出 |
| 消息 segments 架构 | ✅ | 文本段 + 工具段时间线嵌入气泡 |
| MAX_REACT_LOOPS | ✅ | 15 轮（原 5 轮太短） |
| WebSocket 通信 | ✅ | 实时双向通信 |
| 确认机制 | ✅ | 高风险操作需用户确认（request_id + 60s 超时） |

### 2.2 工具系统 ✅

| 工具 | 状态 | 说明 |
|------|------|------|
| `web_search` | ✅ | Bing/百度搜索 |
| `code_exec` | ✅ | Python/Shell 执行（asyncio.run_in_executor，120s 超时）+ base64 写入大文件 |
| `file_manager` | ✅ | 9 个 action + 安全校验 + 信任模式 + 审计日志 |
| `save_memory` | ✅ | 保存长期记忆（用户偏好/事实/指令） |

**file_manager 详情（9 个 action）：**
- `read` / `write`（overwrite/append）/ `list` / `search`（glob）/ `find_replace`
- `copy` / `move` / `delete` / `info`
- 路径安全：expanduser → abspath → realpath（校验用）/ 原始路径（操作用）
- 硬禁止路径：`/proc`, `/sys`, `/dev`, `~/.ssh` 等
- 敏感路径：主目录下 `.` 开头的隐藏文件
- 信任模式：设置页开关，开启后除系统核心文件外直接放行

### 2.3 人格/主题系统 ✅

| 功能 | 状态 | 说明 |
|------|------|------|
| 主题包架构 | ✅ | ThemePack = 角色 + 主题 + 素材 |
| 会话绑定主题包 | ✅ | 切换会话自动切换主题包 |
| 创建向导 | ✅ | 4 步：角色 → 主题 → 素材 → 完成 |
| 主题编辑器 | ✅ | 颜色/字体/间距三标签页 |
| 素材装饰 | ✅ | 9 个上传位 + 示意图 |
| 主题包导入/导出 | ✅ | zip 格式 |
| 一键更新关联会话 | ✅ | 修改主题包后批量更新 |

### 2.4 记忆系统 ✅

| 功能 | 状态 | 说明 |
|------|------|------|
| 长期记忆 | ✅ | 全局共享，不关联角色，Top-20 注入 |
| 自动提取 | ✅ | 规则过滤（关键词）+ LLM 批量提取，每 3 轮检查 |
| 分层摘要 | ✅ | Token 阈值触发 + 10 轮兜底，逐条注入，10 条后聚合为二级 |
| 记忆过期 | ✅ | 自动记忆 30 天过期，手动记忆永不过期 |
| 记忆去重 | ✅ | 字符串包含匹配 |
| 前端管理 | ✅ | 分类筛选 + 搜索 + 编辑/删除 + 手动添加 |

**上下文加载顺序：** system_prompt → 长期记忆 → 摘要（逐条）→ 近期原文（20 轮）

### 2.5 QQ 通道 ✅

| 功能 | 状态 | 说明 |
|------|------|------|
| WebSocket 模式 | ✅ | `wss://api.sgroup.qq.com/websocket`，无需公网地址 |
| C2C 私信 | ✅ | 好友私信收发 |
| 群@消息 | ✅ | 群聊中 @机器人 |
| Token 自动刷新 | ✅ | 7200s 过期，提前 5 分钟刷新 |
| 心跳保活 | ✅ | 定期发送心跳，断线自动重连 |
| 工具调用 | ✅ | QQ 消息支持使用 agent 工具 |

### 2.6 前端 UI

| 功能 | 状态 | 说明 |
|------|------|------|
| 聊天界面 | ✅ | segments 渲染 + 工具时间线 + 结果格式化 |
| 设置页 | ✅ | 8 个 tab：次元设置/主题包/模型配置/通道管理/插件/技能/工具/记忆 |
| 信任模式开关 | ✅ | 设置页工具 tab |
| 会话列表 | ✅ | 绑定主题包，切换自动切换 |
| 会话编辑 | ✅ | 重命名 + 更改主题包 |
| 确认对话框 | ✅ | file_manager 高风险操作确认 |

---

## 三、设计文档索引

| 文档 | 路径 |
|------|------|
| 主题包架构 | `docs/superpowers/specs/2026-07-14-themepack-architecture-design.md` |
| 主题包完善 | `docs/superpowers/specs/2026-07-14-persona-theme-asset-improvement-design.md` |
| UI 自定义增强 | `docs/superpowers/specs/2026-07-13-ui-customization-design.md` |
| file_manager 工具 | `docs/superpowers/specs/2026-07-15-file-manager-tool-design.md` |
| 消息 segments 架构 | `docs/superpowers/specs/2026-07-15-message-segments-design.md` |
| 记忆系统 | `docs/superpowers/specs/2026-07-16-memory-system-design.md` |

---

## 四、关键文件索引

### 后端

| 文件 | 说明 |
|------|------|
| `backend/main.py` | FastAPI 入口，路由注册 |
| `backend/config.py` | 配置（端口 8001，MAX_REACT_LOOPS=15） |
| `backend/agent/react.py` | ReActAgent（segment yield + tool_call_id） |
| `backend/agent/memory.py` | MemoryManager（长期记忆 + 分层摘要 + 自动提取） |
| `backend/api/chat.py` | WebSocket /ws/chat |
| `backend/api/qq_api.py` | QQ Bot WebSocket 通道 |
| `backend/api/config_api.py` | 配置 API + 记忆 API |
| `backend/api/themepack_api.py` | 主题包 CRUD + 导入导出 |
| `backend/api/session_api.py` | 会话管理（绑定 theme_pack_id） |
| `backend/db/database.py` | SQLite 数据库（conversations/memories/summaries/app_config/session_metadata） |
| `backend/adapters/qq_bot.py` | QQ Bot WebSocket 适配器 |
| `backend/tools/builtin/file_manager.py` | 文件管理工具（9 action + 安全） |
| `backend/tools/builtin/code_exec.py` | 代码执行工具（base64 支持） |
| `backend/tools/builtin/save_memory.py` | 记忆保存工具 |
| `backend/tools/builtin/web_search.py` | 搜索工具 |

### 前端

| 文件 | 说明 |
|------|------|
| `frontend/src/views/ChatView.vue` | 聊天主界面 |
| `frontend/src/views/SettingsView.vue` | 设置页（8 tab） |
| `frontend/src/components/ChatBubble.vue` | 消息气泡（segments 渲染 + 时间线） |
| `frontend/src/components/SessionList.vue` | 会话列表（绑定主题包） |
| `frontend/src/components/CreationWizard.vue` | 4 步创建向导 |
| `frontend/src/components/AssetUploader.vue` | 素材上传（9 位 + 示意图） |
| `frontend/src/stores/chat.js` | 聊天 store（appendSegment + 状态优先级） |

---

## 五、测试状态

- **后端测试：** 28 passed, 2 warnings
- **前端构建：** Vite build 成功

---

## 六、待做 / 未来规划

| 功能 | 优先级 | 说明 |
|------|--------|------|
| 文件操作单独重试 | 低 | file_manager 单工具重试（v3） |
| 知识库/RAG | 中 | 向量检索，导入文档 |
| 图片生成/理解 | 低 | 多模态能力 |
| 多用户系统 | 低 | 登录 + 数据隔离 |
| Electron 打包 | 低 | 桌面应用分发 |
| 插件系统完善 | 中 | 已有 loader，需实际插件 |
| 语音 TTS | 低 | 文字转语音 |
| 摘要精度优化 | 中 | 用 tokenizer 替代 len/2 估算 |
