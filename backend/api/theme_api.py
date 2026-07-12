from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse
from themes.manager import theme_manager

router = APIRouter()

@router.get("/api/themes")
async def list_themes():
    return theme_manager.list_themes()

@router.get("/api/themes/{name}")
async def get_theme(name: str):
    try:
        return theme_manager.get_theme(name)
    except FileNotFoundError:
        raise HTTPException(404, f"Theme '{name}' not found")

@router.get("/api/themes/{name}/css", response_class=PlainTextResponse)
async def get_theme_css(name: str):
    try:
        return theme_manager.get_css(name)
    except FileNotFoundError:
        raise HTTPException(404, f"Theme CSS '{name}' not found")
