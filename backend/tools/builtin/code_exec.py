import asyncio
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
import tempfile
import uuid
import re
from pathlib import Path

from tools.base import BaseTool, ToolContext
from tools.paths import ToolPathError, resolve_tool_path
from tools.results import tool_confirm, tool_error, tool_result


DEFAULT_MAX_OUTPUT_BYTES = 100_000
MIN_OUTPUT_BYTES = 12_000
MAX_OUTPUT_BYTES = 500_000
MAX_TIMEOUT_SECONDS = 300
SENSITIVE_ENV_PARTS = (
    "KEY", "TOKEN", "SECRET", "PASSWORD", "PASS", "CREDENTIAL", "AUTH",
    "COOKIE", "SESSION", "PRIVATE", "SSH", "AWS", "AZURE", "GOOGLE",
    "GITHUB", "NPM", "DOCKER", "KUBE", "PROXY",
)
BROAD_GIT_STAGE_PATTERN = re.compile(r"\bgit\s+add\s+(?:-A|--all|\.)(?:\s|$)", re.IGNORECASE)


def _safe_environment(runtime_home: Path | None = None) -> dict[str, str]:
    environment = {}
    for key, value in os.environ.items():
        if any(part in key.upper() for part in SENSITIVE_ENV_PARTS):
            continue
        environment[key] = value
    environment["PYTHONIOENCODING"] = "utf-8"
    environment["PYTHONUTF8"] = "1"
    environment.pop("PYTHONPATH", None)
    environment.pop("VIRTUAL_ENV", None)
    if runtime_home is not None:
        home = str(runtime_home)
        environment.update({
            "HOME": home,
            "USERPROFILE": home,
            "APPDATA": home,
            "LOCALAPPDATA": home,
            "TMP": home,
            "TEMP": home,
        })
    if os.name != "nt":
        environment["LC_ALL"] = "C.UTF-8"
        environment["LANG"] = "C.UTF-8"
    return environment


def _decode_output(output_bytes: bytes) -> str:
    utf8 = output_bytes.decode("utf-8", errors="replace")
    if "�" not in utf8:
        return utf8
    legacy = output_bytes.decode("gb18030", errors="replace")
    return legacy if legacy.count("�") < utf8.count("�") else utf8


