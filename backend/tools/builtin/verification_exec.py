import asyncio
import os
import re
import shlex
import shutil
import subprocess
from pathlib import Path

from tools.base import BaseTool, ToolContext
from tools.builtin.code_exec import MAX_TIMEOUT_SECONDS, _run_process
from tools.paths import ToolPathError, resolve_tool_path
from tools.results import tool_error, tool_result


SHELL_META_PATTERN = re.compile(r"[;&|><`\r\n]")
DIRECT_TOOLS = {"tsc", "pytest", "unittest", "vitest", "jest", "eslint", "ruff", "mypy"}
PACKAGE_SCRIPTS = {"test", "build", "lint"}
BLOCKED_ARGUMENTS = {"--fix", "--write", "--update-snapshots", "-u"}
CHECK_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,39}$")


def _is_test_command(kind: str, arguments: list[str]) -> bool:
    if kind in {"pytest", "unittest", "python:pytest", "python:unittest", "vitest", "jest"}:
        return True
    if kind in {"npm", "pnpm", "yarn"}:
        script = [str(value).lower() for value in arguments]
        return "test" in script or (len(script) > 1 and script[0] == "run" and script[1] == "test")
    return kind in {"cargo", "go", "dotnet", "mvn", "gradle", "gradlew"} and bool(arguments) and arguments[0] == "test"


def _count_test_results(kind: str, output: str) -> int | None:
    text = str(output or "")
    if kind in {"unittest", "python:unittest"}:
        match = re.search(r"\bRan\s+(\d+)\s+tests?\b", text, re.IGNORECASE)
        return int(match.group(1)) if match else None
    if kind in {"pytest", "python:pytest"}:
        match = re.search(r"\bcollected\s+(\d+)\s+items?\b", text, re.IGNORECASE)
        if match:
            return int(match.group(1))
        counts = [int(value) for value in re.findall(
            r"\b(\d+)\s+(?:passed|failed|skipped|xfailed|xpassed|error|errors)\b",
            text, re.IGNORECASE,
        )]
        return sum(counts) if counts else None
    if kind in {"vitest", "jest"}:
        patterns = (
            r"\bTests?:\s+.*?\b(\d+)\s+total\b",
            r"\bTests?\s+(\d+)\s+(?:passed|failed)\b",
        )
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                return int(match.group(1))
    if kind in {"npm", "pnpm", "yarn"}:
        patterns = (
            r"\bTests?:\s+.*?\b(\d+)\s+total\b",
            r"\bTests?\s+(\d+)\s+(?:passed|failed)\b",
            r"\bRan\s+(\d+)\s+tests?\b",
            r"\bcollected\s+(\d+)\s+items?\b",
        )
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                return int(match.group(1))
    return None


def _analyze_verification_output(kind: str, arguments: list[str], output: str) -> dict:
    if not _is_test_command(kind, arguments):
        return {
            "verification_quality": "not_applicable",
            "tests_discovered": None,
            "tests_executed": None,
            "test_count": None,
        }
    text = str(output or "")
    empty_markers = (
        r"\bRan\s+0\s+tests?\b",
        r"\bno\s+tests?\s+(?:ran|collected|found)\b",
        r"\bno\s+test\s+files?\b",
        r"\bcollected\s+0\s+items?\b",
        r"\b0\s+tests?\b",
    )
    count = _count_test_results(kind, text)
    empty = any(re.search(marker, text, re.IGNORECASE) for marker in empty_markers)
    if count == 0 or empty:
        quality, discovered, executed = "empty", False, 0
    elif count is not None and count > 0:
        quality, discovered, executed = "meaningful", True, count
    else:
        quality, discovered, executed = "unknown", None, None
    return {
        "verification_quality": quality,
        "tests_discovered": discovered,
        "tests_executed": executed,
        "test_count": count,
    }


