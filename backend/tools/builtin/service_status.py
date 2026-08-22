"""Read-only service/port identity checks for long-running tasks."""

from __future__ import annotations

import asyncio
import os
import re
import socket
import subprocess
import time
from pathlib import Path

from tools.base import BaseTool, ToolContext
from tools.results import tool_error, tool_result


PORT_RE = re.compile(r":(?P<port>\d+)\s+")
WINDOWS_LISTENER_RE = re.compile(
    r"^\s*TCP\s+\S+:(?P<port>\d+)\s+\S+\s+LISTENING\s+(?P<pid>\d+)\s*$",
    re.IGNORECASE,
)


def _netstat_listeners(port: int) -> list[dict]:
    """Return listeners without invoking a shell or modifying the host."""
    commands = [["netstat", "-ano", "-p", "tcp"]]
    if os.name != "nt":
        commands = [["ss", "-ltnp"], ["netstat", "-ltnp"]]
    for command in commands:
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=3,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            continue
        listeners = []
        for line in completed.stdout.splitlines():
            if os.name == "nt":
                match = WINDOWS_LISTENER_RE.match(line)
                if not match or int(match.group("port")) != port:
                    continue
                listeners.append({"address": line.split()[1], "pid": int(match.group("pid"))})
                continue
            match = re.search(r"(?:::|0\.0\.0\.0:|127\.0\.0\.1:)(\d+)", line)
            if not match or int(match.group(1)) != port:
                continue
            pid_match = re.search(r"pid=(\d+)", line)
            listeners.append({
                "address": line.split()[3] if len(line.split()) > 3 else "",
                "pid": int(pid_match.group(1)) if pid_match else None,
            })
        if listeners:
            return listeners
    return []


def _pid_alive(pid: int | None) -> bool | None:
    if not pid or pid <= 0:
        return None
    if os.name == "nt":
        # Sending signal 0 is not a harmless process probe on every Windows
        # host (and can surface protected PIDs as SystemError). Query the
        # process table instead; this does not signal or terminate anything.
        try:
            completed = subprocess.run(
                ["tasklist", "/FI", f"PID eq {int(pid)}", "/FO", "CSV", "/NH"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=3,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        if completed.returncode != 0:
            return None
        target = f'"{int(pid)}"'
        return any(target in line for line in completed.stdout.splitlines())
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except (OSError, SystemError):
        # Windows can surface a protected/system PID as SystemError with an
        # underlying access-denied exception.  Port status remains useful even
        # when the PID liveness probe is unavailable.
        return None


def _inspect(port: int, host: str, timeout: float) -> dict:
    started = time.monotonic()
    listeners = _netstat_listeners(port)
    reachable = False
    connection_error = ""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            reachable = True
    except OSError as exc:
        connection_error = str(exc)
    for listener in listeners:
        listener["pid_alive"] = _pid_alive(listener.get("pid"))
    return {
        "host": host,
        "port": port,
        # A local socket can be reachable even when netstat/ss is unavailable
        # or its output is restricted.  Treat that as listening while keeping
        # the listener/PID fields explicitly unknown.
        "listening": bool(listeners) or reachable,
        "reachable": reachable,
        "listeners": listeners[:16],
        "pid": next((item.get("pid") for item in listeners if item.get("pid")), None),
        "connection_error": connection_error,
        "checked_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "elapsed_ms": round((time.monotonic() - started) * 1000),
    }


class ServiceStatusTool(BaseTool):
    name = "service_status"
    description = (
        "只读检查本机端口是否仍由服务监听，并返回监听地址、PID、PID 存活状态和检查时间。"
        "它只确认端口状态；需要确认服务身份和版本时继续使用 runtime_smoke。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "port": {"type": "integer", "minimum": 1, "maximum": 65535},
            "host": {"type": "string", "description": "检查地址，默认 127.0.0.1"},
            "timeout": {"type": "number", "minimum": 0.1, "maximum": 5},
        },
        "required": ["port"],
        "additionalProperties": False,
    }

    async def execute(
        self,
        port: int = 0,
        host: str = "127.0.0.1",
        timeout: float = 1.0,
        _context: ToolContext | None = None,
        **kwargs,
    ) -> str:
        if _context is None:
            return tool_error("MISSING_CONTEXT", "服务状态检查需要工具上下文")
        try:
            port = int(port)
            timeout = max(0.1, min(float(timeout), 5.0))
        except (TypeError, ValueError):
            return tool_error("INVALID_PORT", "port 和 timeout 必须是有效数字")
        if not 1 <= port <= 65535:
            return tool_error("INVALID_PORT", "port 必须在 1 到 65535 之间")
        host = str(host or "127.0.0.1").strip()
        if host not in {"127.0.0.1", "localhost", "::1"}:
            return tool_error("INVALID_HOST", "service_status 只允许检查本机地址")
        data = await asyncio.to_thread(_inspect, port, "127.0.0.1" if host == "localhost" else host, timeout)
        if not data["listening"]:
            return tool_error("SERVICE_NOT_LISTENING", f"端口 {port} 当前没有监听服务", data=data)
        return tool_result(True, data=data, message="服务端口状态检查完成")


def register(registry):
    registry.register(ServiceStatusTool())
