import json
from typing import Any

from agent.task_state import compact_task_state, normalize_task_state, format_task_state


MAX_CHECKPOINT_BYTES = 12_000


def decode_checkpoint(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def encode_checkpoint(value: dict[str, Any]) -> str:
    normalized = compact_task_state(value)
    encoded = json.dumps(normalized, ensure_ascii=False, separators=(",", ":"))
    if len(encoded.encode("utf-8")) > MAX_CHECKPOINT_BYTES:
        raise ValueError(f"任务检查点不能超过 {MAX_CHECKPOINT_BYTES} 字节")
    return encoded


def format_checkpoint(value: dict[str, Any]) -> str:
    if not value:
        return "暂无任务检查点。"
    if value.get("version", 0) >= 2 or value.get("active_goal") or value.get("acceptance_matrix"):
        return format_task_state(normalize_task_state(value, value.get("workspace")))
    lines = []
    labels = (
        ("phase", "当前阶段"),
        ("current", "当前工作"),
        ("next_step", "下一步"),
        ("validation", "最近验证"),
        ("risk", "风险/阻塞"),
        ("port", "端口"),
        ("pid", "进程 PID"),
    )
    for key, label in labels:
        if value.get(key) not in (None, "", []):
            lines.append(f"- {label}: {value[key]}")
    completed = value.get("completed") or []
    if completed:
        lines.append("- 已完成: " + "；".join(str(item) for item in completed))
    notes = value.get("notes", "")
    if notes:
        lines.append(f"- 备注: {notes}")
    return "\n".join(lines) or "暂无任务检查点。"
