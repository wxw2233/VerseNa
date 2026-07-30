import json
from pathlib import Path
from config import settings

THEMES_DIR = settings.CONTENT_DIR / "themes"

class ThemeManager:
    @staticmethod
    def list_themes() -> list[dict]:
        result = []
        if not THEMES_DIR.exists():
            return result
        for d in THEMES_DIR.iterdir():
            config_path = d / "theme.json"
            if d.is_dir() and config_path.exists():
                config = json.loads(config_path.read_text(encoding="utf-8"))
                result.append({"id": d.name, "name": config.get("name", d.name)})
        return result

    @staticmethod
    def get_theme(name: str) -> dict:
        theme_dir = THEMES_DIR / name
        config_path = theme_dir / "theme.json"
        if not config_path.exists():
            raise FileNotFoundError(f"Theme '{name}' not found")
        return json.loads(config_path.read_text(encoding="utf-8"))

    @staticmethod
    def get_css(name: str) -> str:
        theme_dir = THEMES_DIR / name
        css_path = theme_dir / "variables.css"
        if not css_path.exists():
            raise FileNotFoundError(f"Theme CSS '{name}' not found")
        return css_path.read_text(encoding="utf-8")

theme_manager = ThemeManager()
