import os
import shutil
import time
import uuid
import glob as glob_mod
from pathlib import Path
from tools.base import BaseTool

# 硬禁止路径（所有操作均拦截）
FORBIDDEN_PATHS_LINUX = ['/proc', '/sys', '/dev', '/etc/shadow', '/etc/passwd']
FORBIDDEN_PATHS_WIN = ['c:\\windows\\system32', 'c:\\program files', 'c:\\programdata']


def _get_home():
    return Path.home()


def _get_forbidden_paths():
    home = str(_get_home())
    paths = [home + '/.ssh', home + '/.gnupg']
    if os.name == 'nt':
        paths.extend(FORBIDDEN_PATHS_WIN)
    else:
        paths.extend(FORBIDDEN_PATHS_LINUX)
    return paths


def _normalize_for_check(path):
    """安全校验用：expanduser → abspath → realpath"""
    p = os.path.expanduser(path)
    p = os.path.abspath(p)
    p = os.path.realpath(p)
    return p


def _normalize_for_op(path):
    """实际操作用：expanduser → abspath（不解析符号链接）"""
    p = os.path.expanduser(path)
    p = os.path.abspath(p)
    return p


def _is_forbidden(check_path):
    """检查路径是否命中硬禁止"""
    cp = check_path.lower() if os.name == 'nt' else check_path
    for fp in _get_forbidden_paths():
        fp_norm = fp.lower() if os.name == 'nt' else fp
        if cp == fp_norm or cp.startswith(fp_norm + '/') or cp.startswith(fp_norm + '\\'):
            return True
    return False


def _is_sensitive(check_path):
    """检查路径是否为敏感路径（主目录下隐藏文件）"""
    home = str(_get_home())
    cp = check_path
    if cp.startswith(home):
        rel = cp[len(home):].lstrip('/\\')
        if rel.startswith('.'):
            return True
    if cp.startswith('/etc/'):
        return True
    if os.name == 'nt' and cp.lower().startswith('c:\\windows\\'):
        return True
    return False


def _is_binary(path, op_path):
    """检测文件是否为二进制"""
    try:
        with open(op_path, 'rb') as f:
            chunk = f.read(8192)
            return b'\x00' in chunk
    except Exception:
        return False


def _audit_log(request_id, action, path, result, error='', trust_mode=False):
    """审计日志"""
    try:
        log_dir = Path(__file__).parent.parent.parent.parent / 'data'
        log_dir.mkdir(exist_ok=True)
        log_file = log_dir / 'audit.log'
        ts = time.strftime('%Y-%m-%d %H:%M:%S')
        line = f"[{ts}] request_id={request_id} action={action} path={path} result={result}"
        if error:
            line += f" error={error}"
        line += f" trust_mode={trust_mode}\n"
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(line)
    except Exception:
        pass


