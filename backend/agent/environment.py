import os
import platform
import subprocess
from pathlib import Path


def _run_git(workspace: Path, args: list[str]) -> str:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=str(workspace),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=2,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


def collect_environment_facts(workspace: Path) -> dict[str, str]:
    workspace = workspace.expanduser().resolve()
    git_root = _run_git(workspace, ["rev-parse", "--show-toplevel"])
    branch = _run_git(workspace, ["branch", "--show-current"])
    dirty = ""
    if git_root:
        dirty = _run_git(workspace, ["status", "--porcelain", "--untracked-files=no"])

    return {
        "os": platform.system() or os.name,
        "os_version": platform.release(),
        "python": platform.python_version(),
        "tool_shell": "cmd.exe" if os.name == "nt" else (os.environ.get("SHELL") or "sh"),
        "workspace": str(workspace),
        "git_root": git_root or "不是 Git 仓库或无法读取",
        "git_branch": branch or "未知",
        "git_dirty": "有已跟踪改动" if dirty else ("干净" if git_root else "未知"),
    }


def format_environment_facts(facts: dict[str, str]) -> str:
    labels = {
        "os": "操作系统",
        "os_version": "系统版本",
        "python": "Python",
        "tool_shell": "code_exec 实际 Shell",
        "workspace": "工具工作目录",
        "git_root": "Git 仓库根目录",
        "git_branch": "当前分支",
        "git_dirty": "Git 状态",
    }
    return "\n".join(
        f"- {labels.get(key, key)}：{value}"
        for key, value in facts.items()
        if value
    )
