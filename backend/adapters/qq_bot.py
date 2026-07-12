import httpx
from .base import BaseAdapter, AdapterMessage

class QQBotAdapter(BaseAdapter):
    def __init__(self, app_id: str = "", app_secret: str = "", sandbox: bool = True):
        self.app_id = app_id
        self.app_secret = app_secret
        self.base_url = "https://sandbox.api.sgroup.qq.com" if sandbox else "https://api.sgroup.qq.com"
        self.token = ""

    async def start(self):
        async with httpx.AsyncClient() as client:
            resp = await client.post(f"{self.base_url}/oauth2/token", data={
                "grant_type": "client_credentials",
                "client_id": self.app_id,
                "client_secret": self.app_secret,
            })
            self.token = resp.json().get("access_token", "")

    async def stop(self):
        self.token = ""

    async def send(self, channel_id: str, content: str):
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{self.base_url}/channels/{channel_id}/messages",
                json={"content": content},
                headers={"Authorization": f"Bot {self.app_id}.{self.token}"}
            )

    def parse_webhook(self, data: dict):
        if data.get("d", {}).get("content"):
            d = data["d"]
            return AdapterMessage(
                platform="qq",
                user_id=d.get("author", {}).get("id", ""),
                content=d.get("content", ""),
                channel_id=d.get("channel_id", ""),
                message_id=d.get("id", ""),
            )
        return None
