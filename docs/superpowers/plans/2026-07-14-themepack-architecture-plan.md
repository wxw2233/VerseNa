# 主题包架构重构 — 实现计划

**Goal:** 以主题包为核心重构架构，会话绑定主题包。

## W0: 后端 ThemePack 模型 + CRUD API

### Task 1

**Files:**
- Create: `backend/themepacks/__init__.py`
- Create: `backend/themepacks/manager.py`
- Create: `backend/api/themepack_api.py`
- Modify: `backend/main.py`

- [ ] ThemePackManager：加载/保存/创建/删除主题包
- [ ] CRUD API：GET/POST/PUT/DELETE /api/themepacks
- [ ] 导出/导入 API：GET export, POST import
- [ ] 一键更新 API：POST /api/themepacks/{id}/apply
- [ ] 测试 + 提交

## W1: 后端会话扩展

### Task 2

**Files:**
- Modify: `backend/db/database.py`
- Modify: `backend/api/session_api.py`

- [ ] 会话元数据表（session_id, name, theme_pack_id）
- [ ] GET /api/sessions 返回 theme_pack_id
- [ ] PUT /api/sessions/{id} 可修改 name 和 theme_pack_id
- [ ] 测试 + 提交

## W2: 前端次元设置改造

### Task 3

**Files:**
- Modify: `frontend/src/views/SettingsView.vue`

- [ ] 次元设置 tab 改为「+ 新建主题包」+ 主题包列表
- [ ] 点击主题包卡片展开编辑器（角色+主题+素材）
- [ ] 编辑器使用现有的表单组件
- [ ] 构建 + 提交

## W3: 前端主题包 tab 改造

### Task 4

**Files:**
- Modify: `frontend/src/views/SettingsView.vue`

- [ ] 主题包 tab：列表+导出/删除/更新
- [ ] 导入按钮
- [ ] 构建 + 提交

## W4: 新建会话改为选主题包

### Task 5

**Files:**
- Modify: `frontend/src/components/SessionList.vue`

- [ ] 新建会话弹窗改为选择主题包
- [ ] 选好后创建会话并绑定 theme_pack_id
- [ ] 构建 + 提交

## W5: 会话编辑

### Task 6

**Files:**
- Modify: `frontend/src/components/SessionList.vue`

- [ ] 会话 hover 显示编辑按钮
- [ ] 编辑弹窗：重命名 + 更改主题包
- [ ] 构建 + 提交

## W6: 切换会话自动切换主题包

### Task 7

**Files:**
- Modify: `frontend/src/components/SessionList.vue`
- Modify: `frontend/src/views/ChatView.vue`

- [ ] 切换会话时加载 theme_pack_id
- [ ] 自动应用对应的 persona + theme + assets
- [ ] 构建 + 提交
