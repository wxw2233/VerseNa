import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from agent.react import ReActAgent
from agent.models.openai_adapter import OpenAIAdapter
from agent.memory import MemoryManager
from config import settings
from persona.manager import persona_manager

router = APIRouter()

def create_agent(api_key: str = None, base_url: str = None, model_name: str = None) -> ReActAgent:
    key = api_key or settings.DEFAULT_API_KEY
    url = base_url or settings.DEFAULT_API_BASE
    model = model_name or settings.DEFAULT_MODEL_NAME
    adapter = OpenAIAdapter(api_key=key, base_url=url, model_name=model)
    memory = MemoryManager()
    return ReActAgent(model=adapter, memory=memory)

@router.websocket("/ws/chat")
async def websocket_chat(ws: WebSocket):
    await ws.accept()
    agent = create_agent()

    try:
        while True:
            data = await ws.receive_text()
            msg = json.loads(data)

            session_id = msg.get("session_id", "default")
            content = msg.get("content", "")
            persona_name = msg.get("persona", "default")
            system_prompt = persona_manager.get_system_prompt(persona_name)
            emotion = persona_manager.get_emotion_engine(persona_name)
            emotion_state = emotion.pick_emotion()

            async for event in agent.run(session_id, content, system_prompt=system_prompt):
                await ws.send_text(json.dumps(event, ensure_ascii=False))

            done_msg = {"type": "done", "emotion": emotion_state.primary, "emoji": emotion_state.emoji}
            await ws.send_text(json.dumps(done_msg))

    except WebSocketDisconnect:
        pass
    except Exception as e:
        await ws.send_text(json.dumps({"type": "error", "content": str(e)}))
