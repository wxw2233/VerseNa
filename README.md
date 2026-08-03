# VerseNa — AI 角色扮演聊天平台

> 一个支持多模型、多角色、多主题的 AI 聊天桌面应用。

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-blue?logo=python" />
  <img src="https://img.shields.io/badge/Vue-3.4-green?logo=vuedotjs" />
  <img src="https://img.shields.io/badge/FastAPI-0.115-teal?logo=fastapi" />
  <img src="https://img.shields.io/badge/License-CC--BY--NC--4.0-orange" />
</p>

---

## ✨ 功能特性

- 🎭 **主题包系统** — 角色人设 + 主题配色 + 素材管理，一键切换
- 🤖 **多模型支持** — DeepSeek / OpenAI / SiliconFlow / 智谱AI / 通义千问 / Moonshot / 自定义
- 🧠 **深度思考** — 独立推理模型、低/中/高强度、流式思考折叠展示
- 🎤 **语音合成** — 支持 MiMo 音色克隆、OpenAI TTS、ElevenLabs
- 🎙️ **语音输入** — 浏览器原生 Web Speech API
- 👁️ **图片理解** — 上传图片，视觉模型识别内容
- 📎 **文件附件** — 图片/文档/代码文件上传
- 🔧 **工具调用** — 联网搜索 / 代码执行 / 文件管理 / 长期记忆
- 🧩 **Skill 系统** — 内置 / 自定义 / GitHub 安装，按需加载技能说明和知识文档
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

- Python 3.10+
- Node.js 18+
- npm 或 pnpm

### 安装

```bash
# 克隆项目
git clone https://github.com/wxw2233/VerseNa.git
cd VerseNa

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

后端默认只监听 `127.0.0.1:8002`。生产构建完成后也可直接访问 `http://127.0.0.1:8002`，由 FastAPI 托管前端。

局域网模式使用访问令牌保护 REST、资源文件和 WebSocket：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start-lan.ps1
```

Windows、Termux 和安全注意事项见 [局域网访问文档](docs/LAN_ACCESS.md)。打包发布流程见 [打包文档](docs/PACKAGING.md)。
主力工具的工作区、确认规则和联网边界见 [工具安全文档](docs/TOOLS.md)。

Termux 使用源码部署：

```bash
git clone https://github.com/wxw2233/VerseNa.git
cd VerseNa
bash scripts/setup-termux.sh
bash scripts/start-termux.sh
```

首次 LAN 启动会在终端面板打印并持久化随机访问令牌；登录后可在 **设置 → 访问安全** 中生成或修改令牌。

### 源码更新

通过 `git clone` 部署的版本可在 **设置 → 源码更新** 中检查并安装上游更新。更新器仅允许安全的快进更新；存在未提交的源码修改或分叉提交时会拒绝执行。完成更新后重启 VerseNa 即可生效。

Windows 安装包和旧 Termux 压缩包不使用该更新通道。已有源码部署需要先手动拉取一次包含更新器的版本，详细说明见 [源码更新文档](docs/SOURCE_UPDATES.md)。

### 配置模型

1. 打开 **设置 → 模型配置**
2. 选择提供商（如 DeepSeek），填入 API Key
3. 点击 **测试连接**，选择模型
4. 在 **角色分配** 中设置对话/推理/图片识别/TTS 模型

## 📁 项目结构

```
├── backend/              # Python 后端
│   ├── api/              # API 路由
│   ├── agent/            # ReAct Agent 核心
│   ├── tts/              # TTS 语音合成
│   ├── tools/            # 内置工具
│   ├── skills/           # Skill 管理与内容
│   ├── scripts/          # 维护脚本
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

## ✅ 测试

```bash
cd backend
python -m pytest -q

cd ../frontend
npm run build
```

## 💾 数据备份

```bash
python backend/scripts/backup_user_data.py
```

备份默认保存在 `backups/`，详细恢复步骤见 [docs/BACKUP.md](docs/BACKUP.md)。备份包含私人对话和 API Key，请妥善保管。

## 🤝 贡献

欢迎提交 PR！请确保：
- 代码风格与现有代码一致
- 不提交个人配置或 API Key
- 新功能请附带简要说明

## 📄 许可证

本项目的源代码、文档、人设、音频、图片及其他原创内容统一采用 **知识共享署名 - 非商业性使用 4.0 国际许可协议（CC BY-NC 4.0）**。

您可以在保留署名和许可证说明的前提下复制、修改和分发，但**禁止将本项目或二次衍生程序用于商业售卖、付费服务、广告变现、商业托管等盈利场景**。商业使用必须事先取得版权所有者的书面许可。

禁止商用的授权不属于 OSI 定义的开源软件许可证；VerseNa 属于**源码可用的非商业项目**。第三方依赖继续适用各自原有许可证。

完整授权说明见根目录 [LICENSE](LICENSE) 文件。

欢迎提交 PR 共建项目！
