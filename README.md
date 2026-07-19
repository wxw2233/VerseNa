# 次元人格 — AI 角色扮演聊天平台

> 一个支持多模型、多角色、多主题的 AI 聊天桌面应用。

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.8+-blue?logo=python" />
  <img src="https://img.shields.io/badge/Vue-3.4-green?logo=vuedotjs" />
  <img src="https://img.shields.io/badge/FastAPI-0.110+-teal?logo=fastapi" />
  <img src="https://img.shields.io/badge/License-CC--BY--NC--4.0-orange" />
</p>

---

## ✨ 功能特性

- 🎭 **主题包系统** — 角色人设 + 主题配色 + 素材管理，一键切换
- 🤖 **多模型支持** — DeepSeek / OpenAI / SiliconFlow / 智谱AI / 通义千问 / Moonshot / 自定义
- 🎤 **语音合成** — 支持 MiMo 音色克隆、OpenAI TTS、ElevenLabs
- 🎙️ **语音输入** — 浏览器原生 Web Speech API
- 👁️ **图片理解** — 上传图片，视觉模型识别内容
- 📎 **文件附件** — 图片/文档/代码文件上传
- 🔧 **工具调用** — 联网搜索 / 代码执行 / 文件管理 / 长期记忆
- 🧠 **记忆系统** — 自动提取 + 手动管理，支持分类和搜索
- 📡 **QQ 机器人** — WebSocket 模式，支持私聊和群聊
- 🎨 **主题定制** — 4 色配置 + 背景图 + 自适应亮度

## 📦 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | Vue 3 + Vite + Pinia + vue-router |
| 后端 | Python FastAPI + aiosqlite |
| 实时通信 | WebSocket |
| 数据库 | SQLite |
| 桌面端 | Electron（可选） |

## 🚀 快速开始

### 环境要求

- Python 3.8+
- Node.js 18+
- npm 或 pnpm

### 安装

```bash
# 克隆项目
git clone https://github.com/wxw2233/ciyuan-persona.git
cd ciyuan-persona

# 安装后端依赖
cd backend
pip install -r requirements.txt
cd ..

# 安装前端依赖
cd frontend
npm install
cd ..
```

### 启动

```bash
# 启动后端（终端 1）
cd backend
python main.py

# 启动前端（终端 2）
cd frontend
npm run dev
```

浏览器访问 `http://localhost:5173`

### 配置模型

1. 打开 **设置 → 模型配置**
2. 选择提供商（如 DeepSeek），填入 API Key
3. 点击 **测试连接**，选择模型
4. 在 **角色分配** 中设置对话/图片识别/TTS 模型

## 📁 项目结构

```
├── backend/              # Python 后端
│   ├── api/              # API 路由
│   ├── agent/            # ReAct Agent 核心
│   ├── tts/              # TTS 语音合成
│   ├── tools/            # 内置工具
│   ├── persona/          # 角色系统
│   └── db/               # 数据库
├── frontend/             # Vue 3 前端
│   ├── src/
│   │   ├── views/        # 页面
│   │   ├── components/   # 组件
│   │   ├── stores/       # Pinia 状态
│   │   └── composables/  # 组合式函数
│   └── dist/             # 构建输出
├── themepacks/           # 主题包数据
├── themes/               # 主题资源
└── personas/             # 角色配置
```

## 🎨 主题包

每个主题包包含：
- `theme.json` — 角色人设 + 主题配色
- `variables.css` — CSS 变量
- `assets/` — 图标/背景/参考音频

支持导入/导出 ZIP 格式。

## 🤝 贡献

欢迎提交 PR！请确保：
- 代码风格与现有代码一致
- 不提交个人配置或 API Key
- 新功能请附带简要说明

## 📄 许可证

本项目源代码采用 **MIT 开源协议**，配套人设、音频、图文素材采用 **知识共享署名 - 非商业性使用 4.0 国际许可协议（CC BY-NC 4.0）**。

**1. 源代码规则：** 您可自由复制、修改、分发代码，分发时必须保留原作者版权声明；**禁止将本项目或二次衍生程序用于任何商业售卖、付费服务、广告变现等盈利场景**。

**2. 素材文件规则：** 所有角色文案、音频、图片素材仅允许非商业使用，二次修改 / 分发必须完整保留作者署名，严禁商用牟利。

完整许可条款分别查阅根目录 [LICENSE-MIT](LICENSE-MIT)、[LICENSE-CC](LICENSE-CC) 文件。

欢迎提交 PR 共建项目！
