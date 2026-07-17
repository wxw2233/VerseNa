from pathlib import Path
from api.log_api import log_info, log_error
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse

router = APIRouter()
THEMES_DIR = Path(__file__).parent.parent.parent / "themes"

@router.post("/api/themes/{theme_id}/upload")
async def upload_asset(theme_id: str, file: UploadFile = File(...)):
    """上传图片素材到主题的 assets 目录"""
    log_info("Asset", f"上传请求: theme={theme_id} file={file.filename} size={file.size if hasattr(file, 'size') else '?'}")
    theme_dir = THEMES_DIR / theme_id
    if not theme_dir.exists():
        raise HTTPException(404, f"Theme '{theme_id}' not found")
    
    assets_dir = theme_dir / "assets"
    assets_dir.mkdir(exist_ok=True)
    
    # 保留原始文件名，同名直接覆盖
    filename = file.filename
    target = assets_dir / filename
    
    content = await file.read()
    target.write_bytes(content)
    
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
