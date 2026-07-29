import os
from pathlib import Path

class Settings:
    PROJECT_NAME = "VerseNa"
    VERSION = "1.0.0"
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
    BASE_DIR = Path(__file__).parent
    DATA_DIR = Path(os.getenv("VERSENA_DATA_DIR", str(BASE_DIR / "data"))).expanduser().resolve()
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

settings = Settings()
