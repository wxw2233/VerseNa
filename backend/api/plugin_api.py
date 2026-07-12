from fastapi import APIRouter
from plugins.manager import plugin_manager

router = APIRouter()

@router.get("/api/plugins")
async def list_plugins():
    return plugin_manager.list_plugins()

@router.post("/api/plugins/{name}/enable")
async def enable_plugin(name: str):
    plugin_manager.enable(name)
    return {"status": "ok"}

@router.post("/api/plugins/{name}/disable")
async def disable_plugin(name: str):
    plugin_manager.disable(name)
    return {"status": "ok"}