class FileManagerTool(BaseTool):
    name = "file_manager"
    description = "文件管理器：读取(read)、写入(write)、列出目录(list)、搜索文件名(search)、查找替换(find_replace)、复制(copy)、移动(move)、删除(delete)、获取信息(info)"
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["read", "write", "list", "search", "find_replace", "copy", "move", "delete", "info"],
                "description": "操作类型"
            },
            "path": {"type": "string", "description": "目标文件/目录路径"},
            "content": {"type": "string", "description": "写入内容（write专用）"},
            "mode": {"type": "string", "enum": ["overwrite", "append"], "description": "写入模式，默认overwrite"},
            "old": {"type": "string", "description": "查找文本（find_replace专用）"},
            "new": {"type": "string", "description": "替换文本（find_replace专用）"},
            "pattern": {"type": "string", "description": "glob搜索模式（search专用，如*.py）"},
            "recursive": {"type": "boolean", "description": "是否递归（search默认true, delete默认false）"},
            "src": {"type": "string", "description": "源路径（copy/move专用）"},
            "dst": {"type": "string", "description": "目标路径（copy/move专用）"},
            "encoding": {"type": "string", "description": "文件编码，默认utf-8"},
            "max_size": {"type": "integer", "description": "读取最大字节数，默认50000"},
            "limit": {"type": "integer", "description": "list最大返回条数，默认200"},
            "confirmed": {"type": "boolean", "description": "是否已确认（内部参数，前端确认后传入）"}
        },
        "required": ["action"]
    }

    def __init__(self, trust_mode_getter=None):
        self._trust_mode_getter = trust_mode_getter

    def _get_trust_mode(self):
        if self._trust_mode_getter:
            return self._trust_mode_getter()
        return False

    def _check_path(self, path, action, request_id):
        """安全校验，返回 (check_path, op_path, error_dict_or_None)"""
        check_path = _normalize_for_check(path)
        op_path = _normalize_for_op(path)

        if _is_forbidden(check_path):
            _audit_log(request_id, action, path, 'error', 'PATH_FORBIDDEN', self._get_trust_mode())
            return None, None, {"success": False, "error": "PATH_FORBIDDEN", "message": f"禁止访问系统核心路径: {path}"}

        return check_path, op_path, None

    def _needs_confirm(self, action, check_path, is_overwrite=False, is_recursive_delete=False):
        """判断是否需要确认"""
        if is_recursive_delete:
            return True

        trust = self._get_trust_mode()
        if trust:
            return False

        if action == 'delete':
            return True
        if action == 'write' and is_overwrite:
            return True
        if action in ('find_replace',) and _is_sensitive(check_path):
            return True
        if action in ('copy', 'move') and is_overwrite:
            return True

        return False

    async def execute(self, action='', path='', content='', mode='overwrite',
                      old='', new='', pattern='', recursive=None,
                      src='', dst='', encoding='utf-8', max_size=50000,
                      limit=200, confirmed=False, **kwargs) -> str:
        import json

        if not action:
            return json.dumps({"success": False, "error": "INVALID_PATH", "message": "必须指定 action"}, ensure_ascii=False)

        request_id = str(uuid.uuid4())[:8]

        # copy/move 用 src/dst
        if action in ('copy', 'move'):
            if not src or not dst:
                return json.dumps({"success": False, "error": "INVALID_PATH", "message": f"{action} 需要 src 和 dst 参数"}, ensure_ascii=False)
            check_src, op_src, err = self._check_path(src, action, request_id)
            if err:
                return json.dumps(err, ensure_ascii=False)
            check_dst, op_dst, err = self._check_path(dst, action, request_id)
            if err:
                return json.dumps(err, ensure_ascii=False)

            dst_exists = os.path.exists(op_dst)
            is_overwrite = dst_exists and os.path.isfile(op_dst)

            if not confirmed and self._needs_confirm(action, check_src, is_overwrite=is_overwrite):
                msg = f"确认{('复制' if action == 'copy' else '移动')} {src} → {dst}？"
                if is_overwrite:
                    msg += " (目标文件已存在，将被覆盖)"
                return json.dumps({
                    "type": "confirm", "request_id": request_id, "action": action,
                    "src": src, "dst": dst, "message": msg
                }, ensure_ascii=False)

            try:
                if action == 'copy':
                    if os.path.isdir(op_src):
                        shutil.copytree(op_src, op_dst)
                    else:
                        os.makedirs(os.path.dirname(op_dst) or '.', exist_ok=True)
                        shutil.copy2(op_src, op_dst)
                    size = sum(f.stat().st_size for f in Path(op_dst).rglob('*') if f.is_file()) if os.path.isdir(op_dst) else os.path.getsize(op_dst)
                    _audit_log(request_id, action, f"{src}->{dst}", 'success', trust_mode=self._get_trust_mode())
                    return json.dumps({"success": True, "data": {"copied": size}}, ensure_ascii=False)
                else:
                    os.makedirs(os.path.dirname(op_dst) or '.', exist_ok=True)
                    try:
                        shutil.move(op_src, op_dst)
                    except OSError:
                        if os.path.isdir(op_src):
                            shutil.copytree(op_src, op_dst)
                            shutil.rmtree(op_src)
                        else:
                            shutil.copy2(op_src, op_dst)
                            os.remove(op_src)
                    _audit_log(request_id, action, f"{src}->{dst}", 'success', trust_mode=self._get_trust_mode())
                    return json.dumps({"success": True, "data": {"moved": True}}, ensure_ascii=False)
            except Exception as e:
                _audit_log(request_id, action, f"{src}->{dst}", 'error', str(e), self._get_trust_mode())
                return json.dumps({"success": False, "error": "PERMISSION_DENIED", "message": str(e)}, ensure_ascii=False)

        # 其他操作用 path
        if not path:
            return json.dumps({"success": False, "error": "INVALID_PATH", "message": "必须指定 path"}, ensure_ascii=False)

        check_path, op_path, err = self._check_path(path, action, request_id)
        if err:
            return json.dumps(err, ensure_ascii=False)

        try:
            if action == 'read':
                return self._do_read(op_path, encoding, max_size, request_id)
            elif action == 'write':
                return self._do_write(check_path, op_path, content, mode, encoding, request_id, confirmed)
            elif action == 'list':
                return self._do_list(op_path, limit, request_id)
            elif action == 'search':
                return self._do_search(op_path, pattern, recursive if recursive is not None else True, request_id)
            elif action == 'find_replace':
                return self._do_find_replace(check_path, op_path, old, new, encoding, request_id, confirmed)
            elif action == 'delete':
                return self._do_delete(check_path, op_path, recursive if recursive is not None else False, request_id, confirmed)
            elif action == 'info':
                return self._do_info(op_path, request_id)
            else:
                return json.dumps({"success": False, "error": "INVALID_PATH", "message": f"未知 action: {action}"}, ensure_ascii=False)
        except Exception as e:
            _audit_log(request_id, action, path, 'error', str(e), self._get_trust_mode())
            return json.dumps({"success": False, "error": "PERMISSION_DENIED", "message": str(e)}, ensure_ascii=False)

    def _do_read(self, op_path, encoding, max_size, request_id):
        import json
        if not os.path.exists(op_path):
            return json.dumps({"success": False, "error": "FILE_NOT_FOUND", "message": f"文件不存在: {op_path}"}, ensure_ascii=False)
        if os.path.isdir(op_path):
            return json.dumps({"success": False, "error": "PATH_IS_DIRECTORY", "message": f"路径是目录，不是文件: {op_path}"}, ensure_ascii=False)
        if _is_binary(op_path, op_path):
            return json.dumps({"success": False, "error": "BINARY_FILE_NOT_SUPPORTED", "message": "不支持操作二进制文件"}, ensure_ascii=False)

        size = os.path.getsize(op_path)
        with open(op_path, 'r', encoding=encoding, errors='replace') as f:
            content = f.read(max_size)
        truncated = size > max_size
        return json.dumps({"success": True, "data": {"content": content, "truncated": truncated, "size": size}}, ensure_ascii=False)

    def _do_write(self, check_path, op_path, content, mode, encoding, request_id, confirmed=False):
        import json
        is_overwrite = os.path.exists(op_path) and mode == 'overwrite'
        if os.path.isdir(op_path):
            return json.dumps({"success": False, "error": "PATH_IS_DIRECTORY", "message": f"路径是目录: {op_path}"}, ensure_ascii=False)

        if not confirmed and self._needs_confirm('write', check_path, is_overwrite=is_overwrite):
            msg = f"确认写入文件 {op_path}？"
            if is_overwrite:
                msg += " (文件已存在，将被覆盖)"
            return json.dumps({
                "type": "confirm", "request_id": request_id, "action": "write",
                "path": op_path, "message": msg
            }, ensure_ascii=False)

        os.makedirs(os.path.dirname(op_path) or '.', exist_ok=True)
        write_mode = 'a' if mode == 'append' else 'w'
        with open(op_path, write_mode, encoding=encoding) as f:
            f.write(content)
        _audit_log(request_id, 'write', op_path, 'success', trust_mode=self._get_trust_mode())
        return json.dumps({"success": True, "data": {"bytes_written": len(content.encode(encoding)), "created_dirs": True}}, ensure_ascii=False)

    def _do_list(self, op_path, limit, request_id):
        import json
        if not os.path.exists(op_path):
            return json.dumps({"success": False, "error": "FILE_NOT_FOUND", "message": f"路径不存在: {op_path}"}, ensure_ascii=False)
        if os.path.isfile(op_path):
            return json.dumps({"success": False, "error": "PATH_IS_FILE", "message": f"路径是文件，不是目录: {op_path}"}, ensure_ascii=False)

        items = []
        for entry in os.scandir(op_path):
            if len(items) >= limit:
                break
            etype = 'dir' if entry.is_dir(follow_symlinks=False) else 'file'
            if entry.is_symlink():
                etype = 'symlink'
            items.append({
                "name": entry.name, "type": etype,
                "size": entry.stat(follow_symlinks=False).st_size if entry.is_file(follow_symlinks=False) else 0
            })

        total = sum(1 for _ in os.scandir(op_path))
        return json.dumps({"success": True, "data": {"items": items, "total": total}}, ensure_ascii=False)

    def _do_search(self, op_path, pattern, recursive, request_id):
        import json
        if not pattern:
            return json.dumps({"success": False, "error": "INVALID_PATH", "message": "search 需要 pattern 参数"}, ensure_ascii=False)

        if recursive:
            search_pattern = os.path.join(op_path, '**', pattern)
        else:
            search_pattern = os.path.join(op_path, pattern)

        matches = glob_mod.glob(search_pattern, recursive=recursive)
        return json.dumps({"success": True, "data": {"matches": matches[:200], "count": len(matches)}}, ensure_ascii=False)

    def _do_find_replace(self, check_path, op_path, old, new, encoding, request_id, confirmed=False):
        import json
        if not old:
            return json.dumps({"success": False, "error": "INVALID_PATH", "message": "find_replace 需要 old 参数"}, ensure_ascii=False)
        if not os.path.exists(op_path):
            return json.dumps({"success": False, "error": "FILE_NOT_FOUND", "message": f"文件不存在: {op_path}"}, ensure_ascii=False)
        if os.path.isdir(op_path):
            return json.dumps({"success": False, "error": "PATH_IS_DIRECTORY", "message": f"路径是目录: {op_path}"}, ensure_ascii=False)
        if _is_binary(op_path, op_path):
            return json.dumps({"success": False, "error": "BINARY_FILE_NOT_SUPPORTED", "message": "不支持操作二进制文件"}, ensure_ascii=False)

        size = os.path.getsize(op_path)
        if size > 500 * 1024:
            return json.dumps({"success": False, "error": "FILE_TOO_LARGE", "message": f"文件过大({size}字节)，find_replace 限制 500KB"}, ensure_ascii=False)

        if not confirmed and self._needs_confirm('find_replace', check_path):
            return json.dumps({
                "type": "confirm", "request_id": request_id, "action": "find_replace",
                "path": op_path, "message": f"确认在 {op_path} 中将 '{old}' 替换为 '{new}'？"
            }, ensure_ascii=False)

        with open(op_path, 'r', encoding=encoding, errors='replace') as f:
            content = f.read()

        new_content = content.replace(old, new)
        replacements = content.count(old)

        if len(new_content.encode(encoding)) > 1024 * 1024:
            return json.dumps({"success": False, "error": "FILE_TOO_LARGE", "message": "替换后文件超过 1MB"}, ensure_ascii=False)

        with open(op_path, 'w', encoding=encoding) as f:
            f.write(new_content)

        _audit_log(request_id, 'find_replace', op_path, 'success', trust_mode=self._get_trust_mode())
        preview = new_content[:500]
        return json.dumps({"success": True, "data": {"replacements": replacements, "preview": preview}}, ensure_ascii=False)

    def _do_delete(self, check_path, op_path, recursive, request_id, confirmed=False):
        import json
        if not os.path.exists(op_path):
            return json.dumps({"success": False, "error": "FILE_NOT_FOUND", "message": f"路径不存在: {op_path}"}, ensure_ascii=False)

        is_dir = os.path.isdir(op_path)

        if is_dir and recursive:
            file_count = 0
            dir_count = 0
            for root, dirs, files in os.walk(op_path):
                for name in files + dirs:
                    child = os.path.join(root, name)
                    child_check = _normalize_for_check(child)
                    if _is_forbidden(child_check):
                        return json.dumps({"success": False, "error": "PATH_FORBIDDEN",
                            "message": f"目录内包含禁止访问的路径: {child}"}, ensure_ascii=False)
                    if os.path.isdir(os.path.join(root, name)):
                        dir_count += 1
                    else:
                        file_count += 1

            if not confirmed and self._needs_confirm('delete', check_path, is_recursive_delete=True):
                return json.dumps({
                    "type": "confirm", "request_id": request_id, "action": "delete",
                    "path": op_path,
                    "message": f"确认递归删除目录 {op_path}？（含 {file_count} 个文件, {dir_count} 个子目录）",
                    "file_count": file_count, "dir_count": dir_count
                }, ensure_ascii=False)

            shutil.rmtree(op_path)
        elif is_dir and not recursive:
            return json.dumps({"success": False, "error": "PATH_IS_DIRECTORY",
                "message": f"路径是目录，需要 recursive=true 才能删除: {op_path}"}, ensure_ascii=False)
        else:
            if not confirmed and self._needs_confirm('delete', check_path):
                return json.dumps({
                    "type": "confirm", "request_id": request_id, "action": "delete",
                    "path": op_path, "message": f"确认删除文件 {op_path}？"
                }, ensure_ascii=False)
            os.remove(op_path)

        _audit_log(request_id, 'delete', op_path, 'success', trust_mode=self._get_trust_mode())
        return json.dumps({"success": True, "data": {"deleted": True}}, ensure_ascii=False)

    def _do_info(self, op_path, request_id):
        import json
        if not os.path.exists(op_path) and not os.path.islink(op_path):
            return json.dumps({"success": False, "error": "FILE_NOT_FOUND", "message": f"路径不存在: {op_path}"}, ensure_ascii=False)

        stat = os.lstat(op_path)
        if os.path.islink(op_path):
            ftype = 'symlink'
        elif os.path.isdir(op_path):
            ftype = 'dir'
        else:
            ftype = 'file'

        perms = oct(stat.st_mode & 0o777)
        return json.dumps({"success": True, "data": {
            "size": stat.st_size,
            "modified": int(stat.st_mtime),
            "type": ftype,
            "permissions": perms,
            "is_symlink": os.path.islink(op_path)
        }}, ensure_ascii=False)


def register(registry):
    registry.register(FileManagerTool())
