from pathlib import Path
from api.log_api import log_info, log_error
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from config import settings
from pet_config import read_pet_config

router = APIRouter()

@router.post("/api/themes/{theme_id}/rename/{filename}")
async def rename_asset(theme_id: str, filename: str, to: str = ""):
    """重命名素材文件"""
    theme_dir = THEMES_DIR / theme_id
    src = theme_dir / "assets" / filename
    dst = theme_dir / "assets" / to
    if src.exists():
        src.rename(dst)
        # Also sync to themepacks
        tm_dir = THEMES_DIR.parent / "themepacks" / theme_id / "assets"
        tm_src = tm_dir / filename
        if tm_src.exists():
            tm_src.rename(tm_dir / to)
        return {"status": "ok"}
    return {"status": "not_found"}
THEMES_DIR = settings.CONTENT_DIR / "themes"
PET_ACTIONS = ("idle", "blink", "walk", "jump", "wave", "thinking", "tool", "speaking", "working", "stopping", "done", "error")


@router.get("/api/themes/{theme_id}/pet-config")
async def get_pet_config(theme_id: str):
    return {"theme_id": theme_id, **read_pet_config(THEMES_DIR / theme_id / "theme.json")}

@router.get("/api/themes/{theme_id}/pet-assets")
async def list_pet_assets(theme_id: str):
    """Return ordered desktop-pet frames available for a theme."""
    assets_dir = THEMES_DIR / theme_id / "assets"
    result = {action: [] for action in PET_ACTIONS}
    if not assets_dir.exists():
        return result

    for action in PET_ACTIONS:
        result[action] = sorted(
            file.name for file in assets_dir.glob(f"pet-{action}-*") if file.is_file()
        )
    return result

@router.post("/api/themes/{theme_id}/upload")
async def upload_asset(theme_id: str, file: UploadFile = File(...)):
    """上传图片素材到主题的 assets 目录"""
    log_info("Asset", f"上传请求: theme={theme_id} file={file.filename} size={file.size if hasattr(file, 'size') else '?'}")
    theme_dir = THEMES_DIR / theme_id
    # 自动创建主题目录（新主题包首次上传时需要）
    theme_dir.mkdir(parents=True, exist_ok=True)

    assets_dir = theme_dir / "assets"
    assets_dir.mkdir(exist_ok=True)
    
    # 保留原始文件名，同名直接覆盖
    filename = file.filename
    target = assets_dir / filename

    # 如果上传的是音频文件（ref_audio），清理旧的不同格式的 ref_audio
    if filename.startswith("ref_audio."):
        for old in assets_dir.glob("ref_audio.*"):
            if old.name != filename:
                old.unlink(missing_ok=True)
        # 同步清理 themepacks 目录
        pack_assets_dir = THEMES_DIR.parent / "themepacks" / theme_id / "assets"
        if pack_assets_dir.exists():
            for old in pack_assets_dir.glob("ref_audio.*"):
                if old.name != filename:
                    old.unlink(missing_ok=True)

    content = await file.read()
    target.write_bytes(content)

    # 同步到 themepacks 目录
    pack_assets = THEMES_DIR.parent / "themepacks" / theme_id / "assets"
    if pack_assets.exists():
        (pack_assets / filename).write_bytes(content)

    return {
        "status": "ok",
        "filename": target.name,
        "path": f"assets/{target.name}",
        "size": len(content),
    }

@router.get("/api/themes/{theme_id}/assets/{filename}")
async def get_asset(theme_id: str, filename: str):
    """获取主题素材图片"""
    asset_path = THEMES_DIR / theme_id / "assets" / filename
    if not asset_path.exists():
        raise HTTPException(404, f"Asset '{filename}' not found")
    return FileResponse(str(asset_path))

@router.delete("/api/themes/{theme_id}/assets/{filename}")
async def delete_asset(theme_id: str, filename: str):
    """删除主题素材"""
    asset_path = THEMES_DIR / theme_id / "assets" / filename
    if not asset_path.exists():
        raise HTTPException(404, f"Asset '{filename}' not found")
    asset_path.unlink()
    return {"status": "ok"}
