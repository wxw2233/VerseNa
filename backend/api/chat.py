import json
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from agent.react import ReActAgent
from agent.models.openai_adapter import OpenAIAdapter
from agent.memory import MemoryManager
from config import settings
from persona.manager import persona_manager
from tools.registry import tool_registry

router = APIRouter()

# 待确认的请求 {request_id: asyncio.Future}
pending_confirms = {}

def create_agent(api_key: str = None, base_url: str = None, model_name: str = None) -> ReActAgent:
    key = api_key or settings.DEFAULT_API_KEY
    url = base_url or settings.DEFAULT_API_BASE
    model = model_name or settings.DEFAULT_MODEL_NAME
    adapter = OpenAIAdapter(api_key=key, base_url=url, model_name=model)
    memory = MemoryManager(model=adapter)
    # 注入 memory_manager 到 save_memory 工具
    save_mem_tool = tool_registry.get_tool('save_memory')
    if save_mem_tool:
        save_mem_tool._memory = memory
    return ReActAgent(model=adapter, memory=memory, tool_registry=tool_registry)

@router.websocket("/ws/chat")
async def websocket_chat(ws: WebSocket):
    await ws.accept()
    agent = create_agent()

    async def confirm_callback(confirm_data):
        """等待前端确认的回调"""
        request_id = confirm_data.get('request_id', '')
        loop = asyncio.get_event_loop()
        future = loop.create_future()
        pending_confirms[request_id] = future
        try:
            return await asyncio.wait_for(future, timeout=60)
        except asyncio.TimeoutError:
            return False
        finally:
            pending_confirms.pop(request_id, None)

    try:
        while True:
            data = await ws.receive_text()
            msg = json.loads(data)

            # 处理前端确认响应
            if msg.get('type') == 'confirm_response':
                request_id = msg.get('request_id', '')
                future = pending_confirms.get(request_id)
                if future and not future.done():
                    future.set_result(msg.get('confirmed', False))
                continue

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
                async for event in agent.run(session_id, content, system_prompt=system_prompt, tools=tool_registry.get_tools(), persona=persona_name, confirm_callback=confirm_callback):
                    await ws.send_text(json.dumps(event, ensure_ascii=False))
            except Exception as e:
                try:
                    await ws.send_text(json.dumps({"type": "error", "content": str(e)}, ensure_ascii=False))
                except Exception:
                    pass

            # 确保 done 消息总是发送
            try:
                done_msg = {"type": "done", "emotion": emotion_state.primary, "emoji": emotion_state.emoji}
                await ws.send_text(json.dumps(done_msg))
            except Exception:
                pass

    except WebSocketDisconnect:
        pass
    except Exception:
        pass
