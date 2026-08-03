from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import AsyncGenerator

@dataclass
class ModelResponse:
    content: str = ""
    reasoning_content: str = ""
    tool_calls: list = field(default_factory=list)
    finish_reason: str = "stop"

class BaseModelAdapter(ABC):
    @abstractmethod
    async def chat(self, messages: list[dict], tools: list = None, stream: bool = True) -> AsyncGenerator[ModelResponse, None]:
        ...

    @abstractmethod
    async def list_models(self) -> list[str]:
        ...
