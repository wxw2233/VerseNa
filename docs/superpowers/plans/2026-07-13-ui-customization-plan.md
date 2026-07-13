# 次元人格 UI 自定义增强 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 增强主题系统，支持图片素材装饰和主题包导出/导入。

**Architecture:** 扩展现有 themes/ 结构，增加 assets/ 目录存放图片。后端新增图片上传/导出/导入 API。前端设置页增加素材装饰区。

**Tech Stack:** Python 3.11, FastAPI, Vue 3, Vite, zipfile (Python stdlib)

## Global Constraints

- 所有项目文件在 `E:\Agent_design\`
- 后端 8000, 前端 5173
- 图片无大小限制
- 使用 npm（不是 pnpm）
- 前端构建：`cd frontend && node node_modules/vite/bin/vite.js build`

---

## U0: CSS 变量扩展

### Task 1: 扩展 CSS 变量 + 组件适配

**Files:**
- Modify: `frontend/src/styles/default.css`
- Modify: `themes/default/variables.css`
- Modify: `themes/miku/variables.css`
- Modify: `frontend/src/components/ChatBubble.vue`
- Modify: `frontend/src/components/ChatInput.vue`

- [ ] 扩展 default.css 和所有 variables.css，新增 20 个变量
- [ ] ChatBubble 使用新变量（radius, shadow, border, padding）
- [ ] ChatInput 使用新变量（radius, bg）
- [ ] 构建 + 提交

---

## U1: 图片上传 API

### Task 2: 图片上传 + 素材存储

**Files:**
- Create: `backend/api/theme_asset_api.py`
- Modify: `backend/main.py`

- [ ] 创建图片上传 API：`POST /api/themes/{id}/upload`
- [ ] 创建图片获取 API：`GET /api/themes/{id}/assets/{filename}`
- [ ] 注册路由
- [ ] 测试 + 提交

---

## U2: 前端素材装饰区

### Task 3: 素材上传 UI + 实时预览

**Files:**
- Create: `frontend/src/components/AssetUploader.vue`
- Modify: `frontend/src/views/SettingsView.vue`

- [ ] 创建 AssetUploader 组件（5 个素材位置，每个有缩略图+上传按钮）
- [ ] 集成到设置页"次元设置" tab
- [ ] 上传后实时预览
- [ ] 构建 + 提交

---

## U3: ChatBubble 改造

### Task 4: 头像 + 头像框 + 气泡装饰

**Files:**
- Modify: `frontend/src/components/ChatBubble.vue`
- Modify: `frontend/src/styles/default.css`

- [ ] ChatBubble 增加头像显示（左 agent / 右用户）
- [ ] 头像框叠加层
- [ ] 气泡装饰（::after 伪元素）
- [ ] 背景图应用到 .chat-main
- [ ] 构建 + 提交

---

## U4: 主题包导出/导入

### Task 5: zip 导出/导入

**Files:**
- Create: `backend/api/theme_package_api.py`
- Modify: `frontend/src/views/SettingsView.vue`

- [ ] 导出 API：`GET /api/themes/{id}/export` → zip
- [ ] 导入 API：`POST /api/themes/import` → 解压
- [ ] 前端导出/导入按钮
- [ ] 构建 + 提交

---

## U5: 主题包附带人格

### Task 6: bundled_persona 自动导入

**Files:**
- Modify: `backend/api/theme_package_api.py`

- [ ] 导入时检查 bundled_persona
- [ ] 自动创建 persona 文件
- [ ] 测试 + 提交
