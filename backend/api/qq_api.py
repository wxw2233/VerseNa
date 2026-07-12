from fastapi import APIRouter, Request
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
