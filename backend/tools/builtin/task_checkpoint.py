from typing import Any

from agent.checkpoint import decode_checkpoint, encode_checkpoint
from agent.task_state import (
    acceptance_ready,
    build_self_check,
    normalize_task_state,
    refresh_self_check,
    transition,
    recovery_check,
    TASK_STATE_VERSION,
)
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
            "active_goal": {"type": "string", "description": "当前冻结的用户目标"},
            "goal_mode": {
                "type": "string",
                "enum": ["continue", "refine", "append", "replace", "shrink", "report_only", "pause"],
                "description": "本次目标状态变化类型",
            },
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
            "pending": {"type": "array", "items": {"type": "string"}},
            "verified": {"type": "array", "items": {"type": "string"}},
            "unverified": {"type": "array", "items": {"type": "string"}},
            "do_not_do": {"type": "array", "items": {"type": "string"}},
            "approved_actions": {"type": "array", "items": {"type": "string"}},
            "forbidden_actions": {"type": "array", "items": {"type": "string"}},
            "boundary_cases": {
                "type": "array",
                "items": {"type": "object"},
                "description": "可执行边界场景及其验证状态",
            },
            "acceptance_matrix": {
                "type": "array",
                "items": {"type": "object"},
                "description": "需求验收矩阵，状态必须有证据",
            },
        },
        "required": ["action"],
        "additionalProperties": False,
    }

    async def execute(
        self,
        action: str = "",
        phase: str = "",
        active_goal: str = "",
        current: str = "",
        completed: list[str] | None = None,
        validation: str = "",
        next_step: str = "",
        risk: str = "",
        port: int | None = None,
        pid: int | None = None,
        notes: str = "",
        pending: list[str] | None = None,
        verified: list[str] | None = None,
        unverified: list[str] | None = None,
        do_not_do: list[str] | None = None,
        goal_mode: str = "",
        approved_actions: list[str] | None = None,
        forbidden_actions: list[str] | None = None,
        boundary_cases: list[dict[str, Any]] | None = None,
        acceptance_matrix: list[dict[str, Any]] | None = None,
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
        checkpoint = normalize_task_state(
            decode_checkpoint(meta.get("task_checkpoint")),
            _context.workspace,
        )
        if action == "read":
            recovery = recovery_check(checkpoint, _context.workspace)
            return tool_result(True, data={"checkpoint": checkpoint, "recovery": recovery}, message="任务检查点读取完成")

        updates = {
            "current": _clean_text(current),
            "validation": _clean_text(validation),
            "next_step": _clean_text(next_step),
            "risk": _clean_text(risk),
            "notes": _clean_text(notes),
        }
        for key, value in updates.items():
            if value:
                checkpoint[key] = value
        if active_goal:
            previous_goal = checkpoint.get("active_goal")
            if previous_goal and previous_goal != active_goal:
                checkpoint.setdefault("superseded_goals", []).append(_clean_text(previous_goal))
                checkpoint["pending"] = []
                checkpoint["unverified"] = []
                checkpoint["acceptance_matrix"] = []
                checkpoint["goal_version"] = max(1, int(checkpoint.get("goal_version") or 0) + 1)
            checkpoint["active_goal"] = _clean_text(active_goal)
            if not goal_mode:
                goal_mode = "replace" if previous_goal and previous_goal != active_goal else "refine"
        if goal_mode:
            if goal_mode not in {"continue", "refine", "append", "replace", "shrink", "report_only", "pause"}:
                return tool_error("INVALID_GOAL_MODE", "goal_mode 不受支持")
            checkpoint["goal_mode"] = goal_mode
        if completed is not None:
            checkpoint["completed"] = [
                _clean_text(item) for item in completed[:MAX_COMPLETED] if _clean_text(item)
            ]
        if port is not None:
            checkpoint["port"] = int(port)
        if pid is not None:
            checkpoint["pid"] = int(pid)
        for key, values in (
            ("pending", pending), ("verified", verified),
            ("unverified", unverified), ("do_not_do", do_not_do),
        ):
            if values is not None:
                checkpoint[key] = [_clean_text(item) for item in values[:MAX_COMPLETED] if _clean_text(item)]
        for key, values in (
            ("approved_actions", approved_actions),
            ("forbidden_actions", forbidden_actions),
        ):
            if values is not None:
                checkpoint[key] = [_clean_text(item) for item in values[:MAX_COMPLETED] if _clean_text(item)]
        if boundary_cases is not None:
            checkpoint["boundary_cases"] = boundary_cases[:MAX_COMPLETED]
        if acceptance_matrix is not None:
            checkpoint["acceptance_matrix"] = acceptance_matrix[:MAX_COMPLETED]

        if phase:
            canonical = normalize_task_state({"phase": phase}, _context.workspace)["phase"]
            if canonical == "completed" and not acceptance_ready(checkpoint):
                return tool_error(
                    "ACCEPTANCE_INCOMPLETE",
                    "当前检查点仍有未验证项、待办项或不完整的验收证据，不能标记为完成。",
                    data={"checkpoint": checkpoint},
                )
            if checkpoint.get("phase") == "created" and canonical not in {"created", "investigating"}:
                # Preserve strict transitions for an existing task while
                # allowing the first explicit checkpoint to declare its phase.
                transition(checkpoint, "investigating", reason="开始记录任务阶段")
            if not transition(checkpoint, canonical, reason=current or phase):
                return tool_error("INVALID_PHASE_TRANSITION", f"不能从 {checkpoint.get('phase')} 转移到 {phase}")
            checkpoint["phase_label"] = _clean_text(phase)
            checkpoint["state_phase"] = canonical
        checkpoint = refresh_self_check(checkpoint, _context.workspace)
        checkpoint["version"] = TASK_STATE_VERSION
        checkpoint["phase_label"] = checkpoint.get("phase_label") or checkpoint.get("phase")
        try:
            encoded = encode_checkpoint(checkpoint)
        except ValueError as exc:
            return tool_error("CHECKPOINT_TOO_LARGE", str(exc))
        await db.set_session_meta(_context.session_id, task_checkpoint=encoded)
        response_checkpoint = dict(checkpoint)
        # Keep the legacy human-readable phase field for existing clients;
        # state_phase is the canonical state-machine value.
        response_checkpoint["phase"] = checkpoint.get("phase_label") or checkpoint.get("phase")
        return tool_result(True, data={"checkpoint": response_checkpoint}, message="任务检查点已更新")


def register(registry):
    registry.register(TaskCheckpointTool())
