from typing import Any

from agent.checkpoint import decode_checkpoint, encode_checkpoint
from db.database import db
from tools.base import BaseTool, ToolContext
from tools.results import tool_error, tool_result


MAX_TEXT = 1200
MAX_COMPLETED = 50


def _clean_text(value: Any) -> str:
    return str(value or "").strip()[:MAX_TEXT]


class TaskCheckpointTool(BaseTool):
    name = "task_checkpoint"
    description = (
        "持久化当前长任务的进度，避免刷新或中断后丢失上下文。可读取、更新或清除检查点；"
        "更新时只填写需要变更的字段。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["read", "update", "clear"],
                "description": "读取、合并更新或清除任务检查点",
            },
            "phase": {"type": "string", "description": "当前阶段"},
            "current": {"type": "string", "description": "当前正在处理的事项"},
            "completed": {
                "type": "array",
                "items": {"type": "string"},
                "description": "已经完成的关键事项列表",
            },
            "validation": {"type": "string", "description": "最近实际执行的验证及结果"},
            "next_step": {"type": "string", "description": "恢复任务后要做的下一步"},
            "risk": {"type": "string", "description": "风险、阻塞或待确认事项"},
            "port": {"type": "integer", "description": "相关服务端口"},
            "pid": {"type": "integer", "description": "相关服务进程 PID"},
            "notes": {"type": "string", "description": "其他短备注"},
        },
        "required": ["action"],
        "additionalProperties": False,
    }

    async def execute(
        self,
        action: str = "",
        phase: str = "",
        current: str = "",
        completed: list[str] | None = None,
        validation: str = "",
        next_step: str = "",
        risk: str = "",
        port: int | None = None,
        pid: int | None = None,
        notes: str = "",
        _context: ToolContext | None = None,
        **kwargs,
    ) -> str:
        if not _context:
            return tool_error("MISSING_CONTEXT", "工具执行上下文不可用")
        if action not in {"read", "update", "clear"}:
            return tool_error("INVALID_ACTION", "action 必须是 read、update 或 clear")

        if action == "clear":
            await db.set_session_meta(_context.session_id, task_checkpoint="{}")
            return tool_result(True, data={"checkpoint": {}}, message="任务检查点已清除")

        meta = await db.get_session_meta(_context.session_id)
        checkpoint = decode_checkpoint(meta.get("task_checkpoint"))
        if action == "read":
            return tool_result(True, data={"checkpoint": checkpoint}, message="任务检查点读取完成")

        updates = {
            "phase": _clean_text(phase),
            "current": _clean_text(current),
            "validation": _clean_text(validation),
            "next_step": _clean_text(next_step),
            "risk": _clean_text(risk),
            "notes": _clean_text(notes),
        }
        for key, value in updates.items():
            if value:
                checkpoint[key] = value
        if completed is not None:
            checkpoint["completed"] = [
                _clean_text(item) for item in completed[:MAX_COMPLETED] if _clean_text(item)
            ]
        if port is not None:
            checkpoint["port"] = int(port)
        if pid is not None:
            checkpoint["pid"] = int(pid)

        try:
            encoded = encode_checkpoint(checkpoint)
        except ValueError as exc:
            return tool_error("CHECKPOINT_TOO_LARGE", str(exc))
        await db.set_session_meta(_context.session_id, task_checkpoint=encoded)
        return tool_result(True, data={"checkpoint": checkpoint}, message="任务检查点已更新")


def register(registry):
    registry.register(TaskCheckpointTool())
