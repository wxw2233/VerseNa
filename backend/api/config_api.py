from fastapi import APIRouter
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
    # 更新内存
    settings.DEFAULT_API_KEY = config.api_key
    settings.DEFAULT_API_BASE = config.base_url
    settings.DEFAULT_MODEL_NAME = config.model_name
    # 持久化到数据库
    await db.set_config("api_key", config.api_key)
    await db.set_config("api_base", config.base_url)
    await db.set_config("model_name", config.model_name)
    return {"status": "ok"}

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
    except Exception:
        pass
