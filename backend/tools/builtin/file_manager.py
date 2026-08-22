import asyncio
import os
import shutil
import tempfile
import threading
import time
import uuid
from pathlib import Path

from config import settings
from agent.project_map import mark_project_map_stale
from tools.base import BaseTool, ToolContext
from tools.paths import ToolPath, ToolPathError, resolve_tool_path
from tools.results import tool_confirm, tool_error, tool_result


MAX_READ_BYTES = 500_000
MAX_LIST_ITEMS = 500
MAX_SEARCH_RESULTS = 500
MAX_REPLACE_BYTES = 500 * 1024
MAX_DIRECTORY_SCAN = 5_000
MUTATING_ACTIONS = {"write", "find_replace", "copy", "move", "delete", "mkdir"}


def _audit_log(context: ToolContext, action: str, path: str, result: str, error: str = "") -> None:
    try:
        settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
        clean = lambda value: str(value).replace("\r", " ").replace("\n", " ")
        line = (
            f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] "
            f"session_id={clean(context.session_id)} action={clean(action)} "
            f"path={clean(path)} result={clean(result)} trust_mode={context.trust_mode}"
        )
        if error:
            line += f" error={clean(error)}"
        with (settings.DATA_DIR / "audit.log").open("a", encoding="utf-8") as file:
            file.write(line + "\n")
    except OSError:
        pass


def _atomic_write(path: Path, content: str, encoding: str) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = content.encode(encoding)
    handle, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(handle, "wb") as file:
            file.write(encoded)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)
    return len(encoded)


