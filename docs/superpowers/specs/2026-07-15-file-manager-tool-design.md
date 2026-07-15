# 次元人格 — file_manager 工具设计（v2）

> 日期：2026-07-15

## 1. 概述

为 agent 添加文件管理工具，支持全文件系统的读写操作，配合信任模式和确认机制平衡安全性与便利性。

## 2. file_manager 工具接口

### 2.1 工具定义

```python
name = "file_manager"
description = "文件管理器：读取、写入、列出目录、搜索、编辑、复制、移动、删除、获取信息"
```

### 2.2 参数（按 action 区分必填）

| 参数 | 类型 | 必填于 | 说明 |
|------|------|--------|------|
| action | string | 所有 | read/write/list/search/find_replace/copy/move/delete/info |
| path | string | read/write/list/search/find_replace/delete/info | 目标路径 |
| content | string | write | 写入内容 |
| mode | string | write | overwrite(默认)/append |
| old | string | find_replace | 查找文本 |
| new | string | find_replace | 替换文本 |
| pattern | string | search | glob 模式（如 `*.py`） |
| recursive | bool | search(默认true), delete(默认false) | 是否递归 |
| src | string | copy/move | 源路径 |
| dst | string | copy/move | 目标路径 |
| encoding | string | read/write | 默认 utf-8 |
| max_size | int | read | 默认 50000 |
| limit | int | list | 最大返回条数，默认 200 |

### 2.3 返回格式

成功：
```json
{"success": true, "data": {...}}
```

失败：
```json
{"success": false, "error": "FILE_NOT_FOUND", "message": "文件不存在"}
```

错误类型：`FILE_NOT_FOUND`, `PERMISSION_DENIED`, `DISK_FULL`, `ENCODING_ERROR`, `PATH_FORBIDDEN`, `FILE_TOO_LARGE`, `CONFIRM_REQUIRED`

### 2.4 九个 action

| action | 必需参数 | 可选参数 | 返回 data |
|--------|---------|---------|-----------|
| read | path | encoding, max_size | {content: str, truncated: bool, size: int} |
| write | path, content | mode, encoding | {bytes_written: int, created_dirs: bool} |
| list | path | limit | {items: [{name, type, size}...], total: int} |
| search | path, pattern | recursive | {matches: [str...], count: int} |
| find_replace | path, old, new | — | {replacements: int, preview: str(前500字)} |
| copy | src, dst | — | {copied: int(bytes)} |
| move | src, dst | — | {moved: true} |
| delete | path | recursive | {deleted: true} |
| info | path | — | {size, modified, type, permissions, is_symlink} |

---

## 3. 安全机制

### 3.1 路径规范化

所有路径执行：
1. 统一转正斜杠 `/`
2. `os.path.abspath()` 规范化
3. 解析符号链接 `os.path.realpath()`
4. 检查是否在禁止路径内

### 3.2 禁止访问路径

**硬禁止（直接拒绝，不可信任模式放行）：**
- Linux: `/proc`, `/sys`, `/dev`, `/etc/shadow`, `/etc/passwd`
- Windows: `C:\Windows\System32`, `C:\Program Files`, `C:\ProgramData`
- 跨平台: `~/.ssh`, `~/.gnupg`

### 3.3 敏感路径（信任模式关闭时需确认）

- `/etc` 下其他文件
- `C:\Windows` 下其他文件
- 用户主目录配置文件（`.bashrc`, `.gitconfig` 等）

### 3.4 信任模式

存储于 `app_config` 表，key = `file_trust_mode`。

**关闭（默认）：**
- delete → 需确认
- write 覆盖已有文件 → 需确认（append 不需确认）
- 敏感路径修改 → 需确认
- delete 目录 + recursive → 强制确认（无论信任模式）

**开启：**
- 只有硬禁止路径修改需确认
- 其他操作直接执行

### 3.5 确认机制

后端返回：
```json
{
  "type": "confirm",
  "request_id": "uuid",
  "action": "delete",
  "path": "/some/file",
  "message": "确认删除文件 /some/file？"
}
```

前端回传：
```json
{"type": "confirm_response", "request_id": "uuid", "confirmed": true}
```

### 3.6 读写限制

- 读取：默认最大 50KB，超过截断
- 二进制文件：检测前 8KB 有 null 字节则跳过
- 写入：单次最大 1MB
- 自动创建父目录
- find_replace：大文件（>500KB）拒绝执行，返回 FILE_TOO_LARGE

### 3.7 操作审计日志

所有写入/删除/修改操作记录到 `data/audit.log`：
```
[2026-07-15 22:00:00] action=delete path=/some/file result=success trust_mode=false
```

---

## 4. 前端改动

### 4.1 设置页"工具" tab

信任模式开关。

### 4.2 确认对话框

收到 `confirm` 消息时显示模态确认框，带回 `request_id`。

---

## 5. 开发阶段

| 阶段 | 内容 |
|------|------|
| T0 | file_manager 工具（9 action + 安全检查 + 审计日志） |
| T1 | 信任模式后端（config API + 确认机制 + request_id） |
| T2 | 前端（信任模式开关 + 确认对话框） |
