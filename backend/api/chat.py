import json
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from agent.react import ReActAgent
from agent.models.openai_adapter import OpenAIAdapter
from agent.memory import MemoryManager
from config import settings
from persona.manager import persona_manager
from tools.registry import tool_registry
from api.log_api import log_info, log_error
from db.database import db
from models.providers import get_provider

router = APIRouter()

# 待确认的请求 {request_id: asyncio.Future}
pending_confirms = {}

async def create_agent(api_key: str = None, base_url: str = None, model_name: str = None) -> ReActAgent:
    """创建 Agent，优先使用新版多模型配置"""
    key = api_key
    url = base_url
    model = model_name

    # 如果没有显式指定，从 active_models 配置读取
    if not key or not url or not model:
        try:
            raw = await db.get_config("active_models", "{}")
            active = json.loads(raw) if raw else {}
            chat_config = active.get("chat", {})

            if chat_config.get("provider") and chat_config.get("model"):
                provider_id = chat_config["provider"]
                model = model or chat_config["model"]

                # 从用户提供商配置读取 key 和 url
                providers_raw = await db.get_config("model_providers", "{}")
                user_providers = json.loads(providers_raw) if providers_raw else {}
                user_conf = user_providers.get(provider_id, {})

                key = key or user_conf.get("api_key", "")
                preset = get_provider(provider_id)
                url = url or user_conf.get("base_url") or (preset["base_url"] if preset else "")
        except Exception:
            pass

    # 回退到 settings 默认值
    key = key or settings.DEFAULT_API_KEY
    url = url or settings.DEFAULT_API_BASE
    model = model or settings.DEFAULT_MODEL_NAME

    adapter = OpenAIAdapter(api_key=key, base_url=url, model_name=model)
    memory = MemoryManager(model=adapter)
    save_mem_tool = tool_registry.get_tool('save_memory')
    if save_mem_tool:
        save_mem_tool._memory = memory
    return ReActAgent(model=adapter, memory=memory, tool_registry=tool_registry)

