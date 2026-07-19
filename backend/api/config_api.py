import json
import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from config import settings
from db.database import db
from models.providers import get_all_providers, get_provider, PROVIDER_PRESETS

router = APIRouter()


# ========== 旧版单模型配置（保持向后兼容） ==========

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


# ========== 新版多模型提供商配置 ==========

async def _get_user_providers() -> dict:
    """获取用户已保存的提供商配置"""
    raw = await db.get_config("model_providers", "{}")
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}

async def _save_user_providers(providers: dict):
    """保存用户提供商配置"""
    await db.set_config("model_providers", json.dumps(providers, ensure_ascii=False))

async def _get_active_models() -> dict:
    """获取当前激活的模型角色"""
    raw = await db.get_config("active_models", "{}")
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}

async def _save_active_models(models: dict):
    """保存激活的模型角色"""
    await db.set_config("active_models", json.dumps(models, ensure_ascii=False))


@router.get("/api/models/providers")
async def list_providers():
    """返回所有提供商（预设 + 用户自定义），附带用户配置的 API Key 状态"""
    presets = get_all_providers()
    user_providers = await _get_user_providers()

    result = []
    for pid, preset in presets.items():
        user_conf = user_providers.get(pid, {})
        # 合并预设和用户配置的 vision/image 模型
        user_vision = user_conf.get("vision_models", [])
        user_image = user_conf.get("image_models", [])
        result.append({
            **preset,
            "has_key": bool(user_conf.get("api_key")),
            "enabled": user_conf.get("enabled", False),
            "selected_models": user_conf.get("selected_models", []),
            "vision_models": user_vision if user_vision else preset.get("vision_models", []),
            "image_models": user_image if user_image else preset.get("image_models", []),
        })

    # 添加用户自定义提供商
    for pid, conf in user_providers.items():
        if pid not in presets and conf.get("is_custom"):
            result.append({
                "id": pid,
                "name": conf.get("name", pid),
                "base_url": conf.get("base_url", ""),
                "tts_endpoint": conf.get("tts_endpoint", ""),
                "models": conf.get("models", []),
                "vision_models": conf.get("vision_models", []),
                "image_models": conf.get("image_models", []),
                "is_custom": True,
                "has_key": bool(conf.get("api_key")),
                "enabled": conf.get("enabled", False),
                "selected_models": conf.get("selected_models", []),
            })

    return result


class ProviderSaveReq(BaseModel):
    provider_id: str
    api_key: str = ""
    base_url: str = ""
    tts_endpoint: str = ""
    name: str = ""
    enabled: bool = True
    selected_models: list[str] = []
    vision_models: list[str] = []
    image_models: list[str] = []
    is_custom: bool = False

@router.post("/api/models/providers")
async def save_provider(req: ProviderSaveReq):
    """保存/更新提供商配置"""
    user_providers = await _get_user_providers()

    existing = user_providers.get(req.provider_id, {})

    user_providers[req.provider_id] = {
        "api_key": req.api_key or existing.get("api_key", ""),
        "enabled": req.enabled,
        "selected_models": req.selected_models or existing.get("selected_models", []),
        "is_custom": req.is_custom,
        "base_url": req.base_url or existing.get("base_url", ""),
        "tts_endpoint": req.tts_endpoint or existing.get("tts_endpoint", ""),
        "name": req.name or existing.get("name", ""),
        "vision_models": req.vision_models or existing.get("vision_models", []),
        "image_models": req.image_models or existing.get("image_models", []),
    }

    await _save_user_providers(user_providers)

    # 同步更新旧版单模型配置（兼容）
    active = await _get_active_models()
    if active.get("chat", {}).get("provider") == req.provider_id:
        model = active["chat"].get("model", "")
        if model:
            preset = get_provider(req.provider_id) or {}
            base_url = req.base_url or preset.get("base_url", settings.DEFAULT_API_BASE)
            api_key = req.api_key or existing.get("api_key", "")
            settings.DEFAULT_API_KEY = api_key
            settings.DEFAULT_API_BASE = base_url
            settings.DEFAULT_MODEL_NAME = model
            await db.set_config("api_key", api_key)
            await db.set_config("api_base", base_url)
            await db.set_config("model_name", model)

    return {"status": "ok"}


class ProviderTestReq(BaseModel):
    provider_id: str
    api_key: str
    base_url: str = ""

