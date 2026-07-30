from pathlib import Path
from fastapi import APIRouter, HTTPException
import shutil
from config import settings

router = APIRouter()
THEMES_DIR = settings.CONTENT_DIR / "themes"

@router.delete("/api/themes/{theme_id}")
async def delete_theme(theme_id: str):
    theme_dir = THEMES_DIR / theme_id
    if not theme_dir.exists():
        raise HTTPException(404, f"Theme '{theme_id}' not found")
    if theme_id == "default":
        raise HTTPException(400, "Cannot delete default theme")
    shutil.rmtree(theme_dir)
    return {"status": "ok"}
