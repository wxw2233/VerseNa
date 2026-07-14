import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from agent.react import ReActAgent
from agent.models.openai_adapter import OpenAIAdapter
from agent.memory import MemoryManager
from config import settings
from persona.manager import persona_manager
from tools.registry import tool_registry

router = APIRouter()

def create_agent(api_key: str = None, base_url: str = None, model_name: str = None) -> ReActAgent:
    key = api_key or settings.DEFAULT_API_KEY
    url = base_url or settings.DEFAULT_API_BASE
    model = model_name or settings.DEFAULT_MODEL_NAME
    adapter = OpenAIAdapter(api_key=key, base_url=url, model_name=model)
    memory = MemoryManager()
    return ReActAgent(model=adapter, memory=memory, tool_registry=tool_registry)

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
            tool_desc = "\n".join(f"- {t['function']['name']}: {t['function']['description']}" for t in tool_registry.get_tools())
            system_prompt += f"\n\n## 可用工具\n你有以下工具可以调用，请在需要时主动使用：\n{tool_desc}\n\n使用工具时请通过 function calling 调用，不要直接告诉用户你没有工具。"
            system_prompt += "\n\n## 重要：你必须始终使用中文回复，不要使用英文。"
            emotion = persona_manager.get_emotion_engine(persona_name)
            emotion_state = emotion.pick_emotion()

            try:
                async for event in agent.run(session_id, content, system_prompt=system_prompt, tools=tool_registry.get_tools(), persona=persona_name):
                    await ws.send_text(json.dumps(event, ensure_ascii=False))
            except Exception as e:
                try:
                    await ws.send_text(json.dumps({"type": "error", "content": str(e)}, ensure_ascii=False))
                except:
                    pass

            # 确保 done 消息总是发送
            try:
                done_msg = {"type": "done", "emotion": emotion_state.primary, "emoji": emotion_state.emoji}
                await ws.send_text(json.dumps(done_msg))
            except:
                pass

    except WebSocketDisconnect:
        pass
    except Exception:
        pass
