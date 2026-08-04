"""TTS 适配器 — 支持 OpenAI / Fish Audio / ElevenLabs / MiMo 等"""
import json
import base64
import httpx
from pathlib import Path
from db.database import db
from api.log_api import log_info, log_error


async def _post_with_network_fallback(url: str, timeout: float, **kwargs):
    """代理不可用时重试直连，避免本机代理故障让 TTS 整体失效。"""
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            return await client.post(url, **kwargs)
    except httpx.TransportError as exc:
        log_info("TTS", f"代理或默认网络请求失败，尝试直连: {type(exc).__name__}")
        async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
            return await client.post(url, **kwargs)


async def get_tts_config() -> dict | None:
    """从 active_models 读取 TTS 配置"""
    try:
        raw = await db.get_config("active_models", "{}")
        active = json.loads(raw) if raw else {}
        tts = active.get("tts", {})
        if not tts.get("provider") or not tts.get("model"):
            return None

        # 读取提供商的 api_key 和 base_url
        providers_raw = await db.get_config("model_providers", "{}")
        user_providers = json.loads(providers_raw) if providers_raw else {}
        user_conf = user_providers.get(tts["provider"], {})
        api_key = user_conf.get("api_key", "")
        base_url = user_conf.get("base_url", "")
        tts_endpoint = user_conf.get("tts_endpoint", "")

        # 预设提供商的 base_url
        if not base_url:
            from models.providers import get_provider
            preset = get_provider(tts["provider"])
            if preset:
                base_url = preset["base_url"]

        if not api_key:
            return None

        return {
            "provider": tts["provider"],
            "model": tts["model"],
            "api_key": api_key,
            "base_url": base_url,
            "tts_endpoint": tts_endpoint or "/audio/speech",
        }
    except Exception:
        return None


async def get_voice_id(pack_id: str) -> str | None:
    """获取缓存的 voice_id"""
    try:
        return await db.get_config(f"voice_id_{pack_id}", "")
    except Exception:
        return None


async def save_voice_id(pack_id: str, voice_id: str):
    """缓存 voice_id"""
    await db.set_config(f"voice_id_{pack_id}", voice_id)


async def clone_voice(tts_config: dict, audio_path: Path, pack_id: str) -> str | None:
    """上传参考音频克隆音色，返回 voice_id"""
    provider = tts_config["provider"]
    api_key = tts_config["api_key"]
    base_url = tts_config["base_url"].rstrip("/")

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            if provider == "openai":
                # OpenAI 不支持音色克隆，返回 None（使用预设音色）
                return None

            elif provider == "siliconflow":
                # SiliconFlow Fish Audio 克隆
                with open(audio_path, "rb") as f:
                    resp = await client.post(
                        f"{base_url}/audio/voice/clone",
                        headers={"Authorization": f"Bearer {api_key}"},
                        files={"audio": (audio_path.name, f, "audio/wav")},
                        data={"name": f"pack_{pack_id}"},
                    )
                if resp.status_code == 200:
                    data = resp.json()
                    voice_id = data.get("voice_id") or data.get("id", "")
                    if voice_id:
                        await save_voice_id(pack_id, voice_id)
                    return voice_id or None
                return None

            elif provider == "elevenlabs":
                # ElevenLabs 音色克隆
                with open(audio_path, "rb") as f:
                    resp = await client.post(
                        "https://api.elevenlabs.io/v1/voices/add",
                        headers={"xi-api-key": api_key},
                        files={"files": (audio_path.name, f, "audio/wav")},
                        data={"name": f"pack_{pack_id}"},
                    )
                if resp.status_code == 200:
                    data = resp.json()
                    voice_id = data.get("voice_id", "")
                    if voice_id:
                        await save_voice_id(pack_id, voice_id)
                    return voice_id or None
                return None

            else:
                # 通用 OpenAI 兼容提供商（自定义等）— 尝试克隆
                try:
                    with open(audio_path, "rb") as f:
                        resp = await client.post(
                            f"{base_url}/audio/voice/clone",
                            headers={"Authorization": f"Bearer {api_key}"},
                            files={"audio": (audio_path.name, f, "audio/wav")},
                            data={"name": f"pack_{pack_id}"},
                        )
                    if resp.status_code == 200:
                        data = resp.json()
                        voice_id = data.get("voice_id") or data.get("id", "")
                        if voice_id:
                            await save_voice_id(pack_id, voice_id)
                        return voice_id or None
                except Exception:
                    pass
                return None

    except Exception:
        return None