@router.post("/api/models/providers/test")
async def test_provider(req: ProviderTestReq):
    """测试连接并拉取模型列表"""
    # 如果 api_key 为空，使用已保存的 key
    api_key = req.api_key
    if not api_key:
        user_providers = await _get_user_providers()
        user_conf = user_providers.get(req.provider_id, {})
        api_key = user_conf.get("api_key", "")
        if not api_key:
            return {"success": False, "error": "未保存 API Key", "models": []}

    preset = get_provider(req.provider_id)
    if preset:
        base_url = preset["base_url"]
    elif req.base_url:
        base_url = req.base_url
    else:
        raise HTTPException(400, "未知提供商，请提供 base_url")

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{base_url}/models",
                headers={"Authorization": f"Bearer {api_key}"}
            )
            if resp.status_code != 200:
                return {"success": False, "error": f"HTTP {resp.status_code}: {resp.text[:200]}", "models": []}
            data = resp.json()
            models = [m["id"] for m in data.get("data", [])]
            return {"success": True, "models": models}
    except Exception as e:
        return {"success": False, "error": str(e), "models": []}


@router.delete("/api/models/providers/{provider_id}")
async def delete_provider(provider_id: str):
    """删除自定义提供商"""
    user_providers = await _get_user_providers()
    if provider_id not in user_providers:
        raise HTTPException(404, "提供商不存在")
    if provider_id in PROVIDER_PRESETS:
        # 预设提供商只能清空配置，不能删除
        user_providers[provider_id] = {"api_key": "", "enabled": False, "selected_models": []}
    else:
        del user_providers[provider_id]
    await _save_user_providers(user_providers)
    return {"status": "ok"}


@router.get("/api/models/active")
async def get_active_models():
    """获取当前激活的模型角色"""
    active = await _get_active_models()
    # 填充默认值
    return {
        "chat": active.get("chat", {"provider": "", "model": ""}),
        "vision": active.get("vision", {"provider": "", "model": ""}),
        "image_gen": active.get("image_gen", {"provider": "", "model": ""}),
        "tts": active.get("tts", {"provider": "", "model": ""}),
    }

class ActiveModelReq(BaseModel):
    role: str  # "chat" | "vision" | "image_gen"
    provider: str
    model: str

@router.post("/api/models/active")
async def set_active_model(req: ActiveModelReq):
    """设置某个角色的激活模型"""
    if req.role not in ("chat", "vision", "image_gen", "tts"):
        raise HTTPException(400, "无效的角色类型")

    active = await _get_active_models()
    active[req.role] = {"provider": req.provider, "model": req.model}
    await _save_active_models(active)

    # 如果是 chat 角色，同步更新旧版配置
    if req.role == "chat":
        user_providers = await _get_user_providers()
        preset = get_provider(req.provider)
        user_conf = user_providers.get(req.provider, {})
        base_url = user_conf.get("base_url") or (preset["base_url"] if preset else "")
        api_key = user_conf.get("api_key", "")
        settings.DEFAULT_API_KEY = api_key
        settings.DEFAULT_API_BASE = base_url
        settings.DEFAULT_MODEL_NAME = req.model
        await db.set_config("api_key", api_key)
        await db.set_config("api_base", base_url)
        await db.set_config("model_name", req.model)

    return {"status": "ok"}


# ========== 信任模式 ==========

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


# ========== 启动时加载 ==========

async def load_saved_config():
    """启动时从数据库加载已保存的模型配置"""
    try:
        # 优先从新版 active_models 加载
        active = await _get_active_models()
        chat_config = active.get("chat", {})
        if chat_config.get("provider") and chat_config.get("model"):
            user_providers = await _get_user_providers()
            provider_id = chat_config["provider"]
            preset = get_provider(provider_id)
            user_conf = user_providers.get(provider_id, {})
            api_key = user_conf.get("api_key", "")
            base_url = user_conf.get("base_url") or (preset["base_url"] if preset else settings.DEFAULT_API_BASE)
            model_name = chat_config["model"]
            if api_key:
                settings.DEFAULT_API_KEY = api_key
            settings.DEFAULT_API_BASE = base_url
            settings.DEFAULT_MODEL_NAME = model_name
        else:
            # 回退到旧版单模型配置
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


# ========== Memory API ==========

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
