from fastapi import APIRouter

from agent.diagnostics import runtime_diagnostics
from agent.subagent import subagent_manager
from config import settings
from db.database import db


router = APIRouter()


@router.get("/api/diagnostics")
async def get_diagnostics(session_id: str | None = None):
    workspace = str(settings.TOOL_WORKSPACE)
    return {
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "port": settings.PORT,
        "workspace": workspace,
        "memory": await db.get_memory_stats(workspace_path=workspace),
        "runtime": runtime_diagnostics.snapshot(session_id),
        "active_subagents": subagent_manager.active_snapshot(session_id),
    }
