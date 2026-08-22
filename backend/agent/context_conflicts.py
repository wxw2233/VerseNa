"""Detect stale or incompatible reference data before a long task proceeds."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from agent.project_map import build_project_map
from agent.task_state import normalize_task_state, normalize_workspace, recovery_check, workspace_id


MAX_CONFLICTS = 12


def _record(kind: str, severity: str, message: str, **extra: Any) -> dict[str, Any]:
    return {
        "kind": kind,
        "severity": severity,
        "message": message[:600],
        **{key: value for key, value in extra.items() if value not in (None, "", [], {})},
    }


def _path_in_workspace(workspace: Path, value: Any) -> Path | None:
    try:
        path = Path(str(value or ""))
        if not path.is_absolute():
            path = workspace / path
        path = path.resolve()
        return path if path.is_relative_to(workspace) else None
    except (OSError, TypeError, ValueError):
        return None


def detect_context_conflicts(
    workspace: Path | str,
    task_state: dict[str, Any] | None,
    memories: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Return structured warnings without silently choosing between sources.

    A conflict is a request for fresh evidence, not a model instruction.  The
    current filesystem remains the source of truth for code; memories and the
    project map remain navigational reference data.
    """
    root_text = normalize_workspace(workspace)
    root = Path(root_text) if root_text else Path.cwd()
    state = normalize_task_state(task_state or {}, root)
    current_id = workspace_id(root)
    conflicts: list[dict[str, Any]] = []

    for finding in recovery_check(state, root).get("findings", []):
        severity = "blocking" if finding.get("status") == "blocked" else "warning"
        conflicts.append(_record(
            f"recovery_{finding.get('kind') or 'unknown'}",
            severity,
            str(finding.get("message") or "检查点恢复条件不一致"),
            paths=list(finding.get("paths") or [])[:8],
        ))

    for raw_path in state.get("files_changed_by_agent") or []:
        path = _path_in_workspace(root, raw_path)
        if path is None:
            conflicts.append(_record(
                "checkpoint_path_outside_workspace",
                "warning",
                f"检查点中的改动路径不属于当前工作区: {raw_path}",
            ))
        elif not path.exists():
            conflicts.append(_record(
                "checkpoint_file_missing",
                "warning",
                f"检查点记录的改动文件当前不存在: {path.relative_to(root).as_posix()}",
            ))

    try:
        current_map = build_project_map(root)
    except (OSError, ValueError):
        current_map = {}
    stored_map = state.get("project_index") if isinstance(state.get("project_index"), dict) else {}
    if stored_map.get("workspace") and normalize_workspace(stored_map.get("workspace")) != root_text:
        conflicts.append(_record(
            "project_index_workspace_mismatch",
            "warning",
            "项目索引属于其他工作区，不能作为当前项目结构事实。",
            indexed_workspace=stored_map.get("workspace"),
            current_workspace=root_text,
        ))
    stored_revision = str(stored_map.get("source_revision") or "")
    current_revision = str(current_map.get("source_revision") or "")
    if stored_revision and current_revision and stored_revision != current_revision:
        conflicts.append(_record(
            "project_index_stale",
            "warning",
            "项目索引源指纹已变化；索引只能用于导航，修改前需重新读取实际文件。",
            indexed_revision=stored_revision,
            current_revision=current_revision,
        ))
    elif stored_map.get("stale"):
        conflicts.append(_record(
            "project_index_marked_stale",
            "warning",
            "当前任务修改过代码或配置，先前项目索引已标记为待刷新。",
        ))
    stored_types = set(str(item) for item in (stored_map.get("project_types") or []))
    current_types = set(str(item) for item in (current_map.get("project_types") or []))
    if stored_types and current_types and stored_types != current_types:
        conflicts.append(_record(
            "project_type_mismatch",
            "warning",
            "项目索引中的技术栈与当前文件标记不一致，需要重新读取配置和入口。",
            indexed=sorted(stored_types),
            current=sorted(current_types),
        ))
    stored_scripts = set((stored_map.get("scripts") or {}).keys())
    current_scripts = set((current_map.get("scripts") or {}).keys())
    if stored_scripts and current_scripts and stored_scripts != current_scripts:
        conflicts.append(_record(
            "project_scripts_mismatch",
            "warning",
            "项目索引中的 package.json 脚本集合与当前文件不一致。",
            indexed=sorted(stored_scripts)[:20],
            current=sorted(current_scripts)[:20],
        ))

    for memory in memories or []:
        if not isinstance(memory, dict):
            continue
        scope = str(memory.get("scope") or "global")
        memory_workspace = normalize_workspace(memory.get("workspace_path"))
        memory_project = str(memory.get("project_id") or "")
        if scope == "workspace" and memory_workspace and memory_workspace != root_text:
            conflicts.append(_record(
                "memory_workspace_mismatch",
                "warning",
                f"工作区记忆作用域与当前工作区不一致: #{memory.get('id')}",
                memory_id=memory.get("id"),
            ))
        if memory_project and memory_project != current_id:
            conflicts.append(_record(
                "memory_project_mismatch",
                "warning",
                f"记忆属于其他项目，不能自动作为当前项目事实: #{memory.get('id')}",
                memory_id=memory.get("id"),
            ))
        if memory.get("auto_apply") and not memory.get("verified_at"):
            conflicts.append(_record(
                "unverified_auto_memory",
                "warning",
                f"自动应用记忆缺少验证时间，当前只能作为待确认参考: #{memory.get('id')}",
                memory_id=memory.get("id"),
            ))

    ports: dict[str, set[str]] = {}
    for process in state.get("active_processes") or []:
        if not isinstance(process, dict) or process.get("port") in (None, ""):
            continue
        port = str(process.get("port"))
        identity = str(process.get("pid") or process.get("url") or process.get("kind") or "unknown")
        ports.setdefault(port, set()).add(identity)
    for port, identities in ports.items():
        if len(identities) > 1:
            conflicts.append(_record(
                "checkpoint_port_identity_conflict",
                "warning",
                f"检查点中同一端口 {port} 对应多个进程或服务身份。",
                port=port,
                identities=sorted(identities)[:8],
            ))

    if state.get("phase") == "completed" and (state.get("unverified") or state.get("failed_attempts")):
        conflicts.append(_record(
            "completed_state_has_unverified_evidence",
            "blocking",
            "检查点标记为完成，但仍保留未验证项或失败记录。",
        ))

    # De-duplicate repeated recovery/path warnings while preserving a stable,
    # compact report for checkpoints, diagnostics and model context.
    unique: list[dict[str, Any]] = []
    seen = set()
    for conflict in conflicts:
        key = (conflict.get("kind"), conflict.get("message"))
        if key in seen:
            continue
        seen.add(key)
        unique.append(conflict)
        if len(unique) >= MAX_CONFLICTS:
            break
    return {
        "workspace": root_text,
        "status": "conflict" if unique else "clear",
        "conflicts": unique,
        "project_index": {
            "source_revision": current_revision,
            "generated_at": current_map.get("generated_at") if current_map else "",
            "truncated": bool(current_map.get("truncated") or current_map.get("source_revision_truncated")) if current_map else True,
        },
    }
