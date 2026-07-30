"""TTS API — 语音合成接口"""
import json
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from tts.adapter import get_tts_config, get_voice_id, save_voice_id, clone_voice, synthesize
from config import settings

router = APIRouter()


class TTSRequest(BaseModel):
    text: str
    pack_id: str = ""  # 主题包 ID，用于查找参考音频和 voice_id


@router.post("/api/tts/speak")
async def tts_speak(req: TTSRequest):
    """文字转语音"""
    if not req.text.strip():
        raise HTTPException(400, "文本不能为空")

    config = await get_tts_config()
    if not config:
        raise HTTPException(400, "未配置 TTS 模型，请在设置 → 模型配置 → 角色分配中配置语音合成模型")

    voice_id = None
    if req.pack_id:
        voice_id = await get_voice_id(req.pack_id)

    from api.log_api import log_info
    log_info("TTS", f"合成: pack={req.pack_id}, voice={voice_id}, provider={config['provider']}, model={config['model']}, base_url={config['base_url']}")

    audio = await synthesize(config, req.text, voice_id, pack_id=req.pack_id)
    if not audio:
        raise HTTPException(500, f"语音合成失败 (provider={config['provider']}, model={config['model']})，请查看监控日志")

    return Response(content=audio, media_type="audio/mpeg")


@router.post("/api/tts/clone")
async def tts_clone(pack_id: str):
    """为主题包克隆音色（上传参考音频到 TTS 服务）"""
    config = await get_tts_config()
    if not config:
        raise HTTPException(400, "未配置 TTS 模型")

    # 查找参考音频文件
    audio_dir = settings.DATA_DIR / "themes" / pack_id / "assets"
    audio_file = None
    for ext in ("wav", "mp3", "m4a", "ogg", "flac"):
        candidates = list(audio_dir.glob(f"ref_audio.*"))
        if not candidates:
            candidates = list(audio_dir.glob(f"*.{ext}"))
        if candidates:
            audio_file = candidates[0]
            break

    if not audio_file:
        raise HTTPException(404, "未找到参考音频，请先在主题包素材中上传音频")

    voice_id = await clone_voice(config, audio_file, pack_id)
    if voice_id:
        return {"status": "ok", "voice_id": voice_id}
    else:
        return {"status": "unsupported", "message": "当前 TTS 提供商不支持音色克隆，将使用默认音色"}


@router.get("/api/tts/status/{pack_id}")
async def tts_status(pack_id: str):
    """查询主题包的 TTS 状态"""
    config = await get_tts_config()
    voice_id = await get_voice_id(pack_id) if pack_id else None

    # 检查是否有参考音频
    has_ref_audio = False
    search_dirs = [
        settings.CONTENT_DIR / "themepacks" / pack_id / "assets",
        settings.CONTENT_DIR / "themes" / pack_id / "assets",
        settings.DATA_DIR / "themes" / pack_id / "assets",
    ]
    for audio_dir in search_dirs:
        if audio_dir.exists():
            for ext in ("wav", "mp3", "m4a", "ogg", "flac"):
                if list(audio_dir.glob(f"*.{ext}")):
                    has_ref_audio = True
                    break
        if has_ref_audio:
            break

    return {
        "tts_configured": config is not None,
        "has_ref_audio": has_ref_audio,
        "voice_id": voice_id or None,
        "provider": config["provider"] if config else None,
    }
