from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class AdapterMessage:
    platform: str
    user_id: str
    content: str
    channel_id: str = ""
    message_id: str = ""
    attachments: list = None

class BaseAdapter(ABC):
    @abstractmethod
    async def start(self): ...
    @abstractmethod
    async def stop(self): ...
    @abstractmethod
    async def send(self, channel_id: str, content: str): ...
