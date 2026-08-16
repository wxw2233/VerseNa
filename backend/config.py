import os
from pathlib import Path
from dotenv import load_dotenv


_BASE_DIR = Path(__file__).resolve().parent
load_dotenv(_BASE_DIR / ".env")

class Settings:
    PROJECT_NAME = "VerseNa"
    VERSION = "1.1.0"
    HOST = os.getenv("VERSENA_HOST", "127.0.0.1")
    PORT = int(os.getenv("VERSENA_PORT", "8002"))
    DEBUG = os.getenv("VERSENA_DEBUG", "false").lower() == "true"
    ALLOWED_ORIGINS = tuple(
        origin.strip()
        for origin in os.getenv(
            "VERSENA_ALLOWED_ORIGINS",
            "http://localhost:5173,http://127.0.0.1:5173,null",
        ).split(",")
        if origin.strip()
    )
    ACCESS_TOKEN = os.getenv("VERSENA_ACCESS_TOKEN", "").strip()
    AUTH_SESSION_TTL_SECONDS = int(os.getenv("VERSENA_AUTH_SESSION_TTL", "604800"))
    AUTH_COOKIE_SECURE = os.getenv("VERSENA_AUTH_COOKIE_SECURE", "false").lower() == "true"
    BASE_DIR = _BASE_DIR
    DATA_DIR = Path(os.getenv("VERSENA_DATA_DIR", str(BASE_DIR / "data"))).expanduser().resolve()
    CONTENT_DIR = Path(
        os.getenv("VERSENA_CONTENT_DIR", str(BASE_DIR.parent))
    ).expanduser().resolve()
    SKILLS_DATA_DIR = Path(
        os.getenv("VERSENA_SKILLS_DATA_DIR", str(BASE_DIR / "skills"))
    ).expanduser().resolve()
    TOOL_WORKSPACE = Path(
        os.getenv("VERSENA_TOOL_WORKSPACE") or str(DATA_DIR / "workspace")
    ).expanduser().resolve()
    ACCESS_TOKEN_FILE = Path(
        os.getenv("VERSENA_ACCESS_TOKEN_FILE", str(DATA_DIR / "access_token"))
    ).expanduser().resolve()
    SECRET_KEY = os.getenv("VERSENA_SECRET_KEY", "").strip()
    SECRET_KEY_FILE = Path(
        os.getenv(
            "VERSENA_SECRET_KEY_FILE",
            str(Path.home() / ".config" / "versena" / "secret.key"),
        )
    ).expanduser().resolve()
    FRONTEND_DIST = Path(
        os.getenv("VERSENA_FRONTEND_DIST", str(BASE_DIR.parent / "frontend" / "dist"))
    ).expanduser().resolve()
    DB_PATH = DATA_DIR / "ciyuan.db"
    DEFAULT_MODEL = "deepseek"
    DEFAULT_API_KEY = ""
    DEFAULT_API_BASE = "https://api.deepseek.com/v1"
    DEFAULT_MODEL_NAME = "deepseek-chat"
    MAX_REACT_LOOPS = 15
    MAX_CONTEXT_TOKENS = 4096

    @classmethod
    def ensure_dirs(cls):
        cls.DATA_DIR.mkdir(parents=True, exist_ok=True)
        cls.CONTENT_DIR.mkdir(parents=True, exist_ok=True)
        cls.SKILLS_DATA_DIR.mkdir(parents=True, exist_ok=True)
        cls.TOOL_WORKSPACE.mkdir(parents=True, exist_ok=True)

settings = Settings()
