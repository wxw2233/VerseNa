# 次元人格 — 主题包架构重构设计

> 日期：2026-07-14

## 1. 核心理念

**主题包 = 角色 + 主题 + 素材**，是最高级别的抽象单元。
会话绑定主题包，切换会话自动切换主题包。

## 2. 数据模型

### 2.1 ThemePack（主题包）

存储位置：`themepacks/{id}/`

```
themepacks/miku_pack/
├── pack.json          # 主题包配置
├── persona.json       # 角色配置
├── prompt.md          # 角色人设
├── theme.json         # 主题配置
├── variables.css      # CSS 变量
└── assets/            # 素材
    ├── bg.png
    ├── avatar.png
    └── ...
```

pack.json：
```json
{
  "id": "miku_pack",
  "name": "初音ミク完整包",
  "persona_ref": "miku",
  "theme_ref": "miku",
  "created_at": "2026-07-14T22:00:00"
}
```

### 2.2 Session（会话）

扩展现有的 conversations 表，新增 theme_pack_id 字段：

```sql
ALTER TABLE conversations ADD COLUMN theme_pack_id TEXT DEFAULT 'default_pack'
```

或者在 session 元数据中存储（用 app_config 表）。

### 2.3 关联关系

```
ThemePack 1──N Session
  ├── persona（角色）
  ├── theme（主题）
  └── assets（素材）
```

## 3. 后端 API

### 3.1 主题包 CRUD

- `GET /api/themepacks` — 列表
- `GET /api/themepacks/{id}` — 详情
- `POST /api/themepacks` — 创建
- `PUT /api/themepacks/{id}` — 更新
- `DELETE /api/themepacks/{id}` — 删除
- `POST /api/themepacks/{id}/apply` — 一键更新所有关联会话
- `GET /api/themepacks/{id}/export` — 导出 zip
- `POST /api/themepacks/import` — 导入 zip

### 3.2 会话扩展

- `GET /api/sessions` — 返回结果包含 theme_pack_id
- `PUT /api/sessions/{id}` — 可修改 name 和 theme_pack_id

## 4. 前端改造

### 4.1 次元设置 tab

改为只有一个「+ 新建主题包」按钮，点击后进入创建流程（角色→主题→素材）。
下方显示主题包列表，每个主题包卡片显示名称和包含的角色/主题。
点击卡片展开编辑器（角色编辑+主题编辑+素材上传）。

### 4.2 主题包 tab

- 主题包列表（只显示名称+操作按钮）
- 操作：导出、删除、一键更新关联会话
- 底部：导入按钮
- 不显示编辑功能（编辑在次元设置 tab）

### 4.3 新建会话

向导改为：
1. 选择主题包（从已有主题包列表选，或跳过用默认）
2. 完成

### 4.4 编辑会话

会话列表 hover 显示编辑按钮，点击可：
- 重命名
- 更改主题包

### 4.5 切换会话

切换会话时自动加载对应主题包的 persona + theme + assets。

## 5. 开发阶段

| 阶段 | 内容 |
|------|------|
| W0 | 后端：ThemePack 模型 + CRUD API |
| W1 | 后端：会话扩展（theme_pack_id）+ 关联查询 |
| W2 | 前端：次元设置 tab 改造（新建主题包+编辑） |
| W3 | 前端：主题包 tab 改造（列表+导出/删除/更新） |
| W4 | 前端：新建会话改为选主题包 |
| W5 | 前端：会话编辑（重命名+更改主题包） |
| W6 | 前端：切换会话自动切换主题包 |
