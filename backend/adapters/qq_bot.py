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
        self._connection_task = None
        self._message_tasks = set()
        self._running = False
        self._seq = None
        self._on_message = None  # 回调：收到消息时调用
        self._token_expires_at = 0  # token 过期时间戳

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
                token_data = resp.json()
                token = token_data.get("access_token", "")
                if not token:
                    return False

            # 2. 获取网关地址
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get("https://api.sgroup.qq.com/gateway/bot", headers={
                    "Authorization": f"QQBot {token}"
                })
                if resp.status_code != 200:
                    print(f"QQ Bot gateway error: {resp.status_code}")
                    return False
                gateway_url = resp.json().get("url", "wss://api.sgroup.qq.com/websocket")

            # 3. 连接 WebSocket
            await self._stop_connection()
            self.token = token
            self._token_expires_at = time.time() + int(token_data.get("expires_in", 7200)) - 300
            self._running = True
            self._connection_task = asyncio.create_task(self._connect(gateway_url))
            return True

        except Exception as e:
            print(f"QQ Bot connection error: {e}")
            return False

    async def stop(self):
        await self._stop_connection()
        self._running = False
        self.token = ""
        self._token_expires_at = 0
        current = asyncio.current_task()
        tasks = [task for task in self._message_tasks if task is not current]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._message_tasks.clear()

    async def _stop_connection(self):
        self._running = False
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
        if self.ws:
            await self.ws.close()

        current = asyncio.current_task()
        tasks = [
            task for task in (self._heartbeat_task, self._connection_task)
            if task and task is not current
        ]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        self._heartbeat_task = None
        self._connection_task = None
        self.ws = None

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

            except asyncio.CancelledError:
                raise
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
                                token_data = resp.json()
                                self.token = token_data.get("access_token", "")
                                self._token_expires_at = (
                                    time.time() + int(token_data.get("expires_in", 7200)) - 300
                                )
                    except Exception:
                        pass

    async def _handle_message(self, data):
        """处理 WebSocket 消息"""
        op = data.get("op")
        d = data.get("d")
        t = data.get("t")
        print(f"QQ WS收到: op={op} t={t} d_keys={list(d.keys()) if isinstance(d, dict) else type(d).__name__}")

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
                "intents": (1 << 0) | (1 << 12) | (1 << 25),  # GUILDS + PUBLIC_MESSAGES + DIRECT_MESSAGE
                "properties": {
                    "os": "windows",
                    "browser": "VerseNa",
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
                heartbeat = {"op": 1, "d": None}
                await self.ws.send(json.dumps(heartbeat))
                await asyncio.sleep(self.heartbeat_interval * 0.9)  # 提前 10% 发送
            except Exception:
                break

    async def _handle_event(self, event_type, data):
        """处理事件"""
        if not data:
            return

        print(f"QQ 事件: {event_type}")

        msg = None

        # 好友私信（群/好友机器人）
        if event_type == "C2C_MESSAGE_CREATE":
            author = data.get("author", {})
            user_openid = author.get("user_openid", author.get("id", ""))
            msg = AdapterMessage(
                platform="qq",
                user_id=user_openid,
                content=data.get("content", "").strip(),
                channel_id=user_openid,  # C2C 用 user_openid 作为 channel
                message_id=data.get("id", ""),
                msg_type="c2c"
            )

        # 群@消息（群/好友机器人）
        elif event_type == "GROUP_AT_MESSAGE_CREATE":
            author = data.get("author", {})
            group_openid = data.get("group_openid", data.get("id", ""))
            msg = AdapterMessage(
                platform="qq",
                user_id=author.get("member_openid", author.get("id", "")),
                content=data.get("content", "").strip(),
                channel_id=group_openid,  # 群用 group_openid
                message_id=data.get("id", ""),
                msg_type="group"
            )

        # 频道消息
        elif event_type == "MESSAGE_CREATE":
            msg = AdapterMessage(
                platform="qq",
                user_id=data.get("author", {}).get("id", ""),
                content=data.get("content", "").strip(),
                channel_id=data.get("channel_id", ""),
                message_id=data.get("id", ""),
                msg_type="channel"
            )

        # 频道私信
        elif event_type == "DIRECT_MESSAGE_CREATE":
            msg = AdapterMessage(
                platform="qq",
                user_id=data.get("author", {}).get("id", ""),
                content=data.get("content", "").strip(),
                channel_id=data.get("channel_id", ""),
                message_id=data.get("id", ""),
                msg_type="direct"
            )

        if msg and msg.content and self._on_message:
            print(f"QQ 收到消息: type={msg.msg_type}, user={msg.user_id}, content={msg.content[:50]}")
            task = asyncio.create_task(self._on_message(msg))
            self._message_tasks.add(task)
            task.add_done_callback(self._message_tasks.discard)

    def on_message(self, callback):
        """注册消息回调"""
        self._on_message = callback

    async def send(self, channel_id: str, content: str, msg_type: str = "channel"):
        """发送消息"""
        await self.ensure_token()
        if not self.token:
            print("[QQ] send失败: 无token", flush=True)
            return False
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                if msg_type == "c2c":
                    # C2C私信: channel_id = user_openid
                    url = f"https://api.sgroup.qq.com/v2/users/{channel_id}/messages"
                    payload = {"content": content, "msg_type": 0}
                elif msg_type == "group":
                    # 群@回复: channel_id = group_openid
                    url = f"https://api.sgroup.qq.com/v2/groups/{channel_id}/messages"
                    payload = {"content": content, "msg_type": 0}
                elif msg_type == "direct":
                    url = f"https://api.sgroup.qq.com/dms/{channel_id}/messages"
                    payload = {"content": content}
                else:
                    url = f"https://api.sgroup.qq.com/channels/{channel_id}/messages"
                    payload = {"content": content}

                resp = await client.post(url, json=payload, headers={
                    "Authorization": f"QQBot {self.token}"
                })
                print(f"[QQ] send {msg_type} -> {resp.status_code}: {resp.text[:200]}", flush=True)
                if resp.status_code == 401 or "token" in resp.text.lower():
                    print("[QQ] Token无效，刷新重试...", flush=True)
                    await self.start()
                    resp = await client.post(url, json=payload, headers={
                        "Authorization": f"QQBot {self.token}"
                    })
                    print(f"[QQ] 重试 -> {resp.status_code}: {resp.text[:200]}", flush=True)
                return resp.status_code in (200, 201)
        except Exception as e:
            print(f"[QQ] send异常: {e}", flush=True)
            return False

    async def ensure_token(self):
        if not self.token or time.time() > self._token_expires_at:
            print("[QQ] Token 过期或缺失，重新获取...", flush=True)
            await self.start()

    def is_configured(self) -> bool:
        return bool(self.app_id and self.app_secret)
