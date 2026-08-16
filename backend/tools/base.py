from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from typing import Any


@dataclass
class ToolContext:
    session_id: str
    workspace: Path
    trust_mode_getter: Callable[[], bool] | None = None
    stop_event: Any = None
    approval_mode: str = "ask"
    model: Any = None
    progress_callback: Callable[[dict], Any] | None = None
    agent_config: dict[str, Any] | None = None
    confirm_callback: Callable[[dict], Any] | None = None

    @property
    def trust_mode(self) -> bool:
        return self.approval_mode == "auto" or bool(
            self.trust_mode_getter and self.trust_mode_getter()
        )

    @property
    def host_execution_enabled(self) -> bool:
        return bool((self.agent_config or {}).get("host_execution_enabled", False))

class BaseTool(ABC):
    name: str = ""
    description: str = ""
    parameters: dict = {}

    @abstractmethod
    async def execute(self, **kwargs) -> str:
        ...

    def to_openai_tool(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            }
        }
