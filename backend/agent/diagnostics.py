from collections import deque
from datetime import datetime


class RuntimeDiagnostics:
    """Small in-process runtime snapshot used by the monitor UI."""

    def __init__(self):
        self._sessions = {}

    def _get(self, session_id):
        return self._sessions.setdefault(str(session_id), {
            "session_id": str(session_id),
            "active": False,
            "generation_id": "",
            "workspace": "",
            "max_context": 0,
            "max_steps": 0,
            "context_tokens": 0,
            "context_messages": 0,
            "started_at": "",
            "last_finished_at": "",
            "last_compaction": None,
            "tool_calls_total": 0,
            "tool_failures": 0,
            "repeated_blocks": 0,
            "recent_tools": deque(maxlen=20),
        })

    @staticmethod
    def _now():
        return datetime.now().isoformat(timespec="seconds")

    def start_generation(self, session_id, generation_id, workspace="", max_context=0, max_steps=0):
        state = self._get(session_id)
        state.update({
            "active": True,
            "generation_id": str(generation_id or ""),
            "workspace": str(workspace or ""),
            "max_context": int(max_context or 0),
            "max_steps": int(max_steps or 0),
            "context_tokens": 0,
            "context_messages": 0,
            "started_at": self._now(),
            "tool_calls_total": 0,
            "tool_failures": 0,
            "repeated_blocks": 0,
            "recent_tools": deque(maxlen=20),
        })

    def update_context(self, session_id, tokens, messages):
        state = self._get(session_id)
        state["context_tokens"] = int(tokens or 0)
        if messages is not None:
            state["context_messages"] = int(messages or 0)

    def finish_generation(self, session_id):
        state = self._get(session_id)
        state["active"] = False
        state["last_finished_at"] = self._now()

    def record_tool(self, session_id, tool_name, duration_ms, success, error="", blocked=False):
        state = self._get(session_id)
        state["tool_calls_total"] += 1
        if not success:
            state["tool_failures"] += 1
        if blocked:
            state["repeated_blocks"] += 1
        state["recent_tools"].append({
            "name": str(tool_name or ""),
            "duration_ms": int(duration_ms or 0),
            "success": bool(success),
            "error": str(error or ""),
            "blocked": bool(blocked),
            "at": self._now(),
        })

    def record_compaction(self, session_id, event):
        state = self._get(session_id)
        state["last_compaction"] = {
            "at": self._now(),
            "phase": event.get("phase", ""),
            "reason": event.get("reason", ""),
            "before_tokens": event.get("before_tokens", 0),
            "after_tokens": event.get("after_tokens", 0),
        }

    def snapshot(self, session_id=None):
        if session_id is not None:
            return self._public(self._get(session_id))
        return {key: self._public(value) for key, value in self._sessions.items()}

    @staticmethod
    def _public(state):
        result = dict(state)
        result["recent_tools"] = list(state["recent_tools"])
        return result


runtime_diagnostics = RuntimeDiagnostics()
