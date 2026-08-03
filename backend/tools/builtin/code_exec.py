import asyncio
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

from tools.base import BaseTool, ToolContext
from tools.paths import ToolPathError, resolve_tool_path
from tools.results import tool_confirm, tool_error, tool_result


MAX_OUTPUT_BYTES = 12_000
MAX_TIMEOUT_SECONDS = 120
SENSITIVE_ENV_PARTS = ("KEY", "TOKEN", "SECRET", "PASSWORD", "CREDENTIAL")


def _safe_environment() -> dict[str, str]:
    environment = {}
    for key, value in os.environ.items():
        if any(part in key.upper() for part in SENSITIVE_ENV_PARTS):
            continue
        environment[key] = value
    environment["PYTHONIOENCODING"] = "utf-8"
    return environment


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


def _run_process(command: list[str], cwd: Path, timeout: int, stop_event=None) -> dict:
    creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    process = subprocess.Popen(
        command,
        cwd=str(cwd),
        env=_safe_environment(),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        creationflags=creationflags,
        start_new_session=os.name != "nt",
    )
    captured = bytearray()
    output_size = 0

    def drain_output():
        nonlocal output_size
        while True:
            chunk = process.stdout.read(8192)
            if not chunk:
                break
            output_size += len(chunk)
            if len(captured) < MAX_OUTPUT_BYTES:
                captured.extend(chunk[:MAX_OUTPUT_BYTES - len(captured)])

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

    output = bytes(captured).decode("utf-8", errors="replace").rstrip()
    return {
        "returncode": process.returncode,
        "output": output or "(无输出)",
        "truncated": output_size > MAX_OUTPUT_BYTES,
        "output_bytes": output_size,
        "timed_out": timed_out,
        "cancelled": cancelled,
    }


class CodeExecTool(BaseTool):
    name = "code_exec"
    description = "在受限工作目录中执行一次性的 Python 代码或 Shell 命令；每次执行都需要用户确认。"
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
                "description": "超时秒数，默认 30，最大 120",
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
        timeout: int = 30,
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

        try:
            workdir = resolve_tool_path(_context, cwd).check_path
        except ToolPathError as exc:
            return tool_error("WORKSPACE_VIOLATION", str(exc))
        if not workdir.is_dir():
            return tool_error("INVALID_CWD", f"工作目录不存在: {cwd or '.'}")

        try:
            timeout = max(1, min(int(timeout), MAX_TIMEOUT_SECONDS))
        except (TypeError, ValueError):
            return tool_error("INVALID_TIMEOUT", "timeout 必须是整数")

        if not _confirmed:
            preview = code.replace("\n", " ")[:160]
            return tool_confirm(
                str(uuid.uuid4()),
                "code_exec",
                f"确认执行 {language}？\n{preview}",
                language=language,
                cwd=str(workdir),
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
            result = await asyncio.to_thread(
                _run_process,
                command,
                workdir,
                timeout,
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