def _strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def _parse_command(code: str) -> list[str]:
    if SHELL_META_PATTERN.search(code):
        raise ValueError("验证命令不允许使用分号、管道、重定向、反引号或换行")
    try:
        parts = [_strip_quotes(part) for part in shlex.split(code, posix=os.name != "nt")]
    except ValueError as exc:
        raise ValueError(f"验证命令格式无效: {exc}") from exc
    if not parts:
        raise ValueError("验证命令不能为空")
    return parts


def _validate_command(parts: list[str]) -> tuple[str, list[str]]:
    executable = Path(parts[0]).name.lower()
    if executable.endswith((".exe", ".cmd", ".bat")):
        executable = Path(executable).stem
    arguments = parts[1:]
    lowered = [argument.lower() for argument in arguments]
    if any(argument in BLOCKED_ARGUMENTS or argument.startswith("--fix=") for argument in lowered):
        raise ValueError("验证命令不允许使用会修改文件的参数")

    if executable == "npx":
        if not arguments or arguments[0].startswith("-"):
            raise ValueError("npx 必须直接指定允许的本地验证工具")
        executable = Path(arguments[0]).name.lower()
        arguments = arguments[1:]
        if executable not in DIRECT_TOOLS - {"pytest", "unittest", "ruff", "mypy"}:
            raise ValueError(f"npx 不允许启动验证工具: {executable}")
        return executable, arguments

    if executable in {"python", "python3", "py"}:
        if len(arguments) < 2 or arguments[0] != "-m" or arguments[1] not in {
            "pytest", "unittest", "mypy",
        }:
            raise ValueError("Python 仅允许通过 -m 运行 pytest、unittest 或 mypy")
        return f"python:{arguments[1]}", arguments[2:]

    if executable in DIRECT_TOOLS:
        return executable, arguments

    if executable == "npm":
        if not arguments:
            raise ValueError("npm 仅允许 test、run test、run build 或 run lint")
        if arguments[0] == "test":
            return "npm", arguments
        if len(arguments) >= 2 and arguments[0] == "run" and arguments[1] in PACKAGE_SCRIPTS:
            return "npm", arguments
        raise ValueError("npm 仅允许 test、run test、run build 或 run lint")

    if executable in {"pnpm", "yarn"}:
        if not arguments:
            raise ValueError(f"{executable} 仅允许 test、build 或 lint")
        script_index = 1 if arguments[0] == "run" else 0
        if len(arguments) > script_index and arguments[script_index] in PACKAGE_SCRIPTS:
            return executable, arguments
        raise ValueError(f"{executable} 仅允许 test、build 或 lint")

    allowed_prefixes = {
        "cargo": {"test", "check"},
        "go": {"test"},
        "dotnet": {"test", "build"},
        "mvn": {"test"},
        "gradle": {"test"},
        "gradlew": {"test"},
    }
    if executable in allowed_prefixes:
        if arguments and arguments[0] in allowed_prefixes[executable]:
            return executable, arguments
        raise ValueError(f"{executable} 子命令不在验证白名单中")

    raise ValueError(f"不允许执行验证命令: {executable}")


def _local_node_binary(workdir: Path, workspace: Path, name: str) -> Path | None:
    suffixes = [".cmd", ".exe", ""] if os.name == "nt" else [""]
    current = workdir
    while True:
        for suffix in suffixes:
            candidate = current / "node_modules" / ".bin" / f"{name}{suffix}"
            if candidate.is_file():
                return candidate
        if current == workspace or workspace not in current.parents:
            break
        current = current.parent
    return None


def _resolve_executable(kind: str, workdir: Path, workspace: Path) -> tuple[str, list[str]]:
    if kind.startswith("python:"):
        return shutil.which("python") or shutil.which("python3") or "python", ["-m", kind.split(":", 1)[1]]

    node_tools = {"tsc", "vitest", "jest", "eslint"}
    if kind in node_tools:
        local = _local_node_binary(workdir, workspace, kind)
        if local:
            return str(local), []
    resolved = shutil.which(kind)
    if not resolved:
        raise FileNotFoundError(f"找不到验证工具: {kind}")
    return resolved, []