async def synthesize(tts_config: dict, text: str, voice_id: str | None = None, pack_id: str = "") -> bytes | None:
    """调用 TTS 合成语音，返回音频 bytes。"""
    model = tts_config["model"]
    api_key = tts_config["api_key"]
    base_url = tts_config["base_url"].rstrip("/")
    provider = tts_config["provider"]

    # ElevenLabs 用专用 API
    if provider == "elevenlabs":
        return await _elevenlabs_tts(api_key, model, text, voice_id)

    # MiMo TTS — 用 chat completions 接口 + base64 音频
    if "mimo" in model.lower() and "tts" in model.lower():
        return await _mimo_tts(api_key, base_url, model, text, pack_id)

    # 其他所有提供商（OpenAI / SiliconFlow / 自定义等）统一 OpenAI 兼容格式
    voice = voice_id or "alloy"
    tts_endpoint = tts_config.get("tts_endpoint", "/audio/speech")

    log_info("TTS", f"合成请求: provider={provider}, model={model}, base_url={base_url}, endpoint={tts_endpoint}, voice={voice}, text_len={len(text)}")

    try:
        resp = await _post_with_network_fallback(
            f"{base_url}{tts_endpoint}",
            timeout=60,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "input": text,
                "voice": voice,
                "response_format": "mp3",
            },
        )
        if resp.status_code == 200:
            log_info("TTS", f"合成成功，音频大小: {len(resp.content)} bytes")
            return resp.content
        else:
            body = resp.text[:300]
            log_error("TTS", f"API 返回 {resp.status_code}: {body}")
            return None
    except Exception as e:
        log_error("TTS", f"请求异常: {e}")
        return None


async def _elevenlabs_tts(api_key: str, model: str, text: str, voice_id: str | None) -> bytes | None:
    """ElevenLabs 专用 TTS"""
    vid = voice_id or "21m00Tcm4TlvDq8ikWAM"
    try:
        resp = await _post_with_network_fallback(
            f"https://api.elevenlabs.io/v1/text-to-speech/{vid}",
            timeout=60,
            headers={
                "xi-api-key": api_key,
                "Content-Type": "application/json",
            },
            json={
                "text": text,
                "model_id": model or "eleven_multilingual_v2",
                "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
            },
        )
        if resp.status_code == 200:
            return resp.content
        return None
    except Exception:
        return None


async def _mimo_tts(api_key: str, base_url: str, model: str, text: str, pack_id: str) -> bytes | None:
    """MiMo TTS — 使用 chat completions 接口 + base64 参考音频"""
    from config import settings

    # 查找参考音频（多个可能的目录）
    ref_audio_b64 = None
    mime_type = "audio/mpeg"

    search_dirs = [
        settings.CONTENT_DIR / "themepacks" / pack_id / "assets",
        settings.CONTENT_DIR / "themes" / pack_id / "assets",
        settings.DATA_DIR / "themes" / pack_id / "assets",
    ]

    for audio_dir in search_dirs:
        if not audio_dir.exists():
            continue
        for ext, mime in [("mp3", "audio/mpeg"), ("wav", "audio/wav"), ("m4a", "audio/mpeg")]:
            candidates = list(audio_dir.glob(f"ref_audio.{ext}")) or list(audio_dir.glob(f"*.{ext}"))
            if candidates:
                with open(candidates[0], "rb") as f:
                    ref_audio_b64 = base64.b64encode(f.read()).decode("utf-8")
                mime_type = mime
                break
        if ref_audio_b64:
            break

    if not ref_audio_b64:
        log_error("TTS/MiMo", "未找到参考音频，请在主题包素材中上传音频")
        return None

    voice_str = f"data:{mime_type};base64,{ref_audio_b64}"

    log_info("TTS/MiMo", f"合成: model={model}, text_len={len(text)}, audio_mime={mime_type}")

    try:
        resp = await _post_with_network_fallback(
            f"{base_url}/chat/completions",
            timeout=120,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [
                    {"role": "user", "content": ""},
                    {"role": "assistant", "content": text},
                ],
                "audio": {
                    "format": "wav",
                    "voice": voice_str,
                },
            },
        )
        if resp.status_code != 200:
            body = resp.text[:300]
            log_error("TTS/MiMo", f"API 返回 {resp.status_code}: {body}")
            return None

        data = resp.json()
        audio_data = data.get("choices", [{}])[0].get("message", {}).get("audio", {}).get("data", "")
        if not audio_data:
            log_error("TTS/MiMo", f"响应中无音频数据: {json.dumps(data, ensure_ascii=False)[:300]}")
            return None

        audio_bytes = base64.b64decode(audio_data)
        log_info("TTS/MiMo", f"合成成功，音频大小: {len(audio_bytes)} bytes")
        return audio_bytes

    except Exception as e:
        log_error("TTS/MiMo", f"请求异常: {e}")
        return None


async def tts_speak(pack_id: str, text: str) -> bytes | None:
    """完整的 TTS 流程：获取配置 → 获取 voice_id → 合成"""
    config = await get_tts_config()
    if not config:
        return None

    voice_id = await get_voice_id(pack_id) if pack_id else None

    return await synthesize(config, text, voice_id, pack_id=pack_id)
