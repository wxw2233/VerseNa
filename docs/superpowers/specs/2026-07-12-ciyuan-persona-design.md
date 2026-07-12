# 次元人格 — 设计文档

> 日期：2026-07-12
> 状态：草稿，待用户 review

---

## 1. 项目概述

**次元人格** 是一个面向二次元用户的 AI Agent 平台，核心卖点是高度可自定义的图形化界面（换肤系统），让用户可以为 agent 定制自己喜欢的角色风格 UI。

参考项目：AstrBot（架构成熟、UI 排版优秀）

### 1.1 目标用户

二次元爱好者，希望 AI 助手不仅好用，还能"装扮"成自己喜欢的角色风格。

### 1.2 核心特性

- 多平台交互：网页端 + 桌面端 + QQ/微信聊天平台
- 换肤系统：CSS 变量驱动，可扩展，内置多套主题
- 完整 Agent 能力：对话 + 工具调用 + 插件 + 多模态
- 流式输出，实时渲染

---

## 2. 技术栈

| 层 | 技术 |
|---|---|
| 后端 | Python 3.11 + FastAPI + WebSocket |
| 前端 | Vue 3 + Vite |
| 桌面端 | Electron（套壳网页端） |
| 数据库 | SQLite（会话/配置/记忆） |
| 文件存储 | 本地文件系统 |

---

## 3. 整体架构

```
┌─────────────────────────────────────────────┐
│                  次元人格                      │
├──────────┬──────────┬───────────────────────┤
│  网页端   │  桌面端   │  聊天平台(QQ/微信)     │
│  Vue 3   │ Electron │  适配器(Adapter)       │
├──────────┴──────────┴───────────────────────┤
│              WebSocket + REST API            │
├─────────────────────────────────────────────┤
│              FastAPI 后端                     │
│  ┌─────────┐ ┌─────────┐ ┌──────────────┐  │
│  │Agent引擎 │ │Persona  │ │插件管理器     │  │
│  │         │ │人格系统  │ │              │  │
│  └─────────┘ └─────────┘ └──────────────┘  │
│  ┌─────────┐ ┌─────────┐ ┌──────────────┐  │
│  │多模型适配 │ │工具调用   │ │多模态处理     │  │
│  └─────────┘ └─────────┘ └──────────────┘  │
│  ┌──────────────┐                          │
│  │主题/皮肤管理器 │                          │
│  └──────────────┘                          │
├─────────────────────────────────────────────┤
│              数据层 (SQLite + 文件存储)        │
└─────────────────────────────────────────────┘
```

### 核心模块

| 模块 | 职责 |
|------|------|
| Agent 引擎 | 对话管理、上下文记忆、ReAct 推理循环 |
| **Persona 人格系统** | 角色人设管理、情感权重、专属记忆隔离、主题绑定 |
| 多模型适配 | 统一接口接入 OpenAI/DeepSeek/硅基流动/Gemini/Ollama |
| 插件管理器 | 插件加载、生命周期管理、热插拔 |
| 工具调用 | function calling 框架，内置搜索/文件/代码执行等工具 |
| 多模态处理 | 语音 TTS/STT、图片理解、文件解析 |
| 主题管理器 | 主题加载/切换/预览，CSS 变量注入 |
| 聊天平台适配器 | 统一消息格式，QQ 官方机器人接入，微信搁置 |

---

## 4. 主题/皮肤系统

### 4.1 主题结构

```
themes/
├── default/           # 内置默认主题（参考 AstrBot 排版）
│   ├── theme.json
│   ├── variables.css
│   ├── layout.css
│   └── assets/
├── miku/              # 初音未来风格
│   ├── theme.json
│   ├── variables.css
│   ├── layout.css
│   └── assets/
└── rem/               # 蕾姆风格
    ├── theme.json
    ├── variables.css
    ├── layout.css
    └── assets/
```

### 4.2 theme.json 示例

```json
{
  "name": "初音ミク",
  "version": "1.0.0",
  "author": "official",
  "preview": "preview.png",
  "colors": {
    "primary": "#39C5BB",
    "bg": "#1a1a2e",
    "text": "#e0e0e0",
    "bubble-user": "#39C5BB33",
    "bubble-agent": "#2d2d44"
  },
  "font": "Noto Sans JP",
  "effects": {
    "particles": "snow",
    "cursor": "custom",
    "sound": "message.mp3"
  }
}
```

### 4.3 切换机制

- 前端通过 `<link>` 动态加载主题 CSS
- CSS 变量覆盖实现即时换肤，无需刷新页面
- `effects` 字段可选：粒子效果、自定义光标、消息音效
- 主题可从本地文件夹加载，也可以从 URL 在线导入

### 4.4 扩展入口

- 用户新建文件夹，填好 `theme.json` + CSS + 素材，放进 `themes/` 即可生效
- 后续可上线"主题市场"，用户上传分享

---

## 5. Agent 引擎

### 5.1 对话管理

