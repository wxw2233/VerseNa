import json
from typing import Any


def tool_result(
    success: bool,
    *,
    data: dict[str, Any] | None = None,
    error: str = "",
    message: str = "",
    result_type: str = "result",
) -> str:
    payload: dict[str, Any] = {
        "type": result_type,
        "success": success,
    }
    if data is not None:
        payload["data"] = data
    if error:
        payload["error"] = error
    if message:
        payload["message"] = message
    return json.dumps(payload, ensure_ascii=False)


def tool_error(error: str, message: str, *, data: dict[str, Any] | None = None) -> str:
    return tool_result(False, error=error, message=message, data=data)


def tool_confirm(request_id: str, action: str, message: str, **details: Any) -> str:
    payload = {
        "type": "confirm",
        "success": False,
        "request_id": request_id,
        "action": action,
        "message": message,
        "data": details,
        **details,
    }
    return json.dumps(payload, ensure_ascii=False)
