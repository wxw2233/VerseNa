# 次元人格 — file_manager 工具设计

> 日期：2026-07-15

## 1. 概述

为 agent 添加文件管理工具，支持全文件系统的读写操作，配合信任模式和确认机制平衡安全性与便利性。

## 2. file_manager 工具接口

### 2.1 工具定义

```python
name = "file_manager"
description = "文件管理器：读取、写入、列出目录、搜索、编辑、复制、移动、删除、获取信息"
parameters = {
    "type": "object",
    "properties": {
        "action": {"type": "string", "enum": ["read","write","list","search","find_replace","copy","move","delete","info"]},
        "path": {"type": "string", "description": "目标路径"},
        "content": {"type": "string", "description": "写入内容（write）"},
        "old": {"type": "string", "description": "查找文本（find_replace）"},
        "new": {"type": "string", "description": "替换文本（find_replace）"},
        "pattern": {"type": "string", "description": "搜索模式（search, glob）"},
        "src": {"type": "string", "description": "源路径（copy/move）"},
        "dst": {"type": "string", "description": "目标路径（copy/move）"},
        "encoding": {"type": "string", "default": "utf-8"},
        "max_size": {"type": "integer", "default": 50000}
    },
    "required": ["action", "path"]
}
```

### 2.2 九个 action

| action | 必需参数 | 可选参数 | 返回 |
|--------|---------|---------|------|
| read | path | encoding, max_size | 文件内容（截断到 max_size） |
| write | path, content | encoding | 写入字节数 |
| list | path | — | 文件/目录列表（名称+类型+大小） |
| search | path, pattern | — | 匹配的文件路径列表 |
| find_replace | path, old, new | — | 替换次数 + 替换后内容预览 |
| copy | src, dst | — | 复制结果 |
| move | src, dst | — | 移动结果 |
| delete | path | — | 删除结果（需确认） |
| info | path | — | 大小/修改时间/类型/权限 |

---

## 3. 安全机制

### 3.1 禁止访问路径

- Linux: `/proc`, `/sys`, `/dev`
- Windows: `C:\Windows\System32`, `C:\Program Files`, `C:\ProgramData`

访问这些路径直接返回错误，不执行。

### 3.2 信任模式

存储于 `app_config` 表，key = `file_trust_mode`。

**关闭（默认）：**
- `delete` → 需确认
- `write` 覆盖已有文件 → 需确认
- 修改系统目录（`/etc`, `C:\Windows`, `C:\Program Files`）→ 需确认

**开启：**
- 只有系统核心文件（`/etc`, `C:\Windows`, `C:\Program Files`）需确认
- 其他操作直接执行

### 3.3 确认机制

后端返回：
```json
{"type": "confirm", "action": "delete", "path": "/some/file", "message": "确认删除文件 /some/file？"}
```

前端显示确认对话框，用户点击后发送：
```json
{"type": "confirm_response", "confirmed": true}
```

后端收到确认后继续执行原操作。

### 3.4 读写限制

- 读取：默认最大 50KB，超过截断并提示
- 二进制文件：检测前 8KB 是否有 null 字节，有则跳过
- 写入：单次最大 1MB
- 写入时自动创建父目录（`mkdir -p` 语义）

---

## 4. 前端改动

### 4.1 设置页"工具" tab

添加信任模式开关：

```
🔒 信任模式：[开关]
开启后，除系统核心文件外，所有文件操作无需确认直接执行。
```

### 4.2 确认对话框

收到 `confirm` 消息时，显示模态确认框：
- 标题：`⚠️ 需要确认`
- 内容：操作描述 + 文件路径
- 按钮：确认 / 取消

---

## 5. 后端改动

### 5.1 新文件

- `backend/tools/builtin/file_manager.py` — FileManagerTool

### 5.2 修改文件

- `backend/api/chat.py` — WebSocket 处理确认响应
- `backend/api/config_api.py` — 信任模式 API
- `frontend/src/views/SettingsView.vue` — 信任模式开关
- `frontend/src/views/ChatView.vue` — 确认对话框

---

## 6. 开发阶段

| 阶段 | 内容 |
|------|------|
| T0 | file_manager 工具（9 个 action + 安全检查） |
| T1 | 信任模式后端（config API + 确认机制） |
| T2 | 前端（信任模式开关 + 确认对话框） |
