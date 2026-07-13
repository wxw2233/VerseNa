from fastapi import APIRouter, Request
from pydantic import BaseModel
from adapters.qq_bot import QQBotAdapter
from agent.react import ReActAgent
from agent.memory import MemoryManager
from agent.models.openai_adapter import OpenAIAdapter
from persona.manager import persona_manager
from config import settings

router = APIRouter()
qq_adapter = QQBotAdapter()

@router.post("/api/qq/webhook")
async def qq_webhook(request: Request):
    data = await request.json()
    msg = qq_adapter.parse_webhook(data)
    if not msg or not msg.content:
        return {"code": 0}

    system_prompt = persona_manager.get_system_prompt("default")
    adapter = OpenAIAdapter(api_key=settings.DEFAULT_API_KEY, base_url=settings.DEFAULT_API_BASE, model_name=settings.DEFAULT_MODEL_NAME)
    agent = ReActAgent(model=adapter, memory=MemoryManager())

    full_reply = ""
    async for event in agent.run(f"qq_{msg.user_id}", msg.content, system_prompt=system_prompt):
        if event["type"] == "answer":
            full_reply += event["content"]

    if full_reply:
        await qq_adapter.send(msg.channel_id, full_reply[:2000])
    return {"code": 0}


class QQConfig(BaseModel):
    app_id: str
    app_secret: str
    sandbox: bool = True

@router.get("/api/qq/config")
async def get_qq_config():
    from db.database import db
    try:
        app_id = await db.get_config("qq_app_id", "")
        app_secret = await db.get_config("qq_app_secret", "")
        sandbox = await db.get_config("qq_sandbox", "true")
        return {"app_id": app_id, "app_secret": app_secret, "sandbox": sandbox == "true"}
    except Exception:
        return {"app_id": "", "app_secret": "", "sandbox": True}

@router.post("/api/qq/config")
async def set_qq_config(config: QQConfig):
    from db.database import db
    await db.set_config("qq_app_id", config.app_id)
    await db.set_config("qq_app_secret", config.app_secret)
    await db.set_config("qq_sandbox", "true" if config.sandbox else "false")
    # 更新 adapter
    qq_adapter.app_id = config.app_id
    qq_adapter.app_secret = config.app_secret
    qq_adapter.base_url = "https://sandbox.api.sgroup.qq.com" if config.sandbox else "https://api.sgroup.qq.com"
    return {"status": "ok"}
