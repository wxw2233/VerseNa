# 次元人格 — UI 自定义增强设计

> 日期：2026-07-13
> 方案：B — CSS + 图片叠加层

---

## 1. 概述

在现有主题系统基础上，增加图片素材装饰层和主题包导出/导入功能。

用户可以：
- 上传图片作为聊天背景、头像、头像框、气泡装饰
- 调整 25+ CSS 变量（颜色、字体、间距、气泡样式）
- 导出完整主题包（zip）分享给他人
- 导入他人分享的主题包

---

## 2. 增强 CSS 变量系统

现有 6 个变量扩展到 25+：

```css
:root {
  /* 颜色（已有） */
  --primary: #7c5cfc;
  --bg-primary: #0f0f1a;
  --bg-secondary: #1a1a2e;
  --text-primary: #e8e8f0;
  --text-secondary: #8888aa;
  --border: #2a2a40;
  --bubble-user: rgba(124, 92, 252, 0.15);
  --bubble-agent: rgba(30, 30, 50, 0.9);

  /* 气泡（新增） */
  --bubble-radius: 12px;
  --bubble-shadow: none;
  --bubble-border: none;
  --bubble-padding: 10px 14px;

  /* 字体（新增） */
  --font-family: 'Noto Sans SC', sans-serif;
  --font-size-base: 14px;
  --font-size-small: 12px;
  --line-height: 1.6;

  /* 间距（新增） */
  --spacing-xs: 4px;
  --spacing-sm: 8px;
  --spacing-md: 16px;
  --spacing-lg: 24px;

  /* 侧栏（新增） */
  --sidebar-width: 220px;
  --sidebar-bg: var(--bg-secondary);

  /* 输入框（新增） */
  --input-radius: 8px;
  --input-bg: var(--bg-primary);
}
```

所有组件使用这些变量，用户改一个值全局生效。

---

## 3. 图片素材系统

### 3.1 主题目录结构

```
themes/miku/
├── theme.json
├── variables.css
└── assets/
    ├── bg.png          # 聊天背景图
    ├── avatar.png      # 角色头像
    ├── avatar-frame.png # 头像框装饰
    ├── bubble-user.png # 用户气泡装饰
    └── bubble-agent.png # Agent 气泡装饰
```

### 3.2 theme.json 扩展

```json
{
  "name": "初音ミク",
  "colors": { "primary": "#39C5BB", ... },
  "assets": {
    "background": {
      "image": "assets/bg.png",
      "size": "cover",
      "position": "center",
      "opacity": 0.3,
      "repeat": "no-repeat"
    },
    "avatar": {
      "image": "assets/avatar.png",
      "frame": "assets/avatar-frame.png",
      "size": 40,
      "shape": "circle"
    },
    "bubble_user_decoration": {
      "image": "assets/bubble-user.png",
      "position": "top-right",
      "size": 24,
      "opacity": 0.8
    },
    "bubble_agent_decoration": {
      "image": "assets/bubble-agent.png",
      "position": "bottom-left",
      "size": 24,
      "opacity": 0.8
    }
  }
}
```

### 3.3 CSS 实现

- 背景图：`.chat-main { background-image: url(...); opacity/size 由配置控制 }`
- 头像：`<img>` 标签 + 头像框用 CSS 叠加层
- 气泡装饰：`::after` 伪元素 + `background-image`

### 3.4 图片上传 API

- `POST /api/themes/{id}/upload` — multipart 上传图片到 `assets/`
- `GET /api/themes/{id}/assets/{filename}` — 获取图片

---

## 4. 主题包导出/导入

### 4.1 导出格式

zip 文件：

```
miku-theme.zip
├── theme.json        # 完整配置
├── variables.css     # CSS 变量
└── assets/           # 图片素材
    ├── bg.png
    ├── avatar.png
    └── ...
```

### 4.2 主题包可附带人格

```json
{
  "name": "初音ミク",
  "colors": { ... },
  "assets": { ... },
  "bundled_persona": {
    "id": "miku",
    "name": "初音ミク",
    "prompt": "你是...",
    "emotion_weights": { ... },
    "speech_style": { ... }
  }
}
```

导入时如果 `bundled_persona` 存在，自动创建对应 persona。

### 4.3 API

- `GET /api/themes/{id}/export` → 返回 zip 文件流
- `POST /api/themes/import` → multipart 上传 zip → 解压到 `themes/` → 自动注册

---

## 5. 前端 UI 改造

### 5.1 设置页"次元设置" tab

三个区域：

```
┌─────────────────────────────────────┐
│  🎭 角色管理                         │
│  [角色卡片列表] [+ 新建]              │
│  [内联编辑器]                        │
├─────────────────────────────────────┤
│  🎨 主题管理                         │
│  [主题卡片列表] [导入] [新建]          │
│  [内联编辑器：颜色+字体+间距滑块]      │
├─────────────────────────────────────┤
│  🖼️ 素材装饰                         │
│  [背景图] [头像/头像框] [气泡装饰]     │
│  [上传按钮] [预览区]                  │
│  [导出主题包] [导入主题包]             │
└─────────────────────────────────────┘
```

### 5.2 素材装饰区

每个素材位置显示当前图片缩略图（或占位符），点击弹出文件选择器上传。上传后实时预览。

| 素材 | 操作 | 预览 |
|------|------|------|
| 聊天背景图 | 上传/删除 | 缩略图 + 不透明度滑块 |
| 角色头像 | 上传/删除 | 圆形缩略图 |
| 头像框 | 上传/删除 | 叠加预览 |
| 用户气泡装饰 | 上传/删除 | 缩略图 |
| Agent 气泡装饰 | 上传/删除 | 缩略图 |

### 5.3 ChatBubble 改造

增加：
- 头像显示（左侧 agent 头像，右侧用户头像）
- 头像框叠加层
- 气泡装饰（`::after` 伪元素）

### 5.4 背景图应用

`.chat-main` 的 `background-image` 由当前主题的 `assets.background` 配置控制。

---

## 6. 开发阶段

| 阶段 | 内容 | 里程碑 |
|------|------|--------|
| U0 | CSS 变量扩展 + 组件适配 | 参数可调 |
| U1 | 图片上传 API + 素材存储 | 图片可上传 |
| U2 | 前端素材装饰区 + 实时预览 | 可视化编辑 |
| U3 | ChatBubble 改造（头像+装饰） | 聊天界面美化 |
| U4 | 主题包导出/导入（zip） | 可分享 |
| U5 | 主题包附带人格 + 一键导入 | 主题+角色打包 |