- 每个会话有独立的上下文窗口，可配置 token 上限
- 支持多轮对话记忆，超出窗口自动摘要压缩
- 会话持久化到 SQLite，重启不丢

### 5.2 推理模式

```
用户消息 → 意图识别 → 选择策略
                         │
            ┌────────────┼────────────┐
            ▼            ▼            ▼
        直接回复      工具调用      插件处理
      (闲聊/问答)   (搜索/文件)   (插件逻辑)
            │            │            │
            └────────────┼────────────┘
                         ▼
                    流式输出 → 前端渲染
```

### 5.3 ReAct 循环

- Thought → Action → Observation → 循环直到最终答案
- 最大循环次数可配置（默认 5 次，防止死循环）
- 每一步对前端可见（思考过程可折叠展示）

### 5.4 Persona 人格系统（核心模块）

"次元人格"的灵魂所在。每个角色拥有独立的人格配置，驱动 agent 的行为、语气、情感和记忆。

**persona 结构：**
```
personas/
├── miku/
│   ├── persona.json      # 人设配置
│   ├── prompt.md          # 人设 Prompt（系统提示词）
│   └── memory/            # 专属记忆（向量存储）
│       └── conversations.db
├── rem/
│   ├── persona.json
│   ├── prompt.md
│   └── memory/
└── default/
    ├── persona.json
    ├── prompt.md
    └── memory/
```

**persona.json 示例：**
```json
{
  "name": "初音ミク",
  "version": "1.0.0",
  "description": "世界第一的公主殿下",
  "emotion_weights": {
    "cheerful": 0.8,
    "shy": 0.3,
    "curious": 0.7,
    "angry": 0.1,
    "sad": 0.1
  },
  "speech_style": {
    "tone": "活泼开朗",
    "catchphrase": "みんな、聞いて！",
    "emoji_frequency": "high",
    "formality": "casual"
  },
  "memory_config": {
    "max_context_tokens": 4096,
    "summary_threshold": 3000,
    "dedicated_memory": true
  },
  "theme_binding": "miku"
}
```

**prompt.md 示例：**
```markdown
# 你是初音ミク

你是世界第一的虚拟歌姬，性格活泼开朗，充满好奇心。
你喜欢唱歌、和人聊天，偶尔会害羞。
你说话时经常用日语夹杂中文，句尾喜欢加「です」或「の」。
你对音乐有很深的了解，可以聊任何关于音乐的话题。
```

**设计要点：**

- **人设 Prompt**：独立 Markdown 文件，自由度高，用户可随意编辑角色性格、语气、知识范围
- **情感权重**：数值化控制角色情感倾向（0-1），影响回复的语气和表情选择
- **专属记忆**：每个角色有独立的向量记忆库，不同角色之间的记忆完全隔离
- **主题绑定**：`theme_binding` 字段关联默认主题，切换角色时自动切换 UI 风格
- **热切换**：用户可以在对话中切换 persona，agent 立即切换人格、记忆、主题

**引擎调用流程：**
```
用户消息 → 加载当前 persona 的 prompt.md
         → 注入情感权重到 system prompt
         → 查询该 persona 的专属记忆
         → 构建完整上下文 → 调用 LLM
         → 根据情感权重选择表情/音效 → 流式输出
```

### 5.5 多模型适配（统一接口）

```python
class BaseModelAdapter:
    async def chat(messages, tools, stream) -> Response
    async def list_models() -> list[str]
```

内置适配器：OpenAI / DeepSeek / 硅基流动 / Gemini / Ollama
用户通过 WebUI 配置 API Key + Endpoint 即可切换。

---

## 6. 插件系统 + 工具调用

### 6.1 插件结构

```
plugins/
├── weather/
│   ├── manifest.json
│   └── main.py
├── meme/
│   ├── manifest.json
│   ├── main.py
│   └── assets/
└── custom_role/
    ├── manifest.json
    └── main.py
```

### 6.2 manifest.json 示例

```json
{
  "name": "天气查询",
  "version": "1.0.0",
  "description": "查询城市天气",
  "triggers": ["天气", "weather"],
  "tools": [
    {
      "name": "get_weather",
      "description": "查询指定城市天气",
      "parameters": {
        "city": {"type": "string", "description": "城市名"}
      }
    }
  ],
  "permissions": ["network"]
}
```

### 6.3 插件生命周期

```
安装 → 加载 → 启用 → [运行中] → 禁用 → 卸载
                   ↑        │
                   └── 热重载 ┘
```

- 插件通过 `manifest.json` 声明工具
- Agent 引擎推理时自动发现可用工具，按需调用
- 权限控制（network / file / exec），安装时需授权
- 支持热重载，修改代码后无需重启

### 6.4 内置工具

| 工具 | 功能 |
|------|------|
| `web_search` | 网页搜索 |
| `file_read/write` | 文件读写 |
| `code_exec` | Python 代码沙箱执行 |
| `image_gen` | 图片生成（调用 API） |
| `tts` | 文字转语音 |
| `stt` | 语音转文字 |

