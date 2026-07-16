from fastapi import APIRouter
from pydantic import BaseModel
from adapters.qq_bot import QQBotAdapter
from agent.react import ReActAgent
from agent.memory import MemoryManager
from agent.models.openai_adapter import OpenAIAdapter
from persona.manager import persona_manager
from tools.registry import tool_registry
from config import settings

router = APIRouter()
qq_adapter = QQBotAdapter()


async def handle_qq_message(msg):
    """处理 QQ 收到的消息"""
    if not msg.content:
        return

    system_prompt = persona_manager.get_system_prompt("default")
    tool_desc = "\n".join(f"- {t['function']['name']}: {t['function']['description']}" for t in tool_registry.get_tools())
    system_prompt += f"\n\n## 可用工具\n{tool_desc}\n\n使用工具时请通过 function calling 调用。"
    system_prompt += "\n\n## 重要：你必须始终使用中文回复，不要使用英文。"

    adapter = OpenAIAdapter(api_key=settings.DEFAULT_API_KEY, base_url=settings.DEFAULT_API_BASE, model_name=settings.DEFAULT_MODEL_NAME)
    memory = MemoryManager(model=adapter)
    agent = ReActAgent(model=adapter, memory=memory, tool_registry=tool_registry)

    full_reply = ""
    async for event in agent.run(f"qq_{msg.user_id}", msg.content, system_prompt=system_prompt, tools=tool_registry.get_tools()):
        if event["type"] == "segment":
            seg = event.get("segment", {})
            if seg.get("type") == "text":
                full_reply += seg.get("content", "")

    if full_reply:
        await qq_adapter.send(msg.channel_id, full_reply[:2000], msg_type=msg.msg_type)


# 注册消息回调
qq_adapter.on_message(handle_qq_message)


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
        return {
            "app_id": app_id,
            "app_secret": app_secret,
            "sandbox": sandbox == "true",
            "bot_status": "已连接" if qq_adapter.ws else "未连接",
        }
    except Exception:
        return {"app_id": "", "app_secret": "", "sandbox": True, "bot_status": "未连接"}


@router.post("/api/qq/config")
async def set_qq_config(config: QQConfig):
    from db.database import db
    await db.set_config("qq_app_id", config.app_id)
    await db.set_config("qq_app_secret", config.app_secret)
    await db.set_config("qq_sandbox", "true" if config.sandbox else "false")

    # 更新 adapter
    qq_adapter.app_id = config.app_id
    qq_adapter.app_secret = config.app_secret
    qq_adapter.sandbox = config.sandbox

    # 尝试连接
    success = await qq_adapter.start()
    return {"status": "ok", "bot_status": "已连接" if success else "连接失败，请检查 App ID 和 Secret"}


async def load_qq_config():
    """启动时加载 QQ Bot 配置并尝试连接"""
    from db.database import db
    try:
        app_id = await db.get_config("qq_app_id", "")
        app_secret = await db.get_config("qq_app_secret", "")
        sandbox = await db.get_config("qq_sandbox", "true") == "true"
        if app_id and app_secret:
            qq_adapter.app_id = app_id
            qq_adapter.app_secret = app_secret
            qq_adapter.sandbox = sandbox
            await qq_adapter.start()
    except Exception:
        pass
