import json
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()
THEMES_DIR = Path(__file__).parent.parent.parent / "themes"

class ThemeCreate(BaseModel):
    id: str
    name: str
    primary: str = "#7c5cfc"
    bg_primary: str = "#0f0f1a"
    bg_secondary: str = "#1a1a2e"
    text_primary: str = "#e8e8f0"
    text_secondary: str = "#8888aa"
    border: str = "#2a2a40"
    font: str = "Noto Sans SC"

@router.post("/api/themes/create")
async def create_theme(req: ThemeCreate):
    theme_dir = THEMES_DIR / req.id
    if theme_dir.exists():
        raise HTTPException(400, f"Theme '{req.id}' already exists")
    theme_dir.mkdir(parents=True, exist_ok=True)
    config = {
        "name": req.name,
        "version": "1.0.0",
        "author": "user",
        "colors": {
            "primary": req.primary,
            "bg-primary": req.bg_primary,
            "bg-secondary": req.bg_secondary,
            "text-primary": req.text_primary,
            "text-secondary": req.text_secondary,
            "border": req.border,
            "bubble-user": f"{req.primary}26",
            "bubble-agent": "rgba(30, 30, 50, 0.9)",
        },
        "font": req.font,
        "effects": {},
    }
    (theme_dir / "theme.json").write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    css = f""":root {{
  --primary: {req.primary};
  --bg-primary: {req.bg_primary};
  --bg-secondary: {req.bg_secondary};
  --text-primary: {req.text_primary};
  --text-secondary: {req.text_secondary};
  --border: {req.border};
  --bubble-user: {req.primary}26;
  --bubble-agent: rgba(30, 30, 50, 0.9);
}}
"""
    (theme_dir / "variables.css").write_text(css, encoding="utf-8")
    return {"status": "ok", "id": req.id}


@router.get("/api/themes/{theme_id}/full")
async def get_theme_full(theme_id: str):
    theme_dir = THEMES_DIR / theme_id
    config_path = theme_dir / "theme.json"
    css_path = theme_dir / "variables.css"
    if not config_path.exists():
        raise HTTPException(404, f"Theme '{theme_id}' not found")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    css = css_path.read_text(encoding="utf-8") if css_path.exists() else ""
    return {"id": theme_id, "config": config, "css": css}


@router.put("/api/themes/{theme_id}")
async def update_theme(theme_id: str, req: ThemeCreate):
    theme_dir = THEMES_DIR / theme_id
    if not theme_dir.exists():
        raise HTTPException(404, f"Theme '{theme_id}' not found")
    config = {
        "name": req.name,
        "version": "1.0.0",
        "author": "user",
        "colors": {
            "primary": req.primary,
            "bg-primary": req.bg_primary,
            "bg-secondary": req.bg_secondary,
            "text-primary": req.text_primary,
            "text-secondary": req.text_secondary,
            "border": req.border,
            "bubble-user": f"{req.primary}26",
            "bubble-agent": "rgba(30, 30, 50, 0.9)",
        },
        "font": req.font,
        "effects": {},
    }
    (theme_dir / "theme.json").write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    css = f""":root {{
  --primary: {req.primary};
  --bg-primary: {req.bg_primary};
  --bg-secondary: {req.bg_secondary};
  --text-primary: {req.text_primary};
  --text-secondary: {req.text_secondary};
  --border: {req.border};
  --bubble-user: {req.primary}26;
  --bubble-agent: rgba(30, 30, 50, 0.9);
}}
"""
    (theme_dir / "variables.css").write_text(css, encoding="utf-8")
    return {"status": "ok"}
