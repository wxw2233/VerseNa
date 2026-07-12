from fastapi import APIRouter
from pydantic import BaseModel
from config import settings

router = APIRouter()

class ModelConfig(BaseModel):
    api_key: str
    base_url: str
    model_name: str

@router.get("/api/config/model")
async def get_model_config():
    return {
        "base_url": settings.DEFAULT_API_BASE,
        "model_name": settings.DEFAULT_MODEL_NAME,
    }

@router.post("/api/config/model")
async def set_model_config(config: ModelConfig):
    settings.DEFAULT_API_KEY = config.api_key
    settings.DEFAULT_API_BASE = config.base_url
    settings.DEFAULT_MODEL_NAME = config.model_name
    return {"status": "ok"}
