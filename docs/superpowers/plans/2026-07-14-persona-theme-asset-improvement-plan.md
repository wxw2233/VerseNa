# 次元人格 人格/主题/素材完善 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 完善人格/主题/素材三个功能的联动和交互体验。

**Architecture:** 创建向导替代简单弹窗，设置页三个区块清晰分隔，素材装饰用示意图标注位置。

**Tech Stack:** Python 3.11, FastAPI, Vue 3, Vite

## Global Constraints

- 所有项目文件在 `E:\Agent_design\`
- 后端 8001, 前端 5173
- 使用 npm
- 前端构建：`cd frontend && node node_modules/vite/bin/vite.js build`

---

## V0: 创建向导

### Task 1: 4步向导弹窗

**Files:**
- Create: `frontend/src/components/CreationWizard.vue`
- Modify: `frontend/src/components/SessionList.vue`

- [ ] 创建 CreationWizard 组件（4步：角色→主题→素材→完成）
- [ ] SessionList 的「+」按钮改为打开向导（替代当前的人格选择弹窗）
- [ ] 向导完成后自动创建会话并进入聊天
- [ ] 构建 + 提交

---

## V1: 设置页角色管理改造

### Task 2: 角色编辑表单优化

**Files:**
- Modify: `frontend/src/views/SettingsView.vue`

- [ ] 角色卡片点击切换 + ✓ 标记
- [ ] 编辑表单内联展开（点击卡片后在下方显示）
- [ ] 去掉「新建」按钮（新建走向导）
- [ ] 保存/重置/删除按钮
- [ ] 构建 + 提交

---

## V2: 主题编辑器增强

### Task 3: 颜色/字体/间距三标签页

**Files:**
- Modify: `frontend/src/components/ThemeCreator.vue` 或新建 `ThemeEditor.vue`
- Modify: `frontend/src/views/SettingsView.vue`

- [ ] 主题编辑器改为三个标签页（颜色/字体/间距）
- [ ] 颜色标签：8个颜色选择器
- [ ] 字体标签：字体族下拉 + 字号滑块 + 行高
- [ ] 间距标签：气泡圆角/内距/侧栏宽度/输入框圆角
- [ ] 每个参数修改实时预览 CSS 变量
- [ ] 构建 + 提交

---

## V3: 素材装饰区示意图

### Task 4: 界面预览示意图 + 9个素材位

**Files:**
- Modify: `frontend/src/components/AssetUploader.vue`
- Modify: `frontend/src/styles/default.css`

- [ ] 素材装饰区改为示意图 + 9个上传位
- [ ] 示意图用纯 CSS 模拟聊天界面布局
- [ ] 每个位置标注编号（①②③...）
- [ ] 点击标注自动滚动到对应上传行
- [ ] 9个素材位：bg, avatar, avatar-frame, bubble-user, bubble-agent, sidebar-bg, divider, input-bg, send-btn
- [ ] 构建 + 提交

---

## V4: 侧栏/输入框/发送按钮素材应用

### Task 5: 新素材位的 CSS 应用

**Files:**
- Modify: `frontend/src/components/SessionList.vue`
- Modify: `frontend/src/components/ChatInput.vue`
- Modify: `frontend/src/views/ChatView.vue`

- [ ] 侧栏背景图应用到 `.session-panel`
- [ ] 会话分隔线应用到 `.session-item`
- [ ] 输入框背景图应用到 `.input-bar`
- [ ] 发送按钮图标替换
- [ ] 构建 + 提交
