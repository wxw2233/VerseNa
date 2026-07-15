# 次元人格 — file_manager 工具设计（v4）

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
| old | string | find_replace | 查找文本（全文本匹配，不支持正则） |
| new | string | find_replace | 替换文本 |
| pattern | string | search | 标准 glob 模式（`*.py`, `**/*.json`） |
| recursive | bool | search(默认true), delete(默认false) | 是否递归 |
| src | string | copy/move | 源路径 |
| dst | string | copy/move | 目标路径 |
| encoding | string | read/write | 默认 utf-8 |
| max_size | int | read | 默认 50000 |
| limit | int | list | 最大返回条数，默认 200 |

### 2.3 返回格式

成功：`{"success": true, "data": {...}}`
失败：`{"success": false, "error": "错误码", "message": "人类可读描述"}`

错误码：`FILE_NOT_FOUND`, `PERMISSION_DENIED`, `DISK_FULL`, `ENCODING_ERROR`, `PATH_FORBIDDEN`, `FILE_TOO_LARGE`, `CONFIRM_REQUIRED`, `CONFIRM_TIMEOUT`, `PATH_IS_DIRECTORY`, `PATH_IS_FILE`, `DEST_EXISTS`, `INVALID_PATH`, `BINARY_FILE_NOT_SUPPORTED`

### 2.4 九个 action 语义

| action | 必需 | 可选 | 返回 data |
|--------|------|------|-----------|
| read | path | encoding, max_size | {content, truncated, size} — 空文件: content="", truncated=false; 二进制文件: 返回 BINARY_FILE_NOT_SUPPORTED |
| write | path, content | mode, encoding | {bytes_written, created_dirs} — path 为目录返回 PATH_IS_DIRECTORY; append 模式文件不存在则自动创建; 大小按 encoding 编码后字节数计算 |
| list | path | limit | {items: [{name,type(file/dir/symlink),size}], total} — 空目录: items=[], total=0 |
| search | path, pattern | recursive | {matches: [绝对路径], count} — 返回绝对路径 |
| find_replace | path, old, new | — | {replacements, preview(前500字)} — 全文本全局替换; 二进制文件返回 BINARY_FILE_NOT_SUPPORTED; 替换后大小超 1MB 返回 FILE_TOO_LARGE |
| copy | src, dst | — | {copied(bytes)} |
| move | src, dst | — | {moved: true} |
| delete | path | recursive | {deleted: true} |
| info | path | — | {size, modified(Unix秒时间戳), type(file/dir/symlink), permissions(八进制如0o755), is_symlink} |

### 2.5 copy/move 目标语义

对齐系统 cp/mv：
- dst 为已存在目录：将 src 放入 dst 内，保留原名
- dst 为不存在路径：将 src 重命名为 dst
- dst 为已存在文件：触发覆盖确认（同 write 覆盖规则）
- 跨分区 move：自动降级为 copy + delete
- src 和 dst 都需执行完整安全校验

---

## 3. 安全机制

### 3.1 路径处理顺序

```
1. os.path.expanduser(path)   — 展开 ~ 为用户主目录
2. os.path.abspath(path)      — 解析相对路径为绝对路径
3. os.path.realpath(path)     — 解析符号链接得到物理路径（仅用于安全校验）
```

**安全校验：** 使用 realpath 后的路径
**实际操作：** 使用 expanduser + abspath 后的路径（不解析符号链接）

这样删除软链接只删除链接本身，不删除目标文件。

### 3.2 禁止路径匹配规则

**目录型禁止路径**（如 `/proc`, `C:\Windows`）：
- 目标路径等于禁止路径，或以「禁止路径 + `/`」开头 → 拦截
- 例：`/proc/1/status` 匹配 `/proc`，但 `/proc_thing` 不匹配

**文件型禁止路径**（如 `/etc/shadow`）：
- 精确匹配完整路径

**Windows：** 路径统一转小写后匹配，兼容盘符大小写

**硬禁止（所有操作均拦截，包括只读）：**
- Linux: `/proc`, `/sys`, `/dev`, `/etc/shadow`, `/etc/passwd`
- Windows: `c:\windows\system32`, `c:\program files`, `c:\programdata`
- 跨平台: `{home}/.ssh`, `{home}/.gnupg`

**所有操作均校验**（包括 read/list/search/info），防止通过只读操作窃取敏感文件。

### 3.3 敏感路径（信任模式关闭时需确认）

- 用户主目录下所有以 `.` 开头的隐藏文件与目录
- `/etc` 下其他文件
- `C:\Windows` 下其他文件

### 3.4 信任模式

存储于 `app_config` 表，key = `file_trust_mode`。

**关闭（默认）：**
- delete → 需确认
- write 覆盖已有文件 → 需确认（append 不需确认）
- find_replace 在敏感路径 → 需确认
- copy/move 目标已存在文件 → 需确认
- delete 目录 + recursive → 强制确认（无论信任模式），确认消息显示待删除的文件总数、目录总数

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
  "message": "确认删除文件 /some/file？",
  "file_count": 10,
  "dir_count": 3
}
```

前端回传：
```json
{"type": "confirm_response", "request_id": "uuid", "confirmed": true}
```

**超时：** 60 秒未收到响应，自动取消，返回 CONFIRM_TIMEOUT。

### 3.6 递归删除安全增强

递归删除前，遍历所有子文件与子目录，逐个执行 realpath 安全校验。任意子项命中硬禁止路径，直接拒绝操作，返回 PATH_FORBIDDEN。

### 3.7 读写限制

- 读取：默认最大 50KB，超过截断
- 二进制检测：read 和 find_replace 触发，检测前 8KB 有 null 字节则返回 BINARY_FILE_NOT_SUPPORTED
- 写入：按 encoding 编码后字节数计算，单次最大 1MB
- 自动创建父目录

### 3.8 操作审计日志

记录到 `data/audit.log`：
```
[2026-07-15 22:00:00] request_id=xxx action=delete path=/some/file result=success trust_mode=false
[2026-07-15 22:00:01] request_id=yyy action=write path=/some/file result=error error=FILE_TOO_LARGE trust_mode=false
```

---

## 4. 前端改动

### 4.1 设置页"工具" tab

信任模式开关。

### 4.2 确认对话框

收到 `confirm` 消息时显示模态确认框，带回 `request_id`。显示操作描述 + 文件路径 + 文件/目录总数（递归删除时）。

---

## 5. 开发阶段

| 阶段 | 内容 |
|------|------|
| T0 | 只读 action（read/list/search/info）+ 路径安全校验 + 审计日志 |
| T1 | 写入 action（write/find_replace/copy/move/delete）+ 确认机制 + 信任模式后端 |
| T2 | 前端（信任模式开关 + 确认对话框） |