class FileManagerTool(BaseTool):
    name = "file_manager"
    description = (
        "在工具工作区内读取、列出、搜索和管理文件。读取大文件时必须按返回的 "
        "next_offset 继续，eof=true 后立即停止；不要用 code_exec 代替文件读取。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["read", "write", "list", "search", "find_replace", "copy", "move", "delete", "mkdir", "info"],
                "description": "操作类型",
            },
            "path": {"type": "string", "description": "工作区内的相对路径"},
            "content": {"type": "string", "description": "写入内容"},
            "mode": {"type": "string", "enum": ["overwrite", "append"], "description": "写入模式"},
            "old": {"type": "string", "description": "查找文本"},
            "new": {"type": "string", "description": "替换文本"},
            "pattern": {"type": "string", "description": "文件名 glob 模式，如 *.py"},
            "recursive": {"type": "boolean", "description": "是否递归"},
            "src": {"type": "string", "description": "复制或移动的源路径"},
            "dst": {"type": "string", "description": "复制或移动的目标路径"},
            "encoding": {"type": "string", "description": "文本编码，默认 utf-8"},
            "offset": {
                "type": "integer",
                "minimum": 0,
                "description": "读取起始字节；续读时必须原样使用上次返回的 next_offset",
            },
            "max_size": {
                "type": "integer",
                "minimum": 1,
                "maximum": MAX_READ_BYTES,
                "description": "单次读取字节数；省略时使用高级设置中的工具结果上限，最大 500000",
            },
            "limit": {"type": "integer", "minimum": 1, "maximum": MAX_LIST_ITEMS},
        },
        "required": ["action"],
        "additionalProperties": False,
    }

    async def execute(
        self,
        action: str = "",
        path: str = "",
        content: str = "",
        mode: str = "overwrite",
        old: str = "",
        new: str = "",
        pattern: str = "",
        recursive: bool | None = None,
        src: str = "",
        dst: str = "",
        encoding: str = "utf-8",
        offset: int = 0,
        max_size: int | None = None,
        limit: int = 200,
        _context: ToolContext | None = None,
        _confirmed: bool = False,
        **kwargs,
    ) -> str:
        if not _context:
            return tool_error("MISSING_CONTEXT", "工具执行上下文不可用")
        if action not in self.parameters["properties"]["action"]["enum"]:
            return tool_error("INVALID_ACTION", f"未知 action: {action}")

        try:
            if action in {"copy", "move"}:
                if not src or not dst:
                    return tool_error("INVALID_ARGUMENT", f"{action} 需要 src 和 dst")
                source = resolve_tool_path(_context, src)
                destination = resolve_tool_path(_context, dst)
                if source.check_path == _context.workspace.resolve():
                    return tool_error("WORKSPACE_ROOT_PROTECTED", "不能复制或移动整个工具工作区")
                preflight_error = self._copy_move_preflight(source, destination)
                if preflight_error:
                    return preflight_error
                if not _confirmed and not _context.trust_mode:
                    return self._confirm(action, src=src, dst=dst)
                return await asyncio.to_thread(
                    self._copy_or_move,
                    action,
                    source,
                    destination,
                    _context,
                )

            if not path:
                path = "." if action in {"list", "search"} else ""
            if not path:
                return tool_error("INVALID_ARGUMENT", "必须指定 path")
            target = resolve_tool_path(_context, path)

            if action in MUTATING_ACTIONS and target.check_path == _context.workspace.resolve():
                return tool_error("WORKSPACE_ROOT_PROTECTED", "不能修改工具工作区根目录")

            preflight_error = self._mutation_preflight(action, target, mode, old, recursive)
            if preflight_error:
                return preflight_error

            if action in MUTATING_ACTIONS and not _confirmed and not _context.trust_mode:
                return self._confirm(action, path=path)

            if action == "read":
                if max_size is None:
                    max_size = self._read_limit(_context.agent_config)
                return await self._run_interruptible(
                    _context,
                    self._read,
                    target,
                    encoding,
                    offset,
                    max_size,
                    timeout=20,
                )
            if action == "write":
                return await asyncio.to_thread(
                    self._write,
                    target,
                    content,
                    mode,
                    encoding,
                    _context,
                )
            if action == "list":
                return await self._run_interruptible(
                    _context,
                    self._list,
                    target,
                    limit,
                    timeout=20,
                )
            if action == "search":
                return await self._run_interruptible(
                    _context,
                    self._search,
                    target,
                    pattern,
                    recursive if recursive is not None else True,
                    limit,
                    timeout=30,
                )
            if action == "find_replace":
                return await asyncio.to_thread(
                    self._find_replace,
                    target,
                    old,
                    new,
                    encoding,
                    _context,
                )
            if action == "delete":
                return await asyncio.to_thread(
                    self._delete,
                    target,
                    recursive if recursive is not None else False,
                    _context,
                )
            if action == "mkdir":
                return await asyncio.to_thread(self._mkdir, target, _context)
            return await self._run_interruptible(
                _context,
                self._info,
                target,
                timeout=10,
            )
        except ToolPathError as exc:
            _audit_log(_context, action, path or f"{src}->{dst}", "error", "WORKSPACE_VIOLATION")
            return tool_error("WORKSPACE_VIOLATION", str(exc))
        except LookupError as exc:
            return tool_error("INVALID_ENCODING", str(exc))
        except PermissionError as exc:
            _audit_log(_context, action, path or f"{src}->{dst}", "error", str(exc))
            return tool_error("PERMISSION_DENIED", str(exc))
        except OSError as exc:
            _audit_log(_context, action, path or f"{src}->{dst}", "error", str(exc))
            return tool_error("OS_ERROR", str(exc))

    @staticmethod
    def _read_limit(agent_config) -> int:
        try:
            value = int((agent_config or {}).get("tool_result_max_chars", 100_000))
        except (TypeError, ValueError):
            value = 100_000
        return max(1, min(value, MAX_READ_BYTES))

    @staticmethod
    async def _run_interruptible(
        context: ToolContext,
        operation,
        *args,
        timeout: float,
    ) -> str:
        if context.stop_event and context.stop_event.is_set():
            return tool_error("CANCELLED", "操作已停止")

        cancel_event = threading.Event()
        operation_task = asyncio.create_task(
            asyncio.to_thread(operation, cancel_event, *args)
        )
        stop_task = (
            asyncio.create_task(context.stop_event.wait())
            if context.stop_event
            else None
        )
        wait_for = {operation_task, stop_task} if stop_task else {operation_task}
        try:
            completed, _ = await asyncio.wait(
                wait_for,
                timeout=timeout,
                return_when=asyncio.FIRST_COMPLETED,
            )
            if operation_task in completed:
                return operation_task.result()

            cancel_event.set()
            operation_task.cancel()
            if stop_task and stop_task in completed:
                return tool_error("CANCELLED", "操作已停止")
            return tool_error("TIMEOUT", f"文件操作超过 {int(timeout)} 秒，已中止")
        finally:
            if operation_task.cancelled():
                await asyncio.gather(operation_task, return_exceptions=True)
            if stop_task:
                stop_task.cancel()
                await asyncio.gather(stop_task, return_exceptions=True)

    @staticmethod
    def _confirm(action: str, **details) -> str:
        labels = {
            "write": "写入文件",
            "find_replace": "替换文件内容",
            "copy": "复制文件",
            "move": "移动文件",
            "delete": "删除文件",
            "mkdir": "新建文件夹",
        }
        return tool_confirm(str(uuid.uuid4()), action, f"确认{labels[action]}？", **details)

    @staticmethod
    def _copy_move_preflight(source: ToolPath, destination: ToolPath) -> str | None:
        src = source.op_path
        dst = destination.op_path
        if not src.exists() and not src.is_symlink():
            return tool_error("FILE_NOT_FOUND", f"源路径不存在: {src}")
        if src.is_symlink():
            return tool_error("SYMLINK_NOT_SUPPORTED", "不支持复制或移动符号链接")
        if dst.exists() or dst.is_symlink():
            return tool_error("DESTINATION_EXISTS", f"目标路径已存在: {dst}")
        return None

    @staticmethod
    def _mutation_preflight(action: str, target: ToolPath, mode: str, old: str, recursive: bool | None) -> str | None:
        path = target.op_path
        if action == "write":
            if mode not in {"overwrite", "append"}:
                return tool_error("INVALID_MODE", "mode 必须是 overwrite 或 append")
            if path.exists() and path.is_dir():
                return tool_error("PATH_IS_DIRECTORY", f"路径是目录: {path}")
        elif action == "find_replace":
            if not old:
                return tool_error("INVALID_ARGUMENT", "find_replace 需要 old 参数")
            if not path.exists() or not path.is_file():
                return tool_error("FILE_NOT_FOUND", f"文件不存在: {path}")
            if path.stat().st_size > MAX_REPLACE_BYTES:
                return tool_error("FILE_TOO_LARGE", "find_replace 仅支持 500KB 以内文件")
        elif action == "delete":
            if not path.exists() and not path.is_symlink():
                return tool_error("FILE_NOT_FOUND", f"路径不存在: {path}")
            if path.is_dir() and not path.is_symlink() and not recursive:
                return tool_error("RECURSIVE_REQUIRED", "删除目录需要 recursive=true")
        elif action == "mkdir":
            if path.exists() or path.is_symlink():
                return tool_error("DESTINATION_EXISTS", f"目标路径已存在: {path}")
        return None

    @staticmethod
    def _mark_project_index_stale(context: ToolContext) -> None:
        """Ensure a later project_map call never reuses a pre-mutation cache."""
        try:
            mark_project_map_stale(context.workspace)
        except (OSError, TypeError, ValueError):
            pass

    @staticmethod
    def _read(cancel_event: threading.Event, target: ToolPath, encoding: str, offset: int, max_size: int) -> str:
        if cancel_event.is_set():
            return tool_error("CANCELLED", "操作已停止")
        path = target.op_path
        if not path.exists():
            return tool_error("FILE_NOT_FOUND", f"文件不存在: {path}")
        if path.is_dir():
            return tool_error("PATH_IS_DIRECTORY", f"路径是目录: {path}")
        size = path.stat().st_size
        offset = min(max(0, int(offset)), size)
        max_size = max(1, min(int(max_size), MAX_READ_BYTES))
        with path.open("rb") as file:
            file.seek(min(offset, size))
            raw = file.read(max_size)
        if b"\x00" in raw[:8192]:
            return tool_error("BINARY_FILE_NOT_SUPPORTED", "不支持读取二进制文件")
        text = raw.decode(encoding, errors="replace")
        next_offset = offset + len(raw)
        remaining_bytes = max(0, size - next_offset)
        return tool_result(True, data={
            "content": text,
            "offset": offset,
            "bytes_read": len(raw),
            "next_offset": next_offset,
            "remaining_bytes": remaining_bytes,
            "truncated": remaining_bytes > 0,
            "eof": remaining_bytes == 0,
            "size": size,
            "continuation": (
                f"继续读取时必须设置 offset={next_offset}"
                if remaining_bytes > 0
                else "文件已读取完毕，请勿再次读取此文件"
            ),
        })

    @staticmethod
    def _write(target: ToolPath, content: str, mode: str, encoding: str, context: ToolContext) -> str:
        path = target.op_path
        if path.exists() and path.is_dir():
            return tool_error("PATH_IS_DIRECTORY", f"路径是目录: {path}")
        if mode == "append":
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding=encoding) as file:
                written = file.write(content)
            bytes_written = len(content[:written].encode(encoding))
        else:
            bytes_written = _atomic_write(path, content, encoding)
        _audit_log(context, "write", str(path), "success")
        FileManagerTool._mark_project_index_stale(context)
        return tool_result(True, data={"bytes_written": bytes_written, "path": str(path)})

    @staticmethod
    def _list(cancel_event: threading.Event, target: ToolPath, limit: int) -> str:
        path = target.op_path
        if not path.exists():
            return tool_error("FILE_NOT_FOUND", f"目录不存在: {path}")
        if not path.is_dir():
            return tool_error("PATH_IS_FILE", f"路径不是目录: {path}")
        limit = max(1, min(int(limit), MAX_LIST_ITEMS))
        entries = []
        scan_truncated = False
        for entry in path.iterdir():
            if cancel_event.is_set():
                return tool_error("CANCELLED", "操作已停止")
            entries.append(entry)
            if len(entries) >= MAX_DIRECTORY_SCAN:
                scan_truncated = True
                break
        entries.sort(key=lambda item: (not item.is_dir(), item.name.lower()))
        items = []
        for entry in entries[:limit]:
            stat = entry.lstat()
            kind = "symlink" if entry.is_symlink() else "dir" if entry.is_dir() else "file"
            items.append({"name": entry.name, "type": kind, "size": stat.st_size if kind == "file" else 0})
        return tool_result(True, data={
            "items": items,
            "total": len(entries),
            "truncated": scan_truncated or len(entries) > limit,
            "scan_truncated": scan_truncated,
        })

    @staticmethod
    def _search(
        cancel_event: threading.Event,
        target: ToolPath,
        pattern: str,
        recursive: bool,
        limit: int,
    ) -> str:
        path = target.op_path
        if not path.exists() or not path.is_dir():
            return tool_error("PATH_NOT_DIRECTORY", f"搜索目录不存在: {path}")
        if not pattern or Path(pattern).is_absolute() or ".." in Path(pattern).parts:
            return tool_error("INVALID_PATTERN", "pattern 必须是工作区内的 glob 文件名模式")
        limit = max(1, min(int(limit), MAX_SEARCH_RESULTS))
        matches = []
        truncated = False
        scanned = 0
        if recursive:
            iterator = (
                Path(root) / name
                for root, directories, files in os.walk(path, followlinks=False)
                for name in [*directories, *files]
            )
        else:
            iterator = path.iterdir()
        for match in iterator:
            if cancel_event.is_set():
                return tool_error("CANCELLED", "操作已停止")
            scanned += 1
            if scanned > MAX_DIRECTORY_SCAN:
                truncated = True
                break
            try:
                relative = match.relative_to(path)
            except ValueError:
                relative = match
            if relative.match(pattern):
                matches.append(str(match))
                if len(matches) >= limit:
                    truncated = True
                    break
        return tool_result(True, data={
            "matches": matches,
            "count": len(matches),
            "truncated": truncated,
            "scanned": scanned,
        })

    @staticmethod
    def _find_replace(target: ToolPath, old: str, new: str, encoding: str, context: ToolContext) -> str:
        path = target.op_path
        content = path.read_text(encoding=encoding, errors="replace")
        replacements = content.count(old)
        if replacements:
            _atomic_write(path, content.replace(old, new), encoding)
            _audit_log(context, "find_replace", str(path), "success")
            FileManagerTool._mark_project_index_stale(context)
        return tool_result(True, data={"replacements": replacements, "path": str(path)})

    @staticmethod
    def _copy_or_move(action: str, source: ToolPath, destination: ToolPath, context: ToolContext) -> str:
        src = source.op_path
        dst = destination.op_path
        dst.parent.mkdir(parents=True, exist_ok=True)
        if action == "copy":
            shutil.copytree(src, dst) if src.is_dir() else shutil.copy2(src, dst)
        else:
            shutil.move(str(src), str(dst))
        _audit_log(context, action, f"{src}->{dst}", "success")
        FileManagerTool._mark_project_index_stale(context)
        return tool_result(True, data={"src": str(src), "dst": str(dst), "action": action})

    @staticmethod
    def _delete(target: ToolPath, recursive: bool, context: ToolContext) -> str:
        path = target.op_path
        if path.is_symlink():
            path.unlink()
        elif path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
        _audit_log(context, "delete", str(path), "success")
        FileManagerTool._mark_project_index_stale(context)
        return tool_result(True, data={"deleted": True, "path": str(path)})

    @staticmethod
    def _mkdir(target: ToolPath, context: ToolContext) -> str:
        path = target.op_path
        path.mkdir(parents=True, exist_ok=False)
        _audit_log(context, "mkdir", str(path), "success")
        FileManagerTool._mark_project_index_stale(context)
        return tool_result(True, data={"created": True, "path": str(path), "type": "dir"})

    @staticmethod
    def _info(cancel_event: threading.Event, target: ToolPath) -> str:
        if cancel_event.is_set():
            return tool_error("CANCELLED", "操作已停止")
        path = target.op_path
        if not path.exists() and not path.is_symlink():
            return tool_error("FILE_NOT_FOUND", f"路径不存在: {path}")
        stat = path.lstat()
        kind = "symlink" if path.is_symlink() else "dir" if path.is_dir() else "file"
        return tool_result(True, data={
            "path": str(path),
            "size": stat.st_size,
            "modified": int(stat.st_mtime),
            "type": kind,
            "permissions": oct(stat.st_mode & 0o777),
        })


def register(registry):
    registry.register(FileManagerTool())
