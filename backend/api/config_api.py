from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from config import settings
from db.database import db

router = APIRouter()

class ModelConfig(BaseModel):
    api_key: str
    base_url: str
    model_name: str

@router.get("/api/config/model")
async def get_model_config():
    try:
        saved_key = await db.get_config("api_key", "")
        saved_url = await db.get_config("api_base", settings.DEFAULT_API_BASE)
        saved_model = await db.get_config("model_name", settings.DEFAULT_MODEL_NAME)
    except Exception:
        saved_key, saved_url, saved_model = "", settings.DEFAULT_API_BASE, settings.DEFAULT_MODEL_NAME
    return {
        "api_key": saved_key,
        "base_url": saved_url,
        "model_name": saved_model,
    }

@router.post("/api/config/model")
async def set_model_config(config: ModelConfig):
    settings.DEFAULT_API_KEY = config.api_key
    settings.DEFAULT_API_BASE = config.base_url
    settings.DEFAULT_MODEL_NAME = config.model_name
    await db.set_config("api_key", config.api_key)
    await db.set_config("api_base", config.base_url)
    await db.set_config("model_name", config.model_name)
    return {"status": "ok"}

@router.get("/api/config/trust_mode")
async def get_trust_mode():
    try:
        value = await db.get_config("trust_mode", "false")
    except Exception:
        value = "false"
    return {"enabled": value.lower() == "true"}

@router.post("/api/config/trust_mode")
async def set_trust_mode(req: dict):
    enabled = req.get("enabled", False)
    await db.set_config("trust_mode", str(enabled).lower())
    settings.TRUST_MODE = enabled
    return {"status": "ok", "enabled": enabled}

async def load_saved_config():
    """启动时从数据库加载已保存的模型配置"""
    try:
        saved_key = await db.get_config("api_key", "")
        saved_url = await db.get_config("api_base", settings.DEFAULT_API_BASE)
        saved_model = await db.get_config("model_name", settings.DEFAULT_MODEL_NAME)
        if saved_key:
            settings.DEFAULT_API_KEY = saved_key
        settings.DEFAULT_API_BASE = saved_url
        settings.DEFAULT_MODEL_NAME = saved_model
        # 加载信任模式
        trust_val = await db.get_config("trust_mode", "false")
        settings.TRUST_MODE = trust_val.lower() == "true"
    except Exception:
        pass

# --- Memory API ---

@router.get("/api/memories")
async def list_memories(category: str = None):
    memories = await db.get_memories(limit=100, category=category)
    return memories

@router.post("/api/memories")
async def create_memory(req: dict):
    content = req.get('content', '')
    category = req.get('category', 'general')
    if not content:
        raise HTTPException(400, "内容不能为空")
    dup_id = await db.check_duplicate_memory(content)
    if dup_id:
        return {"status": "duplicate", "id": dup_id}
    await db.save_memory(content, category=category, source='manual', expired_at=None)
    return {"status": "ok"}

@router.put("/api/memories/{memory_id}")
async def update_memory(memory_id: int, req: dict):
    await db.update_memory(memory_id, content=req.get('content'), category=req.get('category'))
    return {"status": "ok"}

@router.delete("/api/memories/{memory_id}")
async def delete_memory(memory_id: int):
    await db.delete_memory(memory_id)
    return {"status": "ok"}
