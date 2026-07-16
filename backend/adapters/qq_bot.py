import httpx
from .base import BaseAdapter, AdapterMessage

class QQBotAdapter(BaseAdapter):
    def __init__(self, app_id: str = "", app_secret: str = "", sandbox: bool = True):
        self.app_id = app_id
        self.app_secret = app_secret
        self.sandbox = sandbox
        self.base_url = "https://sandbox.api.sgroup.qq.com" if sandbox else "https://api.sgroup.qq.com"
        self.token = ""

    async def start(self):
        if not self.app_id or not self.app_secret:
            return False
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post("https://bots.qq.com/app/getAppAccessToken", json={
                    "appId": self.app_id,
                    "clientSecret": self.app_secret,
                })
                if resp.status_code == 200:
                    data = resp.json()
                    self.token = data.get("access_token", "")
                    return bool(self.token)
                else:
                    print(f"QQ Bot token error: {resp.status_code} {resp.text[:200]}")
        except Exception as e:
            print(f"QQ Bot connection error: {e}")
        return False

    async def stop(self):
        self.token = ""

    async def ensure_token(self):
        if not self.token:
            await self.start()

    async def send(self, channel_id: str, content: str):
        await self.ensure_token()
        if not self.token:
            return False
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    f"{self.base_url}/channels/{channel_id}/messages",
                    json={"content": content},
                    headers={"Authorization": f"QQBot {self.token}"}
                )
                return resp.status_code == 200
        except Exception:
            return False

    def parse_webhook(self, data: dict):
        # 处理 QQ 开放平台的 webhook 事件
        d = data.get("d", {})
        # 文字消息
        if d.get("content"):
            return AdapterMessage(
                platform="qq",
                user_id=d.get("author", {}).get("id", ""),
                content=d.get("content", ""),
                channel_id=d.get("channel_id", ""),
                message_id=d.get("id", ""),
            )
        # 私聊消息
        if d.get("msg_type") == 0 and d.get("content"):
            return AdapterMessage(
                platform="qq",
                user_id=d.get("author", {}).get("id", ""),
                content=d.get("content", ""),
                channel_id=d.get("channel_id", ""),
                message_id=d.get("id", ""),
            )
        return None

    def is_configured(self) -> bool:
        return bool(self.app_id and self.app_secret)
