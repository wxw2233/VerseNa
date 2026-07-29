import time
from fastapi import APIRouter
from config import settings

router = APIRouter()

LOG_DIR = settings.DATA_DIR
LOG_FILE = LOG_DIR / "runtime.log"
MAX_LINES = 500  # 日志文件最多保留行数


def _log(level: str, tag: str, message: str):
    """写入运行日志"""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] [{level}] [{tag}] {message}\n"
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line)
        # 超过上限时截断
        if LOG_FILE.exists() and LOG_FILE.stat().st_size > 100_000:
            lines = LOG_FILE.read_text(encoding="utf-8", errors="replace").splitlines()
            LOG_FILE.write_text("\n".join(lines[-MAX_LINES:]) + "\n", encoding="utf-8")
    except Exception:
        pass


def log_info(tag: str, message: str):
    _log("INFO", tag, message)


def log_error(tag: str, message: str):
    _log("ERROR", tag, message)


def log_warn(tag: str, message: str):
    _log("WARN", tag, message)


@router.get("/api/logs")
async def get_logs(lines: int = 100):
    """获取最近 N 行运行日志"""
    if not LOG_FILE.exists():
        return {"lines": []}
    try:
        all_lines = LOG_FILE.read_text(encoding="utf-8", errors="replace").splitlines()
        return {"lines": all_lines[-lines:], "total": len(all_lines)}
    except Exception:
        return {"lines": [], "total": 0}


@router.delete("/api/logs")
async def clear_logs():
    """清空日志"""
    try:
        LOG_FILE.write_text("", encoding="utf-8")
        return {"status": "ok"}
    except Exception:
        return {"status": "error"}
