import asyncio
import json
import time
import httpx
import websockets
from .base import BaseAdapter, AdapterMessage


class QQBotAdapter(BaseAdapter):
    def __init__(self, app_id: str = "", app_secret: str = "", sandbox: bool = True):
        self.app_id = app_id
        self.app_secret = app_secret
        self.sandbox = sandbox
        self.token = ""
        self.ws = None
        self.heartbeat_interval = 41.25
        self._heartbeat_task = None
        self._running = False
        self._seq = None
        self._on_message = None  # 回调：收到消息时调用

    async def start(self):
        if not self.app_id or not self.app_secret:
            return False
        try:
            # 1. 获取 access_token
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post("https://bots.qq.com/app/getAppAccessToken", json={
                    "appId": self.app_id,
                    "clientSecret": self.app_secret,
                })
                if resp.status_code != 200:
                    print(f"QQ Bot token error: {resp.status_code}")
                    return False
                self.token = resp.json().get("access_token", "")
                if not self.token:
                    return False

            # 2. 获取网关地址
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get("https://api.sgroup.qq.com/gateway/bot", headers={
                    "Authorization": f"QQBot {self.token}"
                })
                if resp.status_code != 200:
                    print(f"QQ Bot gateway error: {resp.status_code}")
                    return False
                gateway_url = resp.json().get("url", "wss://api.sgroup.qq.com/websocket")

            # 3. 连接 WebSocket
            self._running = True
            asyncio.create_task(self._connect(gateway_url))
            return True

        except Exception as e:
            print(f"QQ Bot connection error: {e}")
            return False

    async def stop(self):
        self._running = False
        self.token = ""
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
        if self.ws:
            await self.ws.close()

    async def _connect(self, gateway_url):
        """连接 WebSocket 网关"""
        while self._running:
            try:
                async with websockets.connect(gateway_url) as ws:
                    self.ws = ws
                    print("QQ Bot WebSocket 已连接")

                    async for message in ws:
                        data = json.loads(message)
                        await self._handle_message(data)

            except Exception as e:
                print(f"QQ Bot WebSocket 断开: {e}")
                if self._running:
                    await asyncio.sleep(5)  # 重连
                    # 重新获取 token
                    try:
                        async with httpx.AsyncClient(timeout=10) as client:
                            resp = await client.post("https://bots.qq.com/app/getAppAccessToken", json={
                                "appId": self.app_id,
                                "clientSecret": self.app_secret,
                            })
                            if resp.status_code == 200:
                                self.token = resp.json().get("access_token", "")
                    except Exception:
                        pass

    async def _handle_message(self, data):
        """处理 WebSocket 消息"""
        op = data.get("op")
        d = data.get("d")

        if op == 10:  # Hello
            self.heartbeat_interval = d.get("heartbeat_interval", 41250) / 1000
            # 启动心跳
            if self._heartbeat_task:
                self._heartbeat_task.cancel()
            self._heartbeat_task = asyncio.create_task(self._heartbeat())

            # 发送 Identify
            await self._identify()

        elif op == 0:  # Dispatch
            self._seq = data.get("s")
            event_type = data.get("t", "")
            await self._handle_event(event_type, d)

        elif op == 11:  # Heartbeat ACK
            pass

        elif op == 9:  # Invalid Session
            print("QQ Bot: Invalid Session, 重新连接...")
            self._running = True

    async def _identify(self):
        """发送 Identify payload"""
        identify = {
            "op": 2,
            "d": {
                "token": f"QQBot {self.token}",
                "intents": (1 << 0) | (1 << 1) | (1 << 12) | (1 << 25),  # GUILDS + GUILD_MEMBERS + PUBLIC_MESSAGES + DIRECT_MESSAGE
                "properties": {
                    "os": "windows",
                    "browser": "次元人格",
                    "device": "ciyuan-persona"
                }
            }
        }
        await self.ws.send(json.dumps(identify))
        print("QQ Bot: Identify 已发送")

    async def _heartbeat(self):
        """定期发送心跳"""
        while self._running:
            try:
                heartbeat = {"op": 1, "d": self._seq}
                await self.ws.send(json.dumps(heartbeat))
                await asyncio.sleep(self.heartbeat_interval)
            except Exception:
                break

    async def _handle_event(self, event_type, data):
        """处理事件"""
        if not data:
            return

        # 频道消息
        if event_type == "MESSAGE_CREATE":
            msg = AdapterMessage(
                platform="qq",
                user_id=data.get("author", {}).get("id", ""),
                content=data.get("content", "").strip(),
                channel_id=data.get("channel_id", ""),
                message_id=data.get("id", ""),
                msg_type="channel"
            )
            if msg.content and self._on_message:
                await self._on_message(msg)

        # 私信
        elif event_type == "DIRECT_MESSAGE_CREATE":
            msg = AdapterMessage(
                platform="qq",
                user_id=data.get("author", {}).get("id", ""),
                content=data.get("content", "").strip(),
                channel_id=data.get("channel_id", ""),
                message_id=data.get("id", ""),
                msg_type="direct"
            )
            if msg.content and self._on_message:
                await self._on_message(msg)

    def on_message(self, callback):
        """注册消息回调"""
        self._on_message = callback

    async def send(self, channel_id: str, content: str, msg_type: str = "channel"):
        """发送消息"""
        if not self.token:
            return False
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                if msg_type == "direct":
                    # 私信
                    url = f"https://api.sgroup.qq.com/dms/{channel_id}/messages"
                else:
                    # 频道消息
                    url = f"https://api.sgroup.qq.com/channels/{channel_id}/messages"

                resp = await client.post(url, json={"content": content}, headers={
                    "Authorization": f"QQBot {self.token}"
                })
                return resp.status_code == 200
        except Exception as e:
            print(f"QQ Bot send error: {e}")
            return False

    async def ensure_token(self):
        if not self.token:
            await self.start()

    def is_configured(self) -> bool:
        return bool(self.app_id and self.app_secret)
