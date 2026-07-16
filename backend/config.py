import os
from pathlib import Path

class Settings:
    PROJECT_NAME = "次元人格"
    VERSION = "0.1.0"
    HOST = "0.0.0.0"
    PORT = 8001
    DEBUG = True
    BASE_DIR = Path(__file__).parent
    DATA_DIR = BASE_DIR / "data"
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
