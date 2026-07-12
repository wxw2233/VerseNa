from abc import ABC, abstractmethod

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