class VerificationExecTool(BaseTool):
    name = "verification_exec"
    description = (
        "运行只读意图的受限验证命令，用于测试、类型检查、lint 或构建。"
        "仅接受白名单工具和单个命令，禁止命令串联、重定向及修改参数；不能用于读取文件或执行任意脚本。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "单个验证命令，例如 npx tsc --noEmit、npm test、python -m pytest -q",
            },
            "check_id": {
                "type": "string",
                "description": "本轮计划内稳定的检查 ID，例如 typecheck 或 unit_tests；重试同一检查时必须保持一致",
            },
            "cwd": {
                "type": "string",
                "description": "工具工作区内的相对目录，默认工作区根目录",
            },
            "timeout": {
                "type": "integer",
                "minimum": 1,
                "maximum": MAX_TIMEOUT_SECONDS,
                "description": "超时秒数，默认 60，最大 120",
            },
        },
        "required": ["code", "check_id"],
        "additionalProperties": False,
    }

    async def execute(
        self,
        code: str = "",
        check_id: str = "",
        cwd: str = "",
        timeout: int = 60,
        _context: ToolContext | None = None,
        **kwargs,
    ) -> str:
        if not _context:
            return tool_error("MISSING_CONTEXT", "工具执行上下文不可用")
        if not _context.host_execution_enabled:
            return tool_error(
                "HOST_EXECUTION_DISABLED",
                "Host verification execution is disabled for this session.",
            )
        check_id = str(check_id or "").strip()
        if not CHECK_ID_PATTERN.fullmatch(check_id):
            return tool_error(
                "INVALID_VERIFICATION_CHECK_ID",
                "check_id 必须为 1 到 40 位字母、数字、下划线或连字符，并以字母或数字开头",
            )
        try:
            parts = _parse_command(str(code or "").strip())
            kind, arguments = _validate_command(parts)
        except ValueError as exc:
            return tool_error("VERIFICATION_COMMAND_DENIED", str(exc))

        try:
            workdir = resolve_tool_path(_context, cwd).check_path
        except ToolPathError as exc:
            return tool_error("WORKSPACE_VIOLATION", str(exc))
        if not workdir.is_dir():
            return tool_error("INVALID_CWD", f"工作目录不存在: {cwd or '.'}")
        try:
            timeout = max(1, min(int(timeout), MAX_TIMEOUT_SECONDS))
            executable, prefix = _resolve_executable(kind, workdir, _context.workspace)
        except (TypeError, ValueError):
            return tool_error("INVALID_TIMEOUT", "timeout 必须是整数")
        except FileNotFoundError as exc:
            return tool_error("VERIFICATION_TOOL_NOT_FOUND", str(exc))

        command = [executable, *prefix, *arguments]
        if os.name == "nt" and Path(executable).suffix.lower() in {".cmd", ".bat"}:
            command = ["cmd.exe", "/D", "/S", "/C", subprocess.list2cmdline(command)]
        try:
            result = await asyncio.to_thread(
                _run_process, command, workdir, timeout, _context.stop_event,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            return tool_error("EXECUTION_FAILED", str(exc))

        data = {
            "output": result["output"],
            "exit_code": result["returncode"],
            "truncated": result["truncated"],
            "output_bytes": result["output_bytes"],
            "cwd": str(workdir),
            "verification_kind": kind,
            "check_id": check_id,
        }
        data.update(_analyze_verification_output(kind, arguments, result["output"]))
        if result["cancelled"]:
            return tool_error("CANCELLED", "验证已停止，进程已终止", data=data)
        if result["timed_out"]:
            return tool_error("TIMEOUT", f"验证超过 {timeout} 秒，进程已终止", data=data)
        if result["returncode"] != 0:
            return tool_error("PROCESS_EXIT", f"验证进程退出码: {result['returncode']}", data=data)
        return tool_result(True, data=data, message="验证完成")


def register(registry):
    registry.register(VerificationExecTool())