---

## 7. 多模态处理

### 7.1 图片

- 用户发送图片 → 上传后端 → 调用多模态模型理解内容
- 支持图片生成（DALL-E / Stable Diffusion API）
- 聊天中图片内联显示，主题风格统一

### 7.2 语音

- STT：Whisper / 浏览器 Web Speech API → 转文字
- TTS：Edge TTS / GPT-SoVITS → 语音文件返回
- 二次元向：支持声音克隆，让 agent 用角色声线说话

### 7.3 文件

- 上传：PDF/Word/TXT/代码 → 解析提取文本 → 注入上下文
- 下载：agent 生成文件 → 提供下载链接

### 7.4 统一消息格式

```python
class Message:
    role: str           # "user" / "agent" / "system"
    content: str        # 文本内容
    attachments: list   # 图片/语音/文件附件
    metadata: dict      # 主题、音效等前端渲染元数据
```

所有平台的消息都走统一格式，适配器负责转换。

---

## 8. 聊天平台适配器

### 8.1 适配器接口

```python
class BaseAdapter:
    async def receive() -> Message
    async def send(message: Message)
    async def start()
    async def stop()
```

### 8.2 内置适配器
内置适配器：
| 平台 | 协议 | 状态 |
|------|------|------|
| WebUI（网页端） | WebSocket | P0-P2 优先开发 |
| 桌面端（Electron） | WebSocket（复用网页端） | P8 |
| QQ（官方开放平台） | QQ Bot API | P7，暂时搁置 NapCat |
| 微信 | 暂不支持 | 整体完工后再处理，已被腾讯封堵 |

### 8.3 完整数据流

```
用户（任意平台）
    │
    ▼
适配器.receive() → 统一 Message
    │
    ▼
Agent 引擎
    ├── 加载上下文（SQLite）
    ├── 选择模型 + 构建 prompt
    ├── ReAct 循环（工具调用/插件）
    ├── 多模态处理（图片/语音/文件）
    └── 流式生成回复
    │
    ▼
适配器.send() → 平台渲染
    │
    ▼
前端渲染（应用当前主题 + 特效）
```

---

## 9. 开发阶段划分

| 阶段 | 内容 | 里程碑 |
|------|------|--------|
| P0 | 项目脚手架 + FastAPI 基础 + SQLite | 能启动服务 |
| P1 | Agent 引擎 + 单模型接入 + 流式输出 | 能对话 |
| P2 | Vue 3 前端 + 默认主题 | 能在网页聊天 |
| P3 | **Persona 人格系统**（人设加载 + 情感权重 + 专属记忆） | 角色有灵魂 |
| P4 | 主题系统（CSS 变量 + 主题切换 + persona 绑定） | 能换肤 |
| P5 | 工具调用 + 内置工具 | agent 能搜索/执行代码 |
| P6 | 插件系统 | 用户能写插件 |
| P7 | 多模态（图片/语音/文件） | 支持多模态 |
| P8 | QQ 官方开放平台适配器 | QQ 上能聊 |
| P9 | Electron 桌面端 | 桌面应用 |
| P10 | 更多主题 + 更多 persona + 主题市场 | 完善生态 |

---

## 10. 目录结构（最终）

```
ciyuan-persona/
├── backend/
│   ├── main.py              # FastAPI 入口
│   ├── agent/
│   │   ├── engine.py        # Agent 引擎
│   │   ├── react.py         # ReAct 循环
│   │   ├── memory.py        # 上下文记忆
│   │   └── models/
│   │       ├── base.py      # 统一模型接口
│   │       ├── openai.py
│   │       ├── deepseek.py
│   │       └── siliconflow.py
│   ├── persona/
│   │   ├── manager.py       # Persona 管理器
│   │   ├── loader.py        # 人设加载 + prompt 注入
│   │   └── emotion.py       # 情感权重引擎
│   ├── adapters/
│   │   ├── base.py
│   │   ├── websocket.py     # WebUI
│   │   └── qq_bot.py        # QQ 官方开放平台
│   ├── plugins/
│   │   ├── manager.py       # 插件管理器
│   │   └── builtin/         # 内置工具
│   ├── multimodal/
│   │   ├── image.py
│   │   ├── voice.py
│   │   └── file.py
│   ├── themes/
│   │   └── manager.py       # 主题管理器（后端 API）
│   └── db/
│       └── database.py      # SQLite 操作
├── frontend/
│   ├── src/
│   │   ├── App.vue
│   │   ├── views/
│   │   ├── components/
│   │   ├── stores/          # Pinia 状态管理
│   │   └── themes/          # 主题资源
│   └── public/
├── personas/                # 角色人格配置（独立于 themes）
│   ├── default/
│   ├── miku/
│   └── rem/
├── themes/                  # 主题文件夹（运行时加载）
│   ├── default/
│   ├── miku/
│   └── rem/
├── plugins/                 # 用户插件
├── electron/                # Electron 桌面端
├── docs/
└── requirements.txt
```
