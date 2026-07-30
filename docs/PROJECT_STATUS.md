# VerseNa — 项目进度总结

> 最后更新：2026-07-30
> 技术栈：FastAPI + Vue 3 + SQLite + WebSocket
> 定位：个人 AI Agent / 角色扮演聊天平台，支持桌面端、局域网访问和 Termux 部署

---

## 一、项目概述

VerseNa 是一个面向角色扮演、长期陪伴和个人自动化场景的 AI Agent 平台。核心卖点是可自定义的人设/主题包、完整的工具调用链路、长期记忆、语音能力、QQ 通道，以及可在 Windows 桌面端和 Android Termux 上运行的部署方式。

**运行环境：**
- 后端：FastAPI，端口 8002
- 前端：Vue 3 + Vite，端口 5173
- 数据库：SQLite（aiosqlite）
- 模型：OpenAI 兼容接口，支持多个供应商和自定义端点
- 桌面端：Electron，Windows 包内置 Python 运行时
- 局域网：访问令牌 + HttpOnly 会话 Cookie 保护 API、资源和 WebSocket

---

## 二、功能模块完成状态

### 2.1 核心 Agent 系统 ✅

| 功能 | 状态 | 说明 |
|------|------|------|
| ReAct 循环 | ✅ | 支持多轮工具调用 + 流式输出 |
| 消息 segments 架构 | ✅ | 文本段 + 工具段时间线嵌入气泡（状态优先级 + 组内排序） |
| LLM 调用重试 | ✅ | 失败最多重试 3 次，指数退避（1s/2s/4s） |
| MAX_REACT_LOOPS | ✅ | 15 轮（原 5 轮太短） |
| WebSocket 通信 | ✅ | 实时双向通信 |
| 确认机制 | ✅ | 高风险操作需用户确认（request_id + 60s 超时） |
| 运行监控 | ✅ | 设置页监控 tab，终端风格日志查看器，支持自动刷新 |

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
| 长期记忆 | ✅ | 全局共享，不关联角色，权重排序注入（instruction>fact>preference>general） |
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
| 异步消息处理 | ✅ | asyncio.create_task 不阻塞 WebSocket 事件循环 |

### 2.6 前端 UI

| 功能 | 状态 | 说明 |
|------|------|------|
| 聊天界面 | ✅ | segments 渲染 + 工具时间线 + 结果格式化 |
| 设置页 | ✅ | 11 个 tab；认证启用时提供访问安全与令牌轮换 |
| 信任模式开关 | ✅ | 设置页工具 tab |
| 会话列表 | ✅ | 绑定主题包，切换自动切换 |
| 会话编辑 | ✅ | 重命名 + 更改主题包 |
| 确认对话框 | ✅ | file_manager 高风险操作确认 |
| 运行监控面板 | ✅ | 深色终端风格日志查看器，自动刷新（3s），日志按级别着色 |

### 2.7 Skill 系统 ✅

| 功能 | 状态 | 说明 |
|------|------|------|
| Skill 发现 | ✅ | 加载内置、自定义和 GitHub 安装的 Skill |
| 按需加载 | ✅ | Agent 通过 `load_skill` 获取完整说明和知识文档 |
| 生命周期管理 | ✅ | 安装、更新、卸载、刷新和状态诊断 |
| 安全边界 | ✅ | ID/URL 校验、目录限制、原子更新，不执行仓库代码 |
| QQ 接入 | ✅ | QQ 通道可发现并调用 Skill |

### 2.8 局域网访问与认证 ✅

| 功能 | 状态 | 说明 |
|------|------|------|
| 单端口 Web 应用 | ✅ | FastAPI 托管生产前端、REST 和 WebSocket |
| 访问令牌 | ✅ | 首次 LAN 启动自动生成并打印，强令牌换取随机 HttpOnly 会话 Cookie |
| 令牌轮换 | ✅ | 登录后可在设置页修改；当前浏览器保持登录，其他会话立即失效 |
| API 与资源保护 | ✅ | REST、主题资源、下载和 OpenAPI 文档统一认证 |
| WebSocket 认证 | ✅ | 未授权连接使用 `4401` 关闭，不进入重连循环 |
| LAN 启动保护 | ✅ | 非回环监听未配置强令牌时自动生成并持久化 |
| Windows / Termux | ✅ | 提供启动脚本与 Android 精简依赖 |

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
| `backend/config.py` | 配置（端口 8002，MAX_REACT_LOOPS=15） |
| `backend/agent/react.py` | ReActAgent（segment yield + tool_call_id + LLM 重试） |
| `backend/agent/memory.py` | MemoryManager（长期记忆 + 分层摘要 + 自动提取） |
| `backend/api/chat.py` | WebSocket /ws/chat |
| `backend/api/qq_api.py` | QQ Bot WebSocket 通道 |
| `backend/api/config_api.py` | 配置 API + 记忆 API |
| `backend/api/log_api.py` | 运行日志 API（GET/DELETE /api/logs） |
| `backend/api/themepack_api.py` | 主题包 CRUD + 导入导出 |
| `backend/api/session_api.py` | 会话管理（绑定 theme_pack_id） |
| `backend/db/database.py` | SQLite 数据库（conversations/memories/summaries/app_config/session_metadata） |
| `backend/adapters/qq_bot.py` | QQ Bot WebSocket 适配器（token 自动刷新 + 重连） |
| `backend/tools/builtin/file_manager.py` | 文件管理工具（9 action + 安全） |
| `backend/tools/builtin/code_exec.py` | 代码执行工具（base64 支持） |
| `backend/tools/builtin/save_memory.py` | 记忆保存工具 |
| `backend/tools/builtin/web_search.py` | 搜索工具 |
| `backend/tools/builtin/load_skill.py` | 按需加载 Skill 内容 |
| `backend/skills/manager.py` | Skill 发现、安装、校验和诊断 |
| `backend/scripts/backup_user_data.py` | 一致性数据备份脚本 |

