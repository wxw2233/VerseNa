import json
from datetime import datetime, timezone
from typing import Any


def tool_result(
    success: bool,
    *,
    data: dict[str, Any] | None = None,
    error: str = "",
    message: str = "",
    result_type: str = "result",
    status: str | None = None,
    confidence: str | None = None,
    complete: bool | None = None,
    truncated: bool | None = None,
    continuation_token: str = "",
) -> str:
    resolved_status = status or ("success" if success else "failed")
    if complete is None:
        details = data or {}
        complete = bool(success) and not bool(
            details.get("truncated") or details.get("scan_truncated") or details.get("eof") is False
        )
    if truncated is None:
        details = data or {}
        truncated = bool(details.get("truncated") or details.get("scan_truncated") or details.get("eof") is False)
    payload: dict[str, Any] = {
        "type": result_type,
        "success": success,
        "status": resolved_status,
        "confidence": confidence or ("verified" if success and complete else "unknown"),
        "complete": bool(complete),
        "truncated": bool(truncated),
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    if continuation_token:
        payload["continuation_token"] = str(continuation_token)[:500]
    if data is not None:
        payload["data"] = data
    if error:
        payload["error"] = error
    if message:
        payload["message"] = message
    return json.dumps(payload, ensure_ascii=False)


def tool_error(error: str, message: str, *, data: dict[str, Any] | None = None) -> str:
    return tool_result(
        False,
        error=error,
        message=message,
        data=data,
        status="unavailable" if error in {"TOOL_NOT_FOUND", "SHELL_NOT_FOUND", "MEMORY_UNAVAILABLE"} else "failed",
        confidence="unknown",
        complete=False,
    )


def tool_confirm(request_id: str, action: str, message: str, **details: Any) -> str:
    payload = {
        "type": "confirm",
        "success": False,
        "status": "pending",
        "confidence": "unknown",
        "complete": False,
        "truncated": False,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "request_id": request_id,
        "action": action,
        "message": message,
        "data": details,
        **details,
    }
    return json.dumps(payload, ensure_ascii=False)