@router.websocket("/ws/chat")
async def websocket_chat(ws: WebSocket):
    await ws.accept()
    agent = await create_agent()

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

    # 停止信号（每个连接独立）
    stop_event = asyncio.Event()
    msg_queue = asyncio.Queue()
    reader_done = False  # ws_reader 是否已退出

    # 后台持续读取 WebSocket 消息
    async def ws_reader():
        nonlocal reader_done
        try:
            while True:
                raw = await ws.receive_text()
                m = json.loads(raw)
                if m.get('type') == 'stop':
                    stop_event.set()
                elif m.get('type') == 'confirm_response':
                    rid = m.get('request_id', '')
                    fut = pending_confirms.get(rid)
                    if fut and not fut.done():
                        fut.set_result(m.get('confirmed', False))
                else:
                    await msg_queue.put(m)
        except Exception:
            pass
        finally:
            reader_done = True
            stop_event.set()  # 如果 Agent 正在运行，通知它停止
            await msg_queue.put(None)  # 唤醒主循环退出

    reader_task = asyncio.create_task(ws_reader())

    try:
        while True:
            msg = await msg_queue.get()
            if msg is None:
                # ws_reader 已退出（连接断开），结束主循环
                break

            session_id = msg.get("session_id", "default")
            content = msg.get("content", "")
            image_url = msg.get("image_url", "")
            log_info("Chat", f"WS消息: session={session_id} content={content[:80]} image={'yes' if image_url else 'no'}")
            persona_name = msg.get("persona", "default")

            # 处理 /skill install 命令
            if content.strip().startswith("/skill install"):
                url = content.strip().replace("/skill install", "").strip()
                if url:
                    from skills.manager import skill_manager
                    data, error = skill_manager.install_from_github(url)
                    if error:
                        await ws.send_text(json.dumps({"type": "segment", "segment": {"type": "text", "content": f"❌ 技能安装失败: {error}"}}, ensure_ascii=False))
                    else:
                        await ws.send_text(json.dumps({"type": "segment", "segment": {"type": "text", "content": f"✅ 技能「{data['name']}」安装成功！\n\n{data['description']}"}}, ensure_ascii=False))
                    await ws.send_text(json.dumps({"type": "done"}))
                    continue
                else:
                    await ws.send_text(json.dumps({"type": "segment", "segment": {"type": "text", "content": "用法: /skill install <github-repo-url>"}}, ensure_ascii=False))
                    await ws.send_text(json.dumps({"type": "done"}))
                    continue

            system_prompt = persona_manager.get_system_prompt(persona_name)

            # 注入技能列表（Agent 自动选择）
            from skills.manager import skill_manager
            skill_prompt = skill_manager.get_skill_prompt()
            if skill_prompt:
                system_prompt += f"\n\n{skill_prompt}"

            tool_desc = "\n".join(f"- {t['function']['name']}: {t['function']['description']}" for t in tool_registry.get_tools())
            system_prompt += f"\n\n## 可用工具\n你有以下工具可以调用，请在需要时主动使用：\n{tool_desc}\n\n使用工具时请通过 function calling 调用，不要直接告诉用户你没有工具。"
            system_prompt += "\n\n## 重要：你必须始终使用中文回复，不要使用英文。"

            available_tools = tool_registry.get_tools()
            emotion = persona_manager.get_emotion_engine(persona_name)
            emotion_state = emotion.pick_emotion()

            # 将情感状态注入系统提示词，让 Agent 的回复带有对应情感
            emotion_prompts = {
                "cheerful": "你现在心情很好，语气活泼开朗，积极向上。",
                "shy": "你现在有些害羞，语气略带羞涩和不好意思。",
                "curious": "你现在充满好奇，喜欢追问细节和深入探讨。",
                "angry": "你现在有些不满，语气略带抱怨和不耐烦。",
                "sad": "你现在心情低落，语气略带伤感和惆怅。",
            }
            if emotion_state.primary in emotion_prompts:
                system_prompt += f"\n\n## 当前情感\n{emotion_prompts[emotion_state.primary]}（情感强度：{emotion_state.intensity:.1f}）"

            # 读取 Agent 高级配置
            agent_config = {}
            try:
                from api.config_api import AGENT_CONFIG_DEFAULTS
                for key, default in AGENT_CONFIG_DEFAULTS.items():
                    raw = await db.get_config(f"agent_{key}", None)
                    if raw is None:
                        agent_config[key] = default
                    elif key in ("custom_instructions",):
                        agent_config[key] = raw
                    else:
                        try:
                            agent_config[key] = type(default)(raw)
                        except (ValueError, TypeError):
                            agent_config[key] = default
            except Exception:
                pass

            # 主题包角色的 temperature/top_p 覆盖全局配置
            try:
                persona_data = persona_manager.get_persona(persona_name)
                if persona_data.temperature is not None:
                    agent_config["temperature"] = persona_data.temperature
                if persona_data.top_p is not None:
                    agent_config["top_p"] = persona_data.top_p
            except Exception:
                pass

            tool_segments = []
            stop_event.clear()  # 新消息开始前清除停止信号
            try:
                async for event in agent.run(session_id, content, system_prompt=system_prompt, tools=available_tools, persona=persona_name, confirm_callback=confirm_callback, image_url=image_url if image_url else None, stop_event=stop_event, agent_config=agent_config):
                    await ws.send_text(json.dumps(event, ensure_ascii=False))
                    if event.get("type") == "segment" and event.get("segment", {}).get("type") == "tool":
                        tool_segments.append(event["segment"])
            except Exception as e:
                try:
                    await ws.send_text(json.dumps({"type": "error", "content": str(e)}, ensure_ascii=False))
                except Exception:
                    pass

            log_info("Chat", f"会话结束: session={session_id}")
            # 保存 tool segments
            if tool_segments:
                try:
                    # 去重：同 tool_call_id 只保留最后出现的状态
                    deduped = {}
                    for s in tool_segments:
                        deduped[s.get("tool_call_id", "")] = s
                    segments = list(deduped.values())
                    log_info("Chat", f"保存 {len(segments)} 个 tool segments")
                    await db.update_last_message_metadata(
                        session_id, "assistant",
                        {"segments": segments}
                    )
                except Exception as seg_e:
                    log_error("Chat", f"保存 segments 失败: {seg_e}")
            # 确保 done 消息总是发送
            try:
                done_msg = {"type": "done", "emotion": emotion_state.primary, "emoji": emotion_state.emoji}
                await ws.send_text(json.dumps(done_msg))
            except Exception:
                pass

    except WebSocketDisconnect:
        reader_task.cancel()
    except Exception:
        reader_task.cancel()
