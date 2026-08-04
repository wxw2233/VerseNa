"""TTS 适配器 — 支持 OpenAI / Fish Audio / ElevenLabs / MiMo 等"""
import json
import base64
import httpx
from pathlib import Path
from db.database import db
from api.log_api import log_info, log_error


class TTSSynthesisError(RuntimeError):
    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


_AUDIO_MIME_TYPES = {
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".m4a": "audio/mp4",
    ".ogg": "audio/ogg",
    ".flac": "audio/flac",
}


async def _post_with_network_fallback(url: str, timeout: float, **kwargs):
    """代理不可用时重试直连，避免本机代理故障让 TTS 整体失效。"""
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            return await client.post(url, **kwargs)
    except httpx.TransportError as exc:
        log_info("TTS", f"代理或默认网络请求失败，尝试直连: {type(exc).__name__}")
        async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
            return await client.post(url, **kwargs)


def find_reference_audio(pack_id: str) -> tuple[Path, str]:
    """查找主题包参考音频，兼容源码内容目录和外置数据目录。"""
    from config import settings

    pack_id = (pack_id or "").strip()
    if not pack_id or pack_id in {".", ".."} or any(char in pack_id for char in "/\\"):
        raise TTSSynthesisError("当前会话未绑定有效主题包，无法选择参考音频", 422)

    search_dirs = [
        settings.CONTENT_DIR / "themepacks" / pack_id / "assets",
        settings.CONTENT_DIR / "themes" / pack_id / "assets",
        settings.DATA_DIR / "themepacks" / pack_id / "assets",
        settings.DATA_DIR / "themes" / pack_id / "assets",
    ]
    seen = set()
    for audio_dir in search_dirs:
        resolved = audio_dir.resolve()
        if resolved in seen or not resolved.is_dir():
            continue
        seen.add(resolved)
        files = [
            path for path in resolved.iterdir()
            if path.is_file() and path.suffix.lower() in _AUDIO_MIME_TYPES
        ]
        files.sort(key=lambda path: (not path.stem.lower().startswith("ref_audio"), path.name.lower()))
        if files:
            audio_path = files[0]
            return audio_path, _AUDIO_MIME_TYPES[audio_path.suffix.lower()]

    raise TTSSynthesisError(
        f"主题包“{pack_id}”中没有参考音频，请上传 ref_audio.mp3 或 ref_audio.wav",
        422,
    )


def _response_error(response) -> str:
    try:
        payload = response.json()
        error = payload.get("error", payload) if isinstance(payload, dict) else payload
        if isinstance(error, dict):
            detail = error.get("message") or error.get("detail") or error.get("code")
        else:
            detail = str(error)
    except Exception:
        detail = response.text
    return " ".join(str(detail or "").split())[:240]


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

    if not base_url and provider != "elevenlabs":
        raise TTSSynthesisError("TTS 提供商未配置 Base URL", 400)

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
        detail = _response_error(resp)
        log_error("TTS", f"API 返回 {resp.status_code}: {detail}")
        raise TTSSynthesisError(f"TTS 服务返回 HTTP {resp.status_code}: {detail or '未知错误'}")
    except TTSSynthesisError:
        raise
    except Exception as e:
        log_error("TTS", f"请求异常: {e}")
        raise TTSSynthesisError(f"无法连接 TTS 服务: {type(e).__name__}: {e}") from e


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
        detail = _response_error(resp)
        raise TTSSynthesisError(f"ElevenLabs 返回 HTTP {resp.status_code}: {detail or '未知错误'}")
    except TTSSynthesisError:
        raise
    except Exception as exc:
        raise TTSSynthesisError(f"无法连接 ElevenLabs: {type(exc).__name__}: {exc}") from exc


async def _mimo_tts(api_key: str, base_url: str, model: str, text: str, pack_id: str) -> bytes | None:
    """MiMo TTS — 使用 chat completions 接口 + base64 参考音频"""
    audio_path, mime_type = find_reference_audio(pack_id)
    try:
        audio_bytes = audio_path.read_bytes()
    except OSError as exc:
        raise TTSSynthesisError(f"无法读取参考音频 {audio_path.name}: {exc}", 422) from exc
    if not audio_bytes:
        raise TTSSynthesisError(f"参考音频 {audio_path.name} 是空文件", 422)

    ref_audio_b64 = base64.b64encode(audio_bytes).decode("ascii")

    voice_str = f"data:{mime_type};base64,{ref_audio_b64}"

    log_info(
        "TTS/MiMo",
        f"合成: model={model}, text_len={len(text)}, ref={audio_path.name}, ref_size={len(audio_bytes)}, audio_mime={mime_type}",
    )

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
            detail = _response_error(resp)
            log_error("TTS/MiMo", f"API 返回 {resp.status_code}: {detail}")
            raise TTSSynthesisError(
                f"MiMo TTS 返回 HTTP {resp.status_code}: {detail or '未知错误'}"
            )

        data = resp.json()
        audio_data = data.get("choices", [{}])[0].get("message", {}).get("audio", {}).get("data", "")
        if not audio_data:
            log_error("TTS/MiMo", f"响应中无音频数据: {json.dumps(data, ensure_ascii=False)[:300]}")
            raise TTSSynthesisError("MiMo TTS 响应中没有音频数据")

        result = base64.b64decode(audio_data, validate=True)
        if not result:
            raise TTSSynthesisError("MiMo TTS 返回了空音频")
        log_info("TTS/MiMo", f"合成成功，音频大小: {len(result)} bytes")
        return result

    except TTSSynthesisError:
        raise
    except Exception as e:
        log_error("TTS/MiMo", f"请求异常: {e}")
        raise TTSSynthesisError(f"无法连接 MiMo TTS: {type(e).__name__}: {e}") from e


async def tts_speak(pack_id: str, text: str) -> bytes | None:
    """完整的 TTS 流程：获取配置 → 获取 voice_id → 合成"""
    config = await get_tts_config()
    if not config:
        return None

    voice_id = await get_voice_id(pack_id) if pack_id else None

    return await synthesize(config, text, voice_id, pack_id=pack_id)
