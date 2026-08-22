import copy
import hashlib
import json
import time

from fastapi import APIRouter

from agent.diagnostics import runtime_diagnostics
from agent.subagent import subagent_manager
from config import settings
from db.database import db
from agent.checkpoint import decode_checkpoint
from agent.task_state import build_acceptance_report, recovery_check, normalize_task_state
from agent.task_state import workspace_id


router = APIRouter()
TASK_CACHE_TTL_SECONDS = 3.0
_task_cache: dict[str, object] = {"key": "", "expires_at": 0.0, "tasks": []}


def _task_cache_key(session_id: str | None, rows: list[dict]) -> str:
    payload = [
        {
            "session_id": row.get("session_id"),
            "workspace": row.get("tool_workspace"),
            "checkpoint": row.get("task_checkpoint"),
        }
        for row in rows
    ]
    encoded = json.dumps({"session_id": session_id or "", "rows": payload}, sort_keys=True, default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _build_tasks(rows: list[dict], fallback_workspace: str) -> list[dict]:
    tasks = []
    for row in rows:
        workspace_value = row.get("tool_workspace") or fallback_workspace
        state = normalize_task_state(decode_checkpoint(row.get("task_checkpoint")), workspace_value)
        recovery = recovery_check(state, workspace_value)
        tasks.append({
            "session_id": row.get("session_id"),
            "name": row.get("name", ""),
            "workspace": workspace_value,
            "phase": state.get("phase"),
            "status": state.get("status"),
            "recovery_ok": recovery.get("ok"),
            "recovery_findings": recovery.get("findings", [])[:8],
            "context_conflicts": list(state.get("context_conflicts") or [])[:8],
            "acceptance": build_acceptance_report(state),
        })
    return tasks


@router.get("/api/diagnostics")
async def get_diagnostics(session_id: str | None = None):
    workspace = str(settings.TOOL_WORKSPACE)
    session_rows = []
    if session_id:
        session_rows = [await db.get_session_meta(session_id)]
    else:
        try:
            session_rows = await db.list_session_meta(limit=20)
        except Exception:
            session_rows = []
    key = _task_cache_key(session_id, session_rows)
    now = time.monotonic()
    if _task_cache.get("key") == key and now < float(_task_cache.get("expires_at") or 0):
        tasks = copy.deepcopy(_task_cache.get("tasks") or [])
    else:
        tasks = _build_tasks(session_rows, workspace)
        _task_cache.update({
            "key": key,
            "expires_at": now + TASK_CACHE_TTL_SECONDS,
            "tasks": copy.deepcopy(tasks),
        })
    return {
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "port": settings.PORT,
        "workspace": workspace,
        "memory": await db.get_memory_stats(
            workspace_path=workspace,
            project_id=workspace_id(workspace),
        ),
        "runtime": runtime_diagnostics.snapshot(session_id),
        "active_subagents": subagent_manager.active_snapshot(session_id),
        "tasks": tasks,
        "skill_events": await db.list_skill_events(session_id or None, limit=20),
    }