### 前端

| 文件 | 说明 |
|------|------|
| `frontend/src/views/ChatView.vue` | 聊天主界面 |
| `frontend/src/views/SettingsView.vue` | 设置页（11 tab，含访问安全与监控面板） |
| `frontend/src/components/ChatBubble.vue` | 消息气泡（segments 渲染 + 时间线） |
| `frontend/src/components/SessionList.vue` | 会话列表（绑定主题包） |
| `frontend/src/components/CreationWizard.vue` | 4 步创建向导 |
| `frontend/src/components/AssetUploader.vue` | 素材上传（9 位 + 示意图） |
| `frontend/src/stores/chat.js` | 聊天 store（appendSegment + 状态优先级） |

---

## 五、测试状态

- **后端测试：** 76 passed
- **前端构建：** Vite build 成功
- **测试退出：** pytest 正常退出，无残留数据库或 QQ 后台任务
- **安全边界：** 默认仅监听 `127.0.0.1`，CORS 限制为本地前端

---

## 六、待做 / 未来规划

| 功能 | 优先级 | 说明 |
|------|--------|------|
| Electron 独立运行时 | 中 | 对外分发时打包 Python 与后端依赖 |
| 知识库/RAG | 低 | 需要大型文档检索时再引入向量索引 |
| 摘要精度优化 | 低 | 用 tokenizer 替代 len/2 估算 |

**不做：** 多用户账户与权限体系（保持单一共享访问令牌）

---

## 七、开发日志

### 2026-07-29

- 发布 VerseNa 1.1 局域网访问模式。
- 增加访问令牌、HttpOnly 会话、登录限流和 WebSocket 认证。
- FastAPI 可直接托管 Vue 生产构建，局域网设备无需单独运行 Node.js。
- 增加 Windows 与 Termux 启动脚本，后端测试达到 76 项。
- LAN 首启自动生成并打印访问令牌，设置页支持安全轮换令牌并撤销其他会话。
- 完成界面、流式协议、停止反馈、QQ 通道和 TTS 文本清洗优化。
- 完成 Skill 系统发现、按需加载、安装、卸载、诊断与 QQ 接入。
- 后端收紧为本地监听和 CORS 白名单，补齐 QQ 与数据库生命周期清理。
- 新增一致性数据备份，后端测试达到 65 项并可正常退出。

### 2026-07-17（今日）

| 提交 | 内容 |
|------|------|
| `2f36972` | feat: 运行监控面板（设置页 + log_api + 日志查看器） |
| `9cceeea` | docs: 更新 PROJECT_STATUS（单用户定位 + LLM 重试 + 记忆权重） |
| `b680719` | feat: 记忆权重排序 + LLM 调用 3 次重试 |
| `01252a2` | fix: QQ Bot token 过期自动刷新 |
| `ddeaba7` | docs: 项目进度总结初版 |
| `f68e383` | fix: QQ Bot async task + C2C URL + 错误处理 |
| `e2abf1a` | feat: QQ Bot WebSocket 模式（无需公网） |
| `1b3dcc5` | fix: QQ Bot API 端点修正 |
| `c3f063f` | feat: 记忆系统（DB + MemoryManager + 自动提取 + 分层摘要） |
| `aa66541` | feat: 前端记忆管理 tab |
| `d2d0344` | fix: 确认对话框 + 信任模式 + 工具列表 |

### 2026-07-15 ~ 07-16

| 提交 | 内容 |
|------|------|
| `edd59ab` ~ `50305fb` | feat: 消息 segments 架构（react.py + store + ChatBubble） |
| `81eb9f5` | feat: file_manager 工具（9 action + 安全 + 信任模式） |
| `6a3107a` ~ `b0bed8d` | feat: 主题包架构（W0-W6，会话绑定主题包） |
| `be382cd` ~ `4805e33` | feat: UI 增强（V0-V4，创建向导 + 编辑器 + 素材装饰） |
