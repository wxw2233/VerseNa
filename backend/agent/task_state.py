"""Task-level state, worktree baseline and completion evidence.

This is deliberately deterministic.  A model may update a checkpoint through
the tool, but state transitions, provenance and recovery checks are validated
by the application before they are injected into later turns.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agent.context_protocol import classify_error, utc_now


TASK_STATE_VERSION = 3
MAX_ITEMS = 24
MAX_TEXT = 1_500
MAX_WORKSPACE_SNAPSHOT_FILES = 4_000
WORKSPACE_SNAPSHOT_IGNORED_DIRS = {
    ".git", ".hg", ".svn", "node_modules", ".venv", "venv", "env",
    "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    "dist", "build", "coverage", ".cache",
}
VALID_PHASES = {
    "created", "investigating", "implementing", "validating", "blocked",
    "paused", "completed", "abandoned",
}
GOAL_MODES = {
    "new", "continue", "refine", "append", "replace", "shrink",
    "report_only", "pause",
}
MESSAGE_MODES = GOAL_MODES | {"compact"}
BOUNDARY_CASE_KINDS = {
    "empty_state", "limit_state", "rapid_repeat", "invalid_input",
    "interrupt_recovery", "resource_shortage", "concurrent_change",
}
PHASE_ALIASES = {
    "创建": "created", "调查": "investigating", "探索": "investigating",
    "实现": "implementing", "修改": "implementing", "开发": "implementing",
    "验证": "validating", "验收": "validating", "阻塞": "blocked",
    "暂停": "paused", "完成": "completed", "已完成": "completed",
    "废弃": "abandoned", "放弃": "abandoned",
}
TERMINAL_PHASES = {"completed", "abandoned"}
ALLOWED_TRANSITIONS = {
    "created": {"investigating", "blocked", "paused", "abandoned"},
    "investigating": {"implementing", "validating", "blocked", "paused", "completed", "abandoned"},
    "implementing": {"investigating", "validating", "blocked", "paused", "abandoned"},
    "validating": {"investigating", "implementing", "blocked", "paused", "completed", "abandoned"},
    "blocked": {"investigating", "paused", "abandoned"},
    "paused": {"investigating", "blocked", "abandoned"},
    "completed": {"created", "investigating"},
    "abandoned": {"created", "investigating"},
}

CONTINUATION_RE = re.compile(
    r"^\s*(继续|continue|接着|下一步|再试|恢复|好|好的|ok|嗯|行|开始吧|按.*计划|"
    r"/compact)\s*[。！!，,]*\s*$",
    re.IGNORECASE,
)
PAUSE_RE = re.compile(
    r"(?:暂停|先别(?:改|做|动)|停止(?:任务|执行)?|只(?:看|报告|分析)|"
    r"不要(?:继续|修改)|不用(?:再)?(?:改|测试|继续|执行)|先这样(?:吧)?|就这样(?:吧)?)"
)
REPORT_ONLY_RE = re.compile(
    r"^(?:进度(?:如何|怎么样)?|当前状态(?:如何|怎么样)?|评价(?:一下)?|"
    r"看看(?:就行)?|检查一下(?:当前状态|这个问题)?|自检(?:一下)?|有没有问题\??)$"
)
NEGATIVE_RE = re.compile(r"(?:不要|禁止|别(?:再|去|动|改)|不允许|无需|不需要|仅|只)")
REPLACE_RE = re.compile(r"(?:改成|换成|替换|取消之前|不再(?:做|用)|放弃(?:之前|这个)|重新(?:开始|做))")
APPEND_RE = re.compile(r"(?:另外|再加|追加|同时|以及|还要|顺便)")
SHRINK_RE = re.compile(r"(?:只要|仅保留|缩小范围|先只|暂时只|不用(?:做|处理))")
ENGINEERING_RE = re.compile(
    r"(?:代码|项目|源码|文件|目录|模块|接口|前端|后端|测试|构建|编译|修复|实现|开发|部署|"
    r"bug|bugfix|refactor|typecheck|lint|build|npm|python|游戏|网页|服务|工具|架构)",
    re.IGNORECASE,
)


def _bounded(value: Any, limit: int = MAX_TEXT) -> str:
    text = str(value or "").replace("\x00", " ").strip()
    return text[:limit]


def _items(value: Any, *, limit: int = MAX_ITEMS, item_limit: int = 500) -> list[str]:
    if not isinstance(value, (list, tuple, set)):
        return []
    result: list[str] = []
    for item in value:
        text = _bounded(item, item_limit)
        if text and text not in result:
            result.append(text)
        if len(result) >= limit:
            break
    return result


def _normalize_boundary_cases(value: Any) -> list[dict[str, Any]]:
    """Normalize executable edge-case records without trusting model prose."""
    if not isinstance(value, (list, tuple)):
        return []
    result: list[dict[str, Any]] = []
    for item in value:
        if isinstance(item, str):
            item = {"id": item, "kind": item, "description": item}
        if not isinstance(item, dict):
            continue
        kind = _bounded(item.get("kind") or item.get("id"), 60).lower().replace("-", "_")
        if kind not in BOUNDARY_CASE_KINDS:
            continue
        status = str(item.get("status") or "unverified")
        if status not in {"verified", "partially_verified", "unverified", "blocked", "not_applicable"}:
            status = "unverified"
        normalized = {
            "id": kind,
            "kind": kind,
            "description": _bounded(item.get("description") or kind, 500),
            "status": status,
            "evidence": _bounded(item.get("evidence"), 700),
            "required": bool(item.get("required", True)),
            "at": _bounded(item.get("at"), 80) or utc_now(),
        }
        result.append(normalized)
    # Keep the latest record for each kind so a corrected result replaces an
    # earlier uncertain observation instead of accumulating contradictory rows.
    latest = {item["kind"]: item for item in result}
    return list(latest.values())[-len(BOUNDARY_CASE_KINDS):]


def _normalize_self_check(value: Any) -> dict[str, Any]:
    """Bound the self-check envelope stored in a user session checkpoint."""
    if not isinstance(value, dict):
        return {}
    result: dict[str, Any] = {}
    for key in (
        "generated_at", "workspace", "workspace_id", "current_goal",
        "goal_mode", "memory_scope", "latest_user_message", "next_step",
    ):
        if key in value:
            result[key] = _bounded(value.get(key), 1_000)
    for key in (
        "existing_user_changes", "agent_changes", "mixed_changes", "forbidden_actions",
        "approved_actions", "pending", "unverified", "blocking_reasons",
    ):
        result[key] = _items(value.get(key), limit=MAX_ITEMS, item_limit=500)
    for key in ("active_processes", "boundary_cases", "workspace_delta"):
        raw = value.get(key)
        if isinstance(raw, list):
            result[key] = [item for item in raw if isinstance(item, dict)][-12:]
        elif isinstance(raw, dict):
            result[key] = raw
    result["safe_to_continue"] = bool(value.get("safe_to_continue", False))
    result["requires_recovery"] = bool(value.get("requires_recovery", False))
    result["has_user_changes"] = bool(value.get("has_user_changes", False))
    return result


def _normalize_compaction(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    result = {}
    for key in ("phase", "reason", "message", "at", "mode"):
        if key in value:
            result[key] = _bounded(value.get(key), 500)
    for key in ("before_tokens", "after_tokens", "before_messages", "after_messages", "message_count"):
        try:
            if key in value:
                result[key] = max(0, int(value.get(key) or 0))
        except (TypeError, ValueError):
            continue
    result["compressed"] = bool(value.get("compressed", value.get("phase") == "done"))
    return result


def _normalize_project_index(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    result: dict[str, Any] = {}
    for key in (
        "index_version", "workspace", "generated_at", "source_revision",
        "source_revision_files", "source_revision_truncated", "truncated",
        "stale", "stale_reason", "file_count",
    ):
        if key in value:
            item = value.get(key)
            if isinstance(item, (str, int, float, bool)) or item is None:
                result[key] = _bounded(item, 500) if isinstance(item, str) else item
    for key in ("project_types", "top_level", "entrypoints", "scanned_paths", "ignored_paths"):
        result[key] = _items(value.get(key), limit=80, item_limit=300)
    scripts = value.get("scripts")
    if isinstance(scripts, dict):
        result["scripts"] = {
            _bounded(key, 100): _bounded(val, 500)
            for key, val in list(scripts.items())[:40]
        }
    return result


def default_boundary_cases(goal: str) -> list[dict[str, Any]]:
    """Return the minimum executable edge-case matrix for engineering work."""
    if not ENGINEERING_RE.search(str(goal or "")):
        return []
    descriptions = {
        "empty_state": "空状态：首次进入、没有数据或目标对象不存在时能安全结束",
        "limit_state": "极限状态：最大数量、最大输入或边界尺寸不会破坏布局/逻辑",
        "rapid_repeat": "快速重复：连续提交、点击、按键或重启不会重复副作用",
        "invalid_input": "异常输入：空值、非法值、超范围或损坏数据有明确错误",
        "interrupt_recovery": "中断恢复：停止、刷新、重连或服务重启后状态可恢复或明确失败",
        "resource_shortage": "资源不足：缺依赖、端口占用、浏览器不可用时给出可操作反馈",
        "concurrent_change": "并发变化：用户或子代理同时修改时不覆盖未知改动",
    }
    return [
        {
            "id": kind,
            "kind": kind,
            "description": description,
            "status": "unverified",
            "evidence": "",
            "required": True,
            "at": utc_now(),
        }
        for kind, description in descriptions.items()
    ]


def _merge_boundary_cases(
    current: Any,
    defaults: list[dict[str, Any]],
    *,
    reset: bool = False,
) -> list[dict[str, Any]]:
    """Keep verified edge-case evidence only when it still belongs to goal."""
    if reset:
        return _normalize_boundary_cases(defaults)
    previous = {
        item.get("kind"): item
        for item in _normalize_boundary_cases(current)
        if isinstance(item, dict) and item.get("kind")
    }
    merged = []
    for item in defaults:
        old = previous.get(item.get("kind"))
        merged.append(old if old and old.get("status") == "verified" else item)
    return _normalize_boundary_cases(merged)


def _append(values: list[str], value: Any, *, limit: int = MAX_ITEMS, item_limit: int = 500) -> None:
    text = _bounded(value, item_limit)
    if text and text not in values:
        values.append(text)
    if len(values) > limit:
        del values[:-limit]


def normalize_workspace(workspace: Path | str | None) -> str:
    if not workspace:
        return ""
    try:
        return str(Path(workspace).expanduser().resolve())
    except (OSError, TypeError, ValueError):
        return _bounded(workspace, 1_000)


def workspace_id(workspace: Path | str | None) -> str:
    value = normalize_workspace(workspace).lower()
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16] if value else ""


def _git(workspace: Path, *args: str) -> tuple[int, str]:
    try:
        completed = subprocess.run(
            ["git", *args], cwd=str(workspace), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=3, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return 1, ""
    return completed.returncode, completed.stdout.strip()


def capture_worktree_baseline(workspace: Path | str | None) -> dict[str, Any]:
    """Capture a bounded baseline without changing the worktree."""
    root = Path(normalize_workspace(workspace)) if workspace else None
    baseline: dict[str, Any] = {
        "captured_at": utc_now(),
        "workspace": str(root) if root else "",
        "workspace_id": workspace_id(root),
        "git": {"available": False, "branch": "", "head": "", "tracked": [], "untracked": []},
    }
    if not root or not root.is_dir():
        return baseline
    code, git_root = _git(root, "rev-parse", "--show-toplevel")
    if code != 0 or not git_root:
        return baseline
    _, branch = _git(root, "branch", "--show-current")
    _, head = _git(root, "rev-parse", "HEAD")
    _, porcelain = _git(root, "status", "--porcelain=v1", "--untracked-files=all")
    tracked, untracked = [], []
    for line in porcelain.splitlines()[:500]:
        path = line[3:].strip() if len(line) > 3 else line.strip()
        if not path:
            continue
        if line.startswith("??"):
            untracked.append(path)
        else:
            tracked.append(path)
    baseline["git"] = {
        "available": True,
        "root": git_root,
        "branch": branch,
        "head": head,
        "tracked": tracked[:MAX_ITEMS],
        "untracked": untracked[:MAX_ITEMS],
        "truncated": len(tracked) > MAX_ITEMS or len(untracked) > MAX_ITEMS,
    }
    return baseline


def capture_workspace_snapshot(
    workspace: Path | str | None,
    *,
    max_files: int = MAX_WORKSPACE_SNAPSHOT_FILES,
) -> dict[str, Any]:
    """Capture a bounded, content-free file snapshot for an executor audit.

    Git status alone cannot identify a second edit to a file that was already
    dirty before the subagent started.  The snapshot uses relative path, size
    and mtime_ns, so it is cheap enough for a task boundary and does not copy
    user file contents into a checkpoint or a model context.
    """
    root_text = normalize_workspace(workspace)
    root = Path(root_text) if root_text else None
    snapshot: dict[str, Any] = {
        "workspace": root_text,
        "workspace_id": workspace_id(root_text),
        "captured_at": utc_now(),
        "files": {},
        "file_count": 0,
        "truncated": False,
        "fingerprint": "",
    }
    if not root or not root.is_dir():
        return snapshot

    digest = hashlib.sha256()
    files: dict[str, str] = {}
    try:
        paths = root.rglob("*")
        for path in paths:
            if len(files) >= max(1, int(max_files)):
                snapshot["truncated"] = True
                break
            if not path.is_file():
                continue
            try:
                relative = path.relative_to(root)
                if any(part in WORKSPACE_SNAPSHOT_IGNORED_DIRS for part in relative.parts):
                    continue
                stat = path.stat()
            except OSError:
                continue
            relative_text = relative.as_posix()
            marker = f"{stat.st_size}:{getattr(stat, 'st_mtime_ns', int(stat.st_mtime * 1_000_000_000))}"
            files[relative_text] = marker
            digest.update(relative_text.encode("utf-8", "replace"))
            digest.update(marker.encode("ascii", "replace"))
    except OSError:
        snapshot["truncated"] = True

    snapshot["files"] = files
    snapshot["file_count"] = len(files)
    snapshot["fingerprint"] = digest.hexdigest()[:32]
    return snapshot


def diff_workspace_snapshots(
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
) -> dict[str, Any]:
    """Return the observable worktree delta between two executor snapshots."""
    before = before if isinstance(before, dict) else {}
    after = after if isinstance(after, dict) else {}
    before_files = before.get("files") if isinstance(before.get("files"), dict) else {}
    after_files = after.get("files") if isinstance(after.get("files"), dict) else {}
    created = sorted(set(after_files) - set(before_files))
    deleted = sorted(set(before_files) - set(after_files))
    modified = sorted(
        path for path in set(before_files) & set(after_files)
        if before_files.get(path) != after_files.get(path)
    )
    changed = sorted(set(created + modified + deleted))
    return {
        "workspace": after.get("workspace") or before.get("workspace") or "",
        "before_fingerprint": before.get("fingerprint") or "",
        "after_fingerprint": after.get("fingerprint") or "",
        "complete": not bool(before.get("truncated") or after.get("truncated")),
        "created": created,
        "modified": modified,
        "deleted": deleted,
        "changed": changed,
    }


def _default_state(
    workspace: Path | str | None = None,
    *,
    baseline: dict[str, Any] | None = None,
) -> dict[str, Any]:
    root = normalize_workspace(workspace)
    return {
        "version": TASK_STATE_VERSION,
        "task_id": f"task_{uuid.uuid4().hex}",
        "phase": "created",
        "phase_label": "created",
        "status": "active",
        "workspace": root,
        "workspace_id": workspace_id(root),
        "active_goal": "",
        "goal_version": 0,
        "goal_mode": "new",
        "goal_history": [],
        "superseded_goals": [],
        "scope": [],
        "completed": [],
        "pending": [],
        "user_decisions": [],
        "do_not_do": [],
        "approved_actions": [],
        "forbidden_actions": [],
        "verified": [],
        "inferred": [],
        "unverified": [],
        "resolved_failures": [],
        "failed_attempts": [],
        "files_changed_by_agent": [],
        "files_changed_by_user": [],
        "active_processes": [],
        "acceptance_matrix": [],
        "boundary_cases": [],
        "tool_events": [],
        "project_index": {},
        "context_conflicts": [],
        "baseline": baseline if isinstance(baseline, dict) else capture_worktree_baseline(root),
        "workspace_snapshot": capture_workspace_snapshot(root) if root and Path(root).is_dir() else {},
        "self_check": {},
        "last_compaction": {},
        "current": "",
        "next_step": "",
        "validation": "",
        "risk": "",
        "notes": "",
        "port": None,
        "pid": None,
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "last_generation_id": "",
        "last_finish_reason": "",
    }


def normalize_task_state(value: dict[str, Any] | None, workspace: Path | str | None = None) -> dict[str, Any]:
    """Upgrade legacy checkpoints and bound all model-controlled fields."""
    source = value if isinstance(value, dict) else {}
    root = normalize_workspace(workspace or source.get("workspace"))
    # Normalization happens on every streamed turn and checkpoint update.
    # Reusing the captured baseline avoids repeatedly spawning Git processes
    # while retaining the immutable task-start snapshot.
    baseline = source.get("baseline") if isinstance(source.get("baseline"), dict) else None
    state = _default_state(root, baseline=baseline)
    state["task_id"] = _bounded(source.get("task_id"), 80) or state["task_id"]
    phase_label = _bounded(source.get("phase_label") or source.get("phase"), 80)
    phase = _bounded(source.get("state_phase") or source.get("phase"), 40).lower()
    phase = PHASE_ALIASES.get(phase, phase)
    state["phase"] = phase if phase in VALID_PHASES else "investigating" if source else "created"
    state["state_phase"] = state["phase"]
    state["phase_label"] = phase_label or state["phase"]
    state["status"] = _bounded(source.get("status"), 40) or ("paused" if state["phase"] == "paused" else "active")
    state["workspace"] = root
    state["workspace_id"] = workspace_id(root)
    for key in ("active_goal", "current", "next_step", "validation", "risk", "notes", "last_generation_id", "last_finish_reason"):
        state[key] = _bounded(source.get(key), MAX_TEXT if key != "last_generation_id" else 100)
    goal_mode = _bounded(source.get("goal_mode"), 40).lower()
    state["goal_mode"] = goal_mode if goal_mode in GOAL_MODES else "new"
    try:
        state["goal_version"] = max(0, int(source.get("goal_version") or 0))
    except (TypeError, ValueError):
        state["goal_version"] = 0
    for key in (
        "goal_history", "superseded_goals", "scope", "completed", "pending", "user_decisions", "do_not_do",
        "approved_actions", "forbidden_actions",
        "verified", "inferred", "unverified", "failed_attempts", "files_changed_by_agent",
        "files_changed_by_user", "resolved_failures",
    ):
        state[key] = _items(source.get(key))
    state["active_processes"] = [item for item in (source.get("active_processes") or []) if isinstance(item, dict)][-12:]
    state["acceptance_matrix"] = [item for item in (source.get("acceptance_matrix") or []) if isinstance(item, dict)][-24:]
    state["boundary_cases"] = _normalize_boundary_cases(source.get("boundary_cases"))
    if not state["boundary_cases"] and state.get("active_goal"):
        state["boundary_cases"] = default_boundary_cases(state["active_goal"])
    state["tool_events"] = [item for item in (source.get("tool_events") or []) if isinstance(item, dict)][-20:]
    state["project_index"] = _normalize_project_index(source.get("project_index"))
    state["context_conflicts"] = [
        item for item in (source.get("context_conflicts") or []) if isinstance(item, dict)
    ][-12:]
    state["baseline"] = baseline if baseline is not None else capture_worktree_baseline(root)
    raw_snapshot = source.get("workspace_snapshot")
    state["workspace_snapshot"] = raw_snapshot if isinstance(raw_snapshot, dict) else (
        capture_workspace_snapshot(root) if root and Path(root).is_dir() else {}
    )
    state["self_check"] = _normalize_self_check(source.get("self_check"))
    state["last_compaction"] = _normalize_compaction(source.get("last_compaction"))
    for key in ("port", "pid"):
        try:
            state[key] = int(source.get(key)) if source.get(key) is not None else None
        except (TypeError, ValueError):
            state[key] = None
    state["created_at"] = _bounded(source.get("created_at"), 80) or state["created_at"]
    state["updated_at"] = utc_now()
    return state


def transition(state: dict[str, Any], phase: str, *, reason: str = "") -> bool:
    phase = _bounded(phase, 40).lower()
    current = state.get("phase", "created")
    if phase not in VALID_PHASES:
        return False
    if phase != current and phase not in ALLOWED_TRANSITIONS.get(current, set()):
        return False
    state["phase"] = phase
    state["state_phase"] = phase
    state["phase_label"] = phase
    state["status"] = "paused" if phase == "paused" else "blocked" if phase == "blocked" else "completed" if phase == "completed" else "active"
    if reason:
        state["current"] = _bounded(reason)
    state["updated_at"] = utc_now()
    return True


def _is_continuation(message: str) -> bool:
    return bool(CONTINUATION_RE.fullmatch(message.strip()))


def _is_pause(message: str) -> bool:
    return bool(PAUSE_RE.search(message))


def _is_report_only(message: str) -> bool:
    return bool(REPORT_ONLY_RE.search(message)) and len(message.strip()) < 100


def classify_user_message(
    message: str,
    previous: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Classify a user turn before any old plan is allowed to resume.

    This is deliberately conservative. It only controls checkpoint handling;
    it never grants permissions or executes an operation.
    """
    text = _bounded(message, 4_000)
    state = previous if isinstance(previous, dict) else {}
    has_goal = bool(str(state.get("active_goal") or "").strip())
    stripped = text.strip()
    if stripped.lower() == "/compact":
        mode = "compact"
    elif _is_report_only(stripped):
        mode = "report_only"
    elif _is_pause(stripped):
        mode = "pause"
    elif _is_continuation(stripped):
        mode = "continue" if has_goal else "new"
    elif REPLACE_RE.search(stripped):
        mode = "replace"
    elif SHRINK_RE.search(stripped):
        mode = "shrink"
    elif APPEND_RE.search(stripped) and has_goal:
        mode = "append"
    elif has_goal:
        mode = "refine"
    else:
        mode = "new"

    return {
        "mode": mode if mode in MESSAGE_MODES else "new",
        "message": text,
        "has_existing_goal": has_goal,
        "substantive": mode in {"new", "refine", "append", "replace", "shrink"},
        "supersedes_pending": mode in {"new", "replace", "shrink"},
        "preserves_pending": mode in {"continue", "refine", "append", "pause", "report_only"},
        "allows_mutation": mode not in {"pause", "report_only", "compact"},
    }