def _terminate_process_tree(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            capture_output=True,
            check=False,
            timeout=10,
        )
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def _run_process(command: list[str], cwd: Path, timeout: int, max_output_bytes: int, stop_event=None) -> dict:
    creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    runtime_home = Path(tempfile.mkdtemp(prefix="versena-exec-"))
    process = None
    try:
        process = subprocess.Popen(
            command,
            cwd=str(cwd),
            env=_safe_environment(runtime_home),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            creationflags=creationflags,
            start_new_session=os.name != "nt",
        )
        captured = bytearray()
        tail = bytearray()
        output_size = 0
        max_output_bytes = max(MIN_OUTPUT_BYTES, min(int(max_output_bytes), MAX_OUTPUT_BYTES))
        # Reserve space for the truncation marker so the returned payload never
        # exceeds the user-configured output limit.
        marker_reserve = min(512, max_output_bytes // 4)
        head_bytes = max(1, int((max_output_bytes - marker_reserve) * 0.5))
        tail_bytes = max(1, max_output_bytes - marker_reserve - head_bytes)

        def drain_output():
            nonlocal output_size
            while True:
                chunk = process.stdout.read(8192)
                if not chunk:
                    break
                output_size += len(chunk)
                if len(captured) < max_output_bytes:
                    captured.extend(chunk[:max_output_bytes - len(captured)])
                tail.extend(chunk)
                if len(tail) > tail_bytes:
                    del tail[:-tail_bytes]

        reader = threading.Thread(target=drain_output, daemon=True)
        reader.start()
        timed_out = False
        cancelled = False
        deadline = time.monotonic() + timeout
        while process.poll() is None:
            if stop_event is not None and stop_event.is_set():
                cancelled = True
                _terminate_process_tree(process)
                break
            if time.monotonic() >= deadline:
                timed_out = True
                _terminate_process_tree(process)
                break
            time.sleep(0.05)
        reader.join(timeout=5)
        if reader.is_alive() and process.stdout:
            process.stdout.close()
            reader.join(timeout=1)

        truncated = output_size > max_output_bytes
        if truncated:
            omitted = max(0, output_size - head_bytes - len(tail))
            marker = f"\n\n[输出已截断：中间省略 {omitted} 字节；以下为末尾内容]\n\n".encode("utf-8")
            output_bytes = bytes(captured[:head_bytes]) + marker + bytes(tail)
        else:
            output_bytes = bytes(captured)
        output = _decode_output(output_bytes).rstrip()
        return {
            "returncode": process.returncode,
            "output": output or "(无输出)",
            "truncated": truncated,
            "output_bytes": output_size,
            "captured_head_bytes": min(output_size, head_bytes if truncated else max_output_bytes),
            "captured_tail_bytes": len(tail) if truncated else 0,
            "timed_out": timed_out,
            "cancelled": cancelled,
        }
    finally:
        if process is not None and process.poll() is None:
            _terminate_process_tree(process)
        shutil.rmtree(runtime_home, ignore_errors=True)


class CodeExecTool(BaseTool):
    name = "code_exec"
    description = (
        "在所选工作目录中执行一次性的 Python 代码或 Shell 命令。不要用它分段读取文件，"
        "文件读取和搜索应优先使用 file_manager。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "language": {
                "type": "string",
                "enum": ["python", "shell"],
                "description": "执行类型，必须明确指定 python 或 shell",
            },
            "code": {"type": "string", "description": "要执行的代码或命令"},
            "cwd": {"type": "string", "description": "工具工作区内的相对目录，默认工作区根目录"},
            "timeout": {
                "type": "integer",
                "minimum": 1,
                "maximum": MAX_TIMEOUT_SECONDS,
                "description": "超时秒数，默认使用高级设置，最大 300",
            },
        },
        "required": ["language", "code"],
        "additionalProperties": False,
    }

    async def execute(
        self,
        language: str = "",
        code: str = "",
        cwd: str = "",
        timeout: int | None = None,
        _context: ToolContext | None = None,
        _confirmed: bool = False,
        **kwargs,
    ) -> str:
        if language not in {"python", "shell"}:
            return tool_error("INVALID_LANGUAGE", "language 必须是 python 或 shell")
        code = self._strip_code_fence(code)
        if not code:
            return tool_error("EMPTY_CODE", "没有提供要执行的代码")
        if not _context:
            return tool_error("MISSING_CONTEXT", "工具执行上下文不可用")
        if language == "shell" and BROAD_GIT_STAGE_PATTERN.search(code):
            return tool_error(
                "BROAD_REPO_STAGE_BLOCKED",
                "禁止使用 git add -A、git add --all 或无范围的 git add .；请先确认仓库根目录，再暂存明确的文件路径",
            )

        try:
            workdir = resolve_tool_path(_context, cwd).check_path
        except ToolPathError as exc:
            return tool_error("WORKSPACE_VIOLATION", str(exc))
        if not workdir.is_dir():
            return tool_error("INVALID_CWD", f"工作目录不存在: {cwd or '.'}")

        default_timeout = ((_context.agent_config or {}).get("tool_timeout", 30)
                           if timeout is None else timeout)
        try:
            timeout = max(1, min(int(default_timeout), MAX_TIMEOUT_SECONDS))
        except (TypeError, ValueError):
            return tool_error("INVALID_TIMEOUT", "timeout 必须是整数")

        if not _confirmed and not _context.trust_mode:
            preview = code.replace("\n", " ")[:160]
            return tool_confirm(
                str(uuid.uuid4()),
                "code_exec",
                f"确认执行 {language}？\n{preview}",
                language=language,
                cwd=str(workdir),
                code=code,
                security_warning=(
                    "该命令将以当前系统用户身份运行，可能访问工作区之外的数据。"
                    "批准前请检查下方完整命令。"
                ),
            )

        if language == "python":
            command = [sys.executable, "-c", code]
        elif os.name == "nt":
            command = ["cmd.exe", "/D", "/S", "/C", code]
        else:
            shell = shutil.which("bash") or shutil.which("sh")
            if not shell:
                return tool_error("SHELL_NOT_FOUND", "找不到可用的 Shell")
            command = [shell, "-lc", code]

        try:
            max_output_bytes = self._output_limit(_context.agent_config)
            result = await asyncio.to_thread(
                _run_process,
                command,
                workdir,
                timeout,
                max_output_bytes,
                _context.stop_event,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            return tool_error("EXECUTION_FAILED", str(exc))

        data = {
            "output": result["output"],
            "exit_code": result["returncode"],
            "truncated": result["truncated"],
            "output_bytes": result["output_bytes"],
            "language": language,
            "cwd": str(workdir),
        }
        if result["cancelled"]:
            return tool_error("CANCELLED", "执行已停止，进程已终止", data=data)
        if result["timed_out"]:
            return tool_error("TIMEOUT", f"执行超过 {timeout} 秒，进程已终止", data=data)
        if result["returncode"] != 0:
            return tool_error("PROCESS_EXIT", f"进程退出码: {result['returncode']}", data=data)
        return tool_result(True, data=data, message="执行完成")

    @staticmethod
    def _output_limit(agent_config) -> int:
        try:
            value = int((agent_config or {}).get("code_exec_output_max_bytes", DEFAULT_MAX_OUTPUT_BYTES))
        except (TypeError, ValueError):
            value = DEFAULT_MAX_OUTPUT_BYTES
        return max(MIN_OUTPUT_BYTES, min(value, MAX_OUTPUT_BYTES))

    @staticmethod
    def _strip_code_fence(code: str) -> str:
        value = (code or "").strip()
        if value.startswith("```"):
            first_newline = value.find("\n")
            value = value[first_newline + 1:] if first_newline >= 0 else ""
        if value.endswith("```"):
            value = value[:-3]
        return value.strip()


def register(registry):
    registry.register(CodeExecTool())