def prepare_for_user_message(
    previous: dict[str, Any] | None,
    user_message: str,
    workspace: Path | str,
    *,
    generation_id: str = "",
) -> dict[str, Any]:
    """Freeze the active target before a generation begins.

    A bare “continue” resumes the prior goal. A substantive new request creates
    a new task state and retains the old target as historical context instead
    of silently letting it leak into the next task.
    """
    message = _bounded(user_message, 4_000)
    existing = normalize_task_state(previous, workspace)
    classification = classify_user_message(message, existing)
    mode = classification["mode"]
    new_workspace = existing.get("workspace_id") != workspace_id(workspace)
    has_previous = bool(previous) and not new_workspace

    # A new task gets a fresh baseline. Keep only a historical pointer; old
    # pending work must not silently become executable in the new task.
    if not has_previous or (mode == "new" and existing.get("phase") in TERMINAL_PHASES):
        state = _default_state(workspace)
        if existing.get("active_goal"):
            _append(state["superseded_goals"], existing.get("active_goal"))
            _append(state["goal_history"], f"superseded:{existing.get('active_goal')}")
    else:
        state = existing

    old_goal = str(state.get("active_goal") or "").strip()
    if old_goal and mode in {"replace", "shrink"} and old_goal != message:
        _append(state["superseded_goals"], old_goal)
        _append(state["goal_history"], f"{mode}:{old_goal}")
        # Old evidence remains historical, but cannot satisfy a new goal.
        state["pending"] = []
        state["unverified"] = []
        state["acceptance_matrix"] = []
        state["boundary_cases"] = []

    if mode == "pause":
        state["goal_mode"] = "pause"
        transition(state, "paused", reason="用户要求暂停，不得继续执行旧计划")
        _append(state["do_not_do"], "暂停期间不得继续执行旧计划中的修改")
    elif mode == "report_only":
        state["goal_mode"] = "report_only"
        transition(state, "paused", reason="本轮仅报告或分析，不执行修改")
        _append(state["do_not_do"], "本轮仅报告，不执行文件修改、安装、删除或启动操作")
    elif mode == "continue":
        state["goal_mode"] = "continue"
        if state.get("phase") == "paused":
            transition(state, "investigating", reason="用户要求继续，先恢复并校验任务状态")
    elif mode == "compact":
        # /compact is handled by the API. Keep the task target unchanged.
        state["goal_mode"] = "continue" if old_goal else "new"
    else:
        state["goal_mode"] = mode if mode in GOAL_MODES else "refine"
        if mode in {"new", "replace", "shrink"} or not old_goal:
            state["active_goal"] = message
        elif mode == "append":
            state["active_goal"] = _bounded(f"{old_goal}\n追加要求：{message}", MAX_TEXT)
        elif mode == "refine":
            state["active_goal"] = _bounded(f"{old_goal}\n本轮细化：{message}", MAX_TEXT)
        state["goal_version"] = max(1, int(state.get("goal_version") or 0) + 1)
        _append(state["scope"], message)
        transition(state, "investigating", reason="已冻结当前用户目标，正在确认范围和证据")
        state["boundary_cases"] = _merge_boundary_cases(
            state.get("boundary_cases"),
            default_boundary_cases(state.get("active_goal")),
            reset=mode in {"new", "replace", "shrink"},
        )
        if any(marker in message for marker in ("确认", "可以", "开始", "执行", "按计划", "交给你")):
            _append(state["approved_actions"], f"用户批准：{message}")

    if NEGATIVE_RE.search(message):
        _append(state["user_decisions"], message)
        _append(state["do_not_do"], message)
        _append(state["forbidden_actions"], message)
    state["last_generation_id"] = _bounded(generation_id, 100)
    state["updated_at"] = utc_now()
    return refresh_self_check(state, workspace, latest_user_message=message)


def _relative_change_paths(values: Any, workspace: Path | str | None) -> set[str]:
    root = Path(normalize_workspace(workspace)) if workspace else None
    result: set[str] = set()
    for value in values or []:
        try:
            path = Path(str(value))
            if root and not path.is_absolute():
                path = root / path
            if root:
                path = path.resolve()
                if path.is_relative_to(root):
                    result.add(path.relative_to(root).as_posix())
            else:
                result.add(path.as_posix())
        except (OSError, TypeError, ValueError):
            continue
    return result


def build_self_check(
    state: dict[str, Any] | None,
    workspace: Path | str | None = None,
    *,
    latest_user_message: str = "",
    current_snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the short pre-turn/recovery checklist used by the Agent.

    The result is an audit observation, not a permission grant.  Unknown file
    changes and stale process records are kept visible so a later model turn
    cannot mistake a compact checkpoint for a clean workspace.
    """
    raw = state if isinstance(state, dict) else {}
    normalized = normalize_task_state(raw, workspace or raw.get("workspace"))
    root = normalize_workspace(workspace or normalized.get("workspace"))
    current = current_snapshot or capture_workspace_snapshot(root)
    stored = normalized.get("workspace_snapshot") or normalized.get("baseline", {}).get("snapshot") or {}
    delta = diff_workspace_snapshots(stored, current) if stored else {
        "changed": [], "created": [], "modified": [], "deleted": [], "complete": True,
    }
    agent_paths = _relative_change_paths(normalized.get("files_changed_by_agent"), root)
    changed_paths = set(delta.get("changed") or [])
    agent_changes = sorted(changed_paths & agent_paths)
    concurrent_changes = sorted(changed_paths - agent_paths)
    baseline_git = (normalized.get("baseline") or {}).get("git") or {}
    existing_changes = sorted(
        set(baseline_git.get("tracked") or []) | set(baseline_git.get("untracked") or [])
    )
    mixed_changes = sorted(set(existing_changes) & agent_paths)

    process_checks = []
    for process in normalized.get("active_processes") or []:
        if not isinstance(process, dict):
            continue
        pid = process.get("pid")
        alive = _pid_exists(pid) if pid is not None else None
        process_checks.append({
            "kind": _bounded(process.get("kind"), 60),
            "pid": pid,
            "port": process.get("port"),
            "url": _bounded(process.get("url"), 300),
            "alive": alive,
            "reachable": process.get("reachable"),
            "recorded_verified": bool(process.get("verified")),
        })

    blocking: list[str] = []
    if not normalized.get("active_goal"):
        blocking.append("缺少当前用户目标")
    if normalized.get("goal_mode") in {"pause", "report_only"}:
        blocking.append("当前用户要求暂停或仅报告")
    if concurrent_changes:
        blocking.append("检测到任务期间无法归属给 Agent 的工作区改动")
    if any(item.get("alive") is False and item.get("recorded_verified") for item in process_checks):
        # A dead process is not always fatal, but it is unsafe to claim the
        # recorded service is still running.
        blocking.append("检查点记录的已验证进程已退出")

    return {
        "generated_at": utc_now(),
        "workspace": root,
        "workspace_id": workspace_id(root),
        "current_goal": _bounded(normalized.get("active_goal"), MAX_TEXT),
        "goal_mode": _bounded(normalized.get("goal_mode"), 40),
        "latest_user_message": _bounded(latest_user_message, 1_000),
        "memory_scope": {
            "global_allowed": True,
            "workspace": root,
            "workspace_id": workspace_id(root),
        },
        "existing_user_changes": existing_changes[:MAX_ITEMS],
        "agent_changes": agent_changes[:MAX_ITEMS],
        "mixed_changes": mixed_changes[:MAX_ITEMS],
        "workspace_delta": {
            "created": list(delta.get("created") or [])[:MAX_ITEMS],
            "modified": list(delta.get("modified") or [])[:MAX_ITEMS],
            "deleted": list(delta.get("deleted") or [])[:MAX_ITEMS],
            "complete": bool(delta.get("complete", True)),
        },
        "active_processes": process_checks[-12:],
        "forbidden_actions": list(normalized.get("forbidden_actions") or [])[-MAX_ITEMS:],
        "approved_actions": list(normalized.get("approved_actions") or [])[-MAX_ITEMS:],
        "pending": list(normalized.get("pending") or [])[-MAX_ITEMS:],
        "unverified": list(normalized.get("unverified") or [])[-MAX_ITEMS:],
        "boundary_cases": list(normalized.get("boundary_cases") or [])[-len(BOUNDARY_CASE_KINDS):],
        "blocking_reasons": blocking[:MAX_ITEMS],
        "has_user_changes": bool(existing_changes or concurrent_changes or mixed_changes),
        "requires_recovery": bool(
            normalized.get("phase") in {"paused", "blocked"}
            or normalized.get("last_finish_reason") in {"stopped", "cancelled", "error"}
            or normalized.get("last_compaction")
        ),
        "safe_to_continue": not blocking,
        "next_step": _bounded(normalized.get("next_step"), 1_000),
    }


def refresh_self_check(
    state: dict[str, Any],
    workspace: Path | str | None = None,
    *,
    latest_user_message: str = "",
) -> dict[str, Any]:
    """Refresh the snapshot and derived self-check at a task boundary."""
    normalized = normalize_task_state(state, workspace or state.get("workspace"))
    root = normalized.get("workspace")
    current = capture_workspace_snapshot(root) if root and Path(root).is_dir() else {}
    if current:
        baseline_snapshot = normalized.get("workspace_snapshot") or {}
        delta = diff_workspace_snapshots(baseline_snapshot, current)
        known_agent = _relative_change_paths(normalized.get("files_changed_by_agent"), root)
        for path in delta.get("changed") or []:
            if path not in known_agent:
                _append(normalized.setdefault("files_changed_by_user", []), path)
        normalized["self_check"] = build_self_check(
            normalized,
            root,
            latest_user_message=latest_user_message,
            current_snapshot=current,
        )
        # workspace_snapshot is the immutable task-start baseline. Do not move
        # it forward on every turn or concurrent edits would become invisible.
        if not normalized.get("workspace_snapshot"):
            normalized["workspace_snapshot"] = current
    else:
        normalized["self_check"] = build_self_check(
            normalized, root, latest_user_message=latest_user_message,
        )
    normalized["updated_at"] = utc_now()
    return normalized


def _operation_path(tool_name: str, arguments: dict[str, Any], data: dict[str, Any]) -> str:
    if tool_name == "file_manager":
        action = str(arguments.get("action") or "")
        if action in {"copy", "move"}:
            return _bounded(data.get("dst") or arguments.get("dst"), 500)
        return _bounded(data.get("path") or arguments.get("path"), 500)
    return _bounded(data.get("cwd") or arguments.get("cwd") or arguments.get("url"), 500)


def _append_matrix(state: dict[str, Any], kind: str, status: str, evidence: str) -> None:
    record = {
        "kind": _bounded(kind, 80),
        "status": status if status in {"verified", "partially_verified", "unverified", "blocked"} else "unverified",
        "evidence": _bounded(evidence, 500),
        "at": utc_now(),
    }
    matrix = state.setdefault("acceptance_matrix", [])
    matrix.append(record)
    if len(matrix) > 24:
        del matrix[:-24]


def _remove_pending(state: dict[str, Any], *needles: str) -> None:
    values = state.setdefault("pending", [])
    lowered = [str(item).lower() for item in needles if item]
    if not lowered:
        return
    state["pending"] = [
        item for item in values
        if not any(needle in str(item).lower() for needle in lowered)
    ]


def _remove_unverified(state: dict[str, Any], *needles: str) -> None:
    values = state.setdefault("unverified", [])
    lowered = [str(item).lower() for item in needles if item]
    if not lowered:
        return
    removed = []
    kept = []
    for item in values:
        if any(needle in str(item).lower() for needle in lowered):
            removed.append(item)
        else:
            kept.append(item)
    state["unverified"] = kept
    for item in removed:
        _append(state.setdefault("resolved_failures", []), item)


def _record_boundary_case(
    state: dict[str, Any],
    kind: Any,
    status: str,
    evidence: Any,
) -> None:
    normalized_kind = _bounded(kind, 60).lower().replace("-", "_")
    if normalized_kind not in BOUNDARY_CASE_KINDS:
        return
    cases = [
        item for item in (state.get("boundary_cases") or [])
        if isinstance(item, dict) and item.get("kind") != normalized_kind
    ]
    cases.append({
        "id": normalized_kind,
        "kind": normalized_kind,
        "description": _bounded(evidence or normalized_kind, 500),
        "status": status if status in {"verified", "partially_verified", "unverified", "blocked", "not_applicable"} else "unverified",
        "evidence": _bounded(evidence, 700),
        "required": True,
        "at": utc_now(),
    })
    state["boundary_cases"] = _normalize_boundary_cases(cases)


def record_tool_result(
    state: dict[str, Any],
    tool_name: str,
    arguments: dict[str, Any] | None,
    payload: dict[str, Any] | None,
    *,
    duration_ms: int = 0,
) -> dict[str, Any]:
    """Record immutable evidence from a tool call without trusting its prose."""
    arguments = arguments if isinstance(arguments, dict) else {}
    payload = payload if isinstance(payload, dict) else {}
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    success = payload.get("success") is True
    complete = bool(payload.get("complete", success and not data.get("truncated")))
    status = str(payload.get("status") or ("success" if success else "failed"))
    error = str(payload.get("error") or "")
    target = _operation_path(tool_name, arguments, data)
    event = {
        "source": tool_name,
        "status": status,
        "success": success,
        "complete": complete,
        "confidence": payload.get("confidence", "unknown"),
        "error": error,
        "error_class": payload.get("error_class") or classify_error(error, source=tool_name),
        "target": target,
        "duration_ms": max(0, int(duration_ms or 0)),
        "timestamp": payload.get("timestamp") or utc_now(),
        "operation_id": payload.get("operation_id", ""),
        "command": _bounded(arguments.get("code"), 500),
        "check_id": _bounded(data.get("check_id"), 80),
        "verification_kind": _bounded(data.get("verification_kind"), 80),
        "exit_code": data.get("exit_code"),
        "verification_quality": _bounded(data.get("verification_quality"), 40),
    }
    boundary_kind = data.get("boundary_case") or data.get("boundary_case_kind") or arguments.get("boundary_case")
    if boundary_kind:
        _record_boundary_case(
            state,
            boundary_kind,
            "verified" if success and complete else "partially_verified" if success else "blocked",
            data.get("boundary_evidence") or data.get("output") or error or target,
        )
    events = state.setdefault("tool_events", [])
    events.append(event)
    if len(events) > 20:
        del events[:-20]

    if tool_name == "file_manager" and success:
        action = str(arguments.get("action") or "")
        if action in {"write", "find_replace", "copy", "move", "delete", "mkdir"} and target:
            try:
                from agent.project_map import mark_project_map_stale
                mark_project_map_stale(state.get("workspace"))
            except Exception:
                pass
            _append(state.setdefault("files_changed_by_agent", []), target)
            transition(state, "implementing", reason=f"正在修改：{target}")
            _append(state.setdefault("pending", []), f"需要回读或验证修改：{target}")
            index = state.setdefault("project_index", {})
            if isinstance(index, dict):
                index["stale"] = True
                index["stale_reason"] = f"文件已修改: {target}"[:500]
        elif action in {"read", "info"} and target in state.get("files_changed_by_agent", []):
            _append(state.setdefault("verified", []), f"已回读修改文件：{target}")
            _append_matrix(state, "file_readback", "verified" if complete else "partially_verified", target)
            _remove_pending(state, target)

    if tool_name == "project_map" and success:
        action = str(arguments.get("action") or "")
        index = state.setdefault("project_index", {})
        if isinstance(index, dict):
            for key in (
                "index_version", "workspace", "generated_at", "source_revision",
                "source_revision_files", "source_revision_truncated", "truncated",
                "project_types", "scripts", "top_level", "entrypoints",
            ):
                if key in data:
                    index[key] = data.get(key)
            if action == "refresh":
                index["stale"] = False
                index.pop("stale_reason", None)
        if action == "refresh":
            _append(state.setdefault("verified", []), "项目架构索引已按当前工作区刷新")
            _remove_pending(state, "项目架构索引", "刷新索引")
        elif action in {"summary", "inspect", "search"} and not complete:
            _append(state.setdefault("unverified", []), "项目架构索引结果不完整，不能据此断言未找到文件或模块")

    if tool_name in {"verification_exec", "runtime_smoke"}:
        kind = str(data.get("verification_kind") or arguments.get("mode") or tool_name)
        if success and complete:
            transition(state, "validating", reason=f"已获得验证证据：{tool_name}")
            _append(state.setdefault("verified", []), f"{tool_name} 通过：{target or kind}")
            _append_matrix(state, kind, "verified", target or str(data.get("output") or "通过"))
            _remove_pending(state, kind, target, "验证")
            _remove_unverified(state, kind, target)
        else:
            _append(state.setdefault("unverified", []), f"{tool_name} 未完成：{target or kind}")
            _append_matrix(state, kind, "partially_verified" if success else "blocked", error or target)
        if tool_name == "runtime_smoke" and data.get("identity"):
            identity = data.get("identity") or {}
            process = {
                "kind": "service",
                "url": data.get("url") or arguments.get("url"),
                "identity": identity,
                "checked_at": utc_now(),
                "verified": bool(success and complete),
            }
            state.setdefault("active_processes", []).append(process)
            state["active_processes"] = state["active_processes"][-12:]

    if tool_name == "service_status":
        service = data if isinstance(data, dict) else {}
        process = {
            "kind": "service_port",
            "port": service.get("port") or arguments.get("port"),
            "pid": service.get("pid"),
            "listeners": service.get("listeners") or [],
            "reachable": bool(service.get("reachable")),
            "checked_at": service.get("checked_at") or utc_now(),
            "verified": bool(success and complete and service.get("listening")),
        }
        state.setdefault("active_processes", []).append(process)
        state["active_processes"] = state["active_processes"][-12:]

    if tool_name == "code_exec" and success:
        command = _bounded(arguments.get("code"), 300)
        if re.search(r"\b(?:pytest|unittest|vitest|jest|tsc|mypy|ruff|eslint|npm\s+(?:run\s+)?(?:test|build|lint))\b", command, re.I):
            transition(state, "validating", reason="正在执行命令验证")
            _append(state.setdefault("verified", []), f"命令通过：{command}")
            _append_matrix(state, "command", "verified" if complete else "partially_verified", command)
        elif re.search(r"\b(?:uvicorn|vite|npm\s+(?:run\s+)?dev|python\s+.*main\.py)\b", command, re.I):
            _append(state.setdefault("active_processes", []), {
                "kind": "started_by_agent",
                "command": command,
                "workspace": target,
                "checked_at": utc_now(),
                "verified": False,
            })

    if not success and status != "pending":
        detail = f"{tool_name} [{event['error_class']}]: {error or payload.get('message') or '失败'}"
        _append(state.setdefault("failed_attempts", []), detail)
        if event["error_class"] in {"task", "environment"}:
            _append(state.setdefault("unverified", []), detail)
    if tool_name in {"file_manager", "project_map", "service_status", "runtime_smoke"}:
        try:
            state.update(refresh_self_check(state, state.get("workspace")))
        except Exception:
            # The audit snapshot is advisory and must not hide the tool result.
            pass
    state["updated_at"] = utc_now()
    return state


def record_subagent_result(state: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    evidence = data.get("evidence") if isinstance(data.get("evidence"), dict) else {}
    role = _bounded(data.get("role"), 40) or "subagent"
    status = _bounded(data.get("status"), 40) or "unknown"
    for path in evidence.get("modified_files") or []:
        _append(state.setdefault("files_changed_by_agent", []), path)
        _append(state.setdefault("pending", []), f"需要主代理复核子代理修改：{path}")
    parent_audit = evidence.get("parent_audit") if isinstance(evidence.get("parent_audit"), dict) else {}
    if parent_audit.get("status") == "mismatch":
        _append(
            state.setdefault("unverified", []),
            f"子代理工作区二次核验不一致：{parent_audit.get('message') or '报告与当前文件状态不一致'}",
        )
    for failure in evidence.get("failures") or []:
        _append(state.setdefault("failed_attempts", []), f"子代理 {role}: {failure}")
    for check in evidence.get("verifications") or []:
        # A child report is an observation until the parent independently checks it.
        _append(state.setdefault("inferred", []), f"子代理 {role} 报告：{check}")
    if status not in {"done", "completed"}:
        _append(state.setdefault("unverified", []), f"子代理 {role} 状态：{status}")
    state["updated_at"] = utc_now()
    return state


def finalize_task_state(state: dict[str, Any], finish_reason: str) -> dict[str, Any]:
    state = normalize_task_state(state, state.get("workspace"))
    state["last_finish_reason"] = _bounded(finish_reason, 100)
    if finish_reason in {"stopped", "cancelled"}:
        transition(state, "paused", reason="本轮被停止，恢复前必须重新校验状态")
    elif finish_reason not in {"completed", ""}:
        transition(state, "blocked", reason=f"本轮未正常结束：{finish_reason}")
    elif acceptance_ready(state):
        transition(state, "completed", reason="验收矩阵和当前证据均已满足")
    elif state.get("files_changed_by_agent") or state.get("pending"):
        transition(state, "validating", reason="仍存在待验收修改，不自动宣告任务完成")
    state["updated_at"] = utc_now()
    return state


def acceptance_ready(state: dict[str, Any] | None) -> bool:
    """Return whether a checkpoint may truthfully enter the completed phase."""
    source = state if isinstance(state, dict) else {}
    normalized = normalize_task_state(source, source.get("workspace"))
    if not normalized.get("active_goal"):
        return False
    if normalized.get("pending") or normalized.get("unverified"):
        return False
    matrix = normalized.get("acceptance_matrix") or []
    if matrix:
        latest = {}
        for item in matrix:
            if isinstance(item, dict) and item.get("kind"):
                latest[item["kind"]] = item.get("status")
        if not latest or any(status != "verified" for status in latest.values()):
            return False
    return bool(normalized.get("verified") or normalized.get("completed"))


def build_acceptance_report(state: dict[str, Any] | None) -> dict[str, Any]:
    """Build a machine-readable handoff without upgrading reports to facts."""
    normalized = normalize_task_state(state or {}, (state or {}).get("workspace"))
    events = list(normalized.get("tool_events") or [])
    commands = []
    failures = []
    for event in events:
        if event.get("command"):
            commands.append({
                "tool": event.get("source"),
                "command": event.get("command"),
                "check_id": event.get("check_id") or None,
                "exit_code": event.get("exit_code"),
                "status": event.get("status"),
                "complete": bool(event.get("complete")),
                "verification_quality": event.get("verification_quality") or None,
                "at": event.get("timestamp"),
            })
        if not event.get("success") and event.get("error"):
            failures.append({
                "tool": event.get("source"),
                "error": event.get("error"),
                "error_class": event.get("error_class"),
                "target": event.get("target"),
                "operation_id": event.get("operation_id"),
            })
    return {
        "version": 2,
        "task_id": normalized.get("task_id"),
        "workspace": normalized.get("workspace"),
        "workspace_id": normalized.get("workspace_id"),
        "phase": normalized.get("phase"),
        "status": normalized.get("status"),
        "active_goal": normalized.get("active_goal"),
        "goal_mode": normalized.get("goal_mode"),
        "goal_version": normalized.get("goal_version"),
        "superseded_goals": list(normalized.get("superseded_goals") or []),
        "modified_files": list(normalized.get("files_changed_by_agent") or []),
        "user_existing_changes": list(normalized.get("files_changed_by_user") or []),
        "commands": commands[-20:],
        "verified": list(normalized.get("verified") or []),
        "inferred": list(normalized.get("inferred") or []),
        "unverified": list(normalized.get("unverified") or []),
        "pending": list(normalized.get("pending") or []),
        "failures": failures[-20:],
        "acceptance_matrix": list(normalized.get("acceptance_matrix") or []),
        "boundary_cases": list(normalized.get("boundary_cases") or []),
        "context_conflicts": list(normalized.get("context_conflicts") or []),
        "project_index": dict(normalized.get("project_index") or {}),
        "active_processes": list(normalized.get("active_processes") or []),
        "self_check": dict(normalized.get("self_check") or {}),
        "last_compaction": dict(normalized.get("last_compaction") or {}),
        "next_step": normalized.get("next_step"),
        "risk": normalized.get("risk"),
        "finish_reason": normalized.get("last_finish_reason"),
    }


def _pid_exists(pid: Any) -> bool | None:
    try:
        value = int(pid)
    except (TypeError, ValueError):
        return None
    if value <= 0:
        return False
    try:
        os.kill(value, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return None


def recovery_check(state: dict[str, Any], workspace: Path | str | None = None) -> dict[str, Any]:
    """Validate the minimum facts needed before a resumed long task continues."""
    raw_state = state if isinstance(state, dict) else {}
    stored_workspace = normalize_workspace(raw_state.get("workspace"))
    requested_workspace = normalize_workspace(workspace or stored_workspace)
    state = normalize_task_state(raw_state, requested_workspace)
    findings: list[dict[str, Any]] = []
    current_workspace = requested_workspace
    if stored_workspace and current_workspace != stored_workspace:
        findings.append({"kind": "workspace_changed", "status": "blocked", "message": "工作区已变化，旧检查点不可直接复用"})
    baseline = state.get("baseline") or {}
    baseline_head = ((baseline.get("git") or {}).get("head") or "")
    current = capture_worktree_baseline(current_workspace)
    current_head = ((current.get("git") or {}).get("head") or "")
    if baseline_head and current_head and baseline_head != current_head:
        findings.append({"kind": "source_revision_changed", "status": "needs_review", "message": "Git HEAD 已变化，需重新读取目标文件"})
    baseline_git = baseline.get("git") if isinstance(baseline, dict) else {}
    current_git = current.get("git") if isinstance(current, dict) else {}
    baseline_dirty = set((baseline_git or {}).get("tracked") or []) | set((baseline_git or {}).get("untracked") or [])
    current_dirty = set((current_git or {}).get("tracked") or []) | set((current_git or {}).get("untracked") or [])
    known_agent_paths = _relative_change_paths(state.get("files_changed_by_agent"), current_workspace)
    new_dirty = sorted((current_dirty - baseline_dirty) - known_agent_paths)
    if new_dirty:
        findings.append({
            "kind": "worktree_changed",
            "status": "needs_review",
            "message": "任务开始后检测到新的工作区改动，继续前需重新读取相关文件",
            "paths": new_dirty[:MAX_ITEMS],
        })
    baseline_snapshot = state.get("workspace_snapshot") or {}
    if baseline_snapshot and current_workspace:
        current_snapshot = capture_workspace_snapshot(current_workspace)
        snapshot_delta = diff_workspace_snapshots(baseline_snapshot, current_snapshot)
        known_agent = _relative_change_paths(state.get("files_changed_by_agent"), current_workspace)
        unknown_changes = sorted(set(snapshot_delta.get("changed") or []) - known_agent)
        if unknown_changes:
            findings.append({
                "kind": "concurrent_workspace_change",
                "status": "needs_review",
                "message": "任务基线之后出现无法归属给 Agent 的文件改动，继续前需重新读取相关文件",
                "paths": unknown_changes[:MAX_ITEMS],
            })
    for process in state.get("active_processes") or []:
        pid = process.get("pid") if isinstance(process, dict) else None
        if pid is not None and _pid_exists(pid) is False:
            findings.append({"kind": "stale_process", "status": "needs_review", "message": f"记录的进程 PID {pid} 已不存在"})
    if not state.get("active_goal"):
        findings.append({"kind": "missing_goal", "status": "blocked", "message": "检查点缺少当前用户目标"})
    if state.get("goal_mode") in {"pause", "report_only"}:
        findings.append({
            "kind": "user_pause_boundary",
            "status": "blocked",
            "message": "用户要求暂停或仅报告，不能自动恢复旧计划",
        })
    return {
        "ok": not any(item["status"] == "blocked" for item in findings),
        "findings": findings,
        "questions": [
            "当前用户最新目标是什么？",
            "当前工作区是否仍与检查点一致？",
            "哪些结论有可追溯的已验证证据？",
            "哪些修改尚未验收？",
            "下一步是否仍被用户批准？",
        ],
    }


def format_task_state(state: dict[str, Any], *, max_chars: int = 5_000) -> str:
    state = normalize_task_state(state, state.get("workspace"))
    lines = [
        f"任务 ID：{state['task_id']}；阶段：{state['phase']}；目标模式：{state['goal_mode']}；目标版本：{state['goal_version']}",
        f"当前用户目标：{state['active_goal'] or '未冻结'}",
        f"工作区：{state['workspace'] or '未设置'}",
    ]
    labels = (
        ("scope", "范围"), ("user_decisions", "用户决定"), ("do_not_do", "禁止/暂停"),
        ("completed", "已完成"), ("pending", "待完成"), ("verified", "已验证"),
        ("inferred", "待核对推断"), ("unverified", "未验证"), ("failed_attempts", "失败记录"),
        ("files_changed_by_agent", "本任务修改"),
    )
    for key, label in labels:
        values = state.get(key) or []
        if values:
            lines.append(f"{label}：" + "；".join(_bounded(item, 260) for item in values[-8:]))
    conflicts = state.get("context_conflicts") or []
    if conflicts:
        summaries = []
        for item in conflicts[-6:]:
            if isinstance(item, dict):
                summaries.append(_bounded(item.get("message") or item.get("kind"), 260))
        if summaries:
            lines.append("上下文冲突/待核对：" + "；".join(summaries))
    boundary = state.get("boundary_cases") or []
    if boundary:
        lines.append(
            "边界场景：" + "；".join(
                f"{item.get('kind')}={item.get('status')}" for item in boundary[-7:]
                if isinstance(item, dict)
            )
        )
    check = state.get("self_check") or {}
    if check:
        lines.append(
            f"自检：{'可继续' if check.get('safe_to_continue') else '需复核'}"
            + ("；" + "；".join(check.get("blocking_reasons") or []) if check.get("blocking_reasons") else "")
        )
    if state.get("next_step"):
        lines.append(f"下一步：{state['next_step']}")
    if state.get("risk"):
        lines.append(f"风险/阻塞：{state['risk']}")
    content = "\n".join(lines)
    if len(content) > max_chars:
        content = content[:max_chars - 32] + "\n[任务状态已裁剪]"
    return (
        '<task_state source="checkpoint" confidence="verified">\n'
        "这是应用维护的任务状态。旧目标、子代理结论和未验证项不能被当作已完成事实。\n"
        + content
        + "\n</task_state>"
    )


def task_state_json(state: dict[str, Any]) -> str:
    return json.dumps(normalize_task_state(state, state.get("workspace")), ensure_ascii=False, separators=(",", ":"))


def compact_task_state(state: dict[str, Any], max_bytes: int = 11_500) -> dict[str, Any]:
    """Bound the persisted checkpoint while retaining negative evidence first."""
    normalized = normalize_task_state(state, state.get("workspace"))
    priority_lists = (
        "do_not_do", "forbidden_actions", "pending", "unverified", "failed_attempts", "verified",
        "completed", "user_decisions", "approved_actions", "files_changed_by_agent", "files_changed_by_user",
        "inferred", "scope", "goal_history", "superseded_goals",
        "resolved_failures",
    )
    for size in (8, 5, 3, 1):
        candidate = dict(normalized)
        for key in priority_lists:
            candidate[key] = list(normalized.get(key) or [])[-size:]
        candidate["tool_events"] = list(normalized.get("tool_events") or [])[-min(size, 6):]
        candidate["acceptance_matrix"] = list(normalized.get("acceptance_matrix") or [])[-min(size, 8):]
        candidate["active_processes"] = list(normalized.get("active_processes") or [])[-min(size, 4):]
        candidate["context_conflicts"] = list(normalized.get("context_conflicts") or [])[-min(size, 4):]
        candidate["boundary_cases"] = list(normalized.get("boundary_cases") or [])[-min(size, 7):]
        candidate["self_check"] = _normalize_self_check(normalized.get("self_check"))
        candidate["last_compaction"] = _normalize_compaction(normalized.get("last_compaction"))
        snapshot = normalized.get("workspace_snapshot") or {}
        candidate["workspace_snapshot"] = {
            key: snapshot.get(key) for key in ("workspace", "workspace_id", "captured_at", "fingerprint", "file_count", "truncated")
            if key in snapshot
        }
        encoded = json.dumps(candidate, ensure_ascii=False, separators=(",", ":"))
        if len(encoded.encode("utf-8")) <= max_bytes:
            return candidate
    # The scalar state is still more valuable than dropping the checkpoint.
    keep = {
        key: normalized.get(key)
        for key in (
            "version", "task_id", "phase", "state_phase", "phase_label", "status", "workspace",
            "workspace_id", "active_goal", "goal_mode", "goal_version", "current", "next_step", "validation",
            "risk", "last_generation_id", "last_finish_reason", "updated_at", "created_at",
        )
    }
    keep["pending"] = list(normalized.get("pending") or [])[-2:]
    keep["do_not_do"] = list(normalized.get("do_not_do") or [])[-2:]
    keep["forbidden_actions"] = list(normalized.get("forbidden_actions") or [])[-2:]
    keep["approved_actions"] = list(normalized.get("approved_actions") or [])[-2:]
    keep["boundary_cases"] = list(normalized.get("boundary_cases") or [])[-3:]
    keep["resolved_failures"] = list(normalized.get("resolved_failures") or [])[-2:]
    keep["context_conflicts"] = list(normalized.get("context_conflicts") or [])[-2:]
    keep["self_check"] = _normalize_self_check(normalized.get("self_check"))
    keep["last_compaction"] = _normalize_compaction(normalized.get("last_compaction"))
    keep["project_index"] = dict(normalized.get("project_index") or {})
    return keep
