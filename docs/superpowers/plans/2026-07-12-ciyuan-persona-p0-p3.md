# 次元人格 P0-P3 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 搭建次元人格 Agent 平台的基础骨架 — 后端服务、Agent 引擎、前端界面、Persona 人格系统，实现一个能在网页端聊天的、支持角色切换的 AI Agent。

**Architecture:** FastAPI 后端通过 WebSocket 与 Vue 3 前端通信。Agent 引擎基于 ReAct 循环，调用统一模型适配层。Persona 系统管理角色人设、情感权重和专属记忆。SQLite 存储会话和配置。

**Tech Stack:** Python 3.11, FastAPI, uvicorn, SQLite (aiosqlite), Vue 3, Vite, Pinia, WebSocket

## Global Constraints

- Python 3.11+, pip install 不要全局，用 venv
- 前端 Node.js 18+, pnpm
- 所有项目文件放在 `E:\Agent_design\`
- 后端默认端口 8000，前端开发端口 5173
- SQLite 数据库文件: `backend/data/ciyuan.db`
- 测试用 pytest + pytest-asyncio
- 每个 task 结束后 git commit

---

## File Structure

```
E:\Agent_design\
├── backend/
│   ├── main.py                    # FastAPI 入口 + 路由注册
│   ├── config.py                  # 全局配置（端口、数据库路径、模型配置）
│   ├── requirements.txt           # Python 依赖
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── engine.py              # Agent 引擎（对话管理 + ReAct）
│   │   ├── react.py               # ReAct 循环实现
│   │   ├── memory.py              # 上下文记忆管理
│   │   └── models/
│   │       ├── __init__.py
│   │       ├── base.py            # 统一模型接口 BaseModelAdapter
│   │       └── openai_adapter.py  # OpenAI 兼容适配器
│   ├── persona/
│   │   ├── __init__.py
│   │   ├── manager.py             # Persona CRUD + 加载
│   │   ├── loader.py              # prompt.md 加载 + 情感权重注入
│   │   └── emotion.py             # 情感权重引擎
│   ├── db/
│   │   ├── __init__.py
│   │   └── database.py            # SQLite 初始化 + 操作封装
│   ├── api/
│   │   ├── __init__.py
│   │   ├── chat.py                # WebSocket 聊天路由
│   │   ├── persona_api.py         # Persona REST API
│   │   └── config_api.py          # 配置 REST API
│   └── tests/
│       ├── __init__.py
│       ├── test_engine.py
│       ├── test_react.py
│       ├── test_persona.py
│       └── test_api.py
├── frontend/
│   ├── package.json
│   ├── vite.config.js
│   ├── index.html
│   └── src/
│       ├── main.js
│       ├── App.vue
│       ├── router.js
│       ├── stores/
│       │   ├── chat.js             # Pinia 聊天状态
│       │   └── persona.js          # Pinia 角色状态
│       ├── views/
│       │   ├── ChatView.vue        # 主聊天界面
│       │   └── SettingsView.vue    # 设置页（模型配置、主题切换）
│       ├── components/
│       │   ├── ChatBubble.vue      # 聊天气泡组件
│       │   ├── ChatInput.vue       # 输入框组件
│       │   ├── PersonaSwitcher.vue # 角色切换器
│       │   └── ThinkingProcess.vue # ReAct 思考过程折叠展示
│       ├── composables/
│       │   └── useWebSocket.js     # WebSocket 连接管理
│       └── styles/
│           └── default.css         # 默认主题 CSS 变量
├── personas/
│   └── default/
│       ├── persona.json
│       └── prompt.md
└── docs/
    └── superpowers/
        ├── specs/
        │   └── 2026-07-12-ciyuan-persona-design.md
        └── plans/
            └── 2026-07-12-ciyuan-persona-p0-p3.md
```

---

## P0: 项目脚手架

### Task 1: 初始化项目结构 + 后端基础

**Files:**
- Create: `backend/config.py`
- Create: `backend/requirements.txt`
- Create: `backend/main.py`
- Create: `backend/db/__init__.py`
- Create: `backend/db/database.py`
- Create: `backend/tests/__init__.py`

**Interfaces:**
- Produces: `config.Settings` (全局配置单例), `db.database.Database` (SQLite 操作)

- [ ] **Step 1: 创建 config.py**

```python
# backend/config.py
import os
from pathlib import Path

class Settings:
    PROJECT_NAME = "次元人格"
    VERSION = "0.1.0"
    HOST = "0.0.0.0"
    PORT = 8000
    DEBUG = True

    # 数据库
    BASE_DIR = Path(__file__).parent
    DATA_DIR = BASE_DIR / "data"
    DB_PATH = DATA_DIR / "ciyuan.db"

    # 模型默认配置
    DEFAULT_MODEL = "deepseek"
    DEFAULT_API_KEY = ""
    DEFAULT_API_BASE = "https://api.deepseek.com/v1"
    DEFAULT_MODEL_NAME = "deepseek-chat"

    # Agent
    MAX_REACT_LOOPS = 5
    MAX_CONTEXT_TOKENS = 4096

    @classmethod
    def ensure_dirs(cls):
        cls.DATA_DIR.mkdir(parents=True, exist_ok=True)

settings = Settings()
```

- [ ] **Step 2: 创建 requirements.txt**

```
fastapi==0.115.0
uvicorn[standard]==0.30.0
aiosqlite==0.20.0
websockets==12.0
httpx==0.27.0
pydantic==2.9.0
python-dotenv==1.0.1
pytest==8.3.0
pytest-asyncio==0.24.0
```

- [ ] **Step 3: 创建 db/database.py**

```python
# backend/db/database.py
import aiosqlite
from config import settings

class Database:
    def __init__(self, db_path=None):
        self.db_path = db_path or settings.DB_PATH
        self._db = None

    async def connect(self):
        settings.ensure_dirs()
        self._db = await aiosqlite.connect(str(self.db_path))
        self._db.row_factory = aiosqlite.Row
        await self._init_tables()

    async def close(self):
        if self._db:
            await self._db.close()

    async def _init_tables(self):
        await self._db.executescript("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                persona TEXT DEFAULT 'default',
                metadata TEXT DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_session ON conversations(session_id);

            CREATE TABLE IF NOT EXISTS app_config (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
        """)
        await self._db.commit()

    async def save_message(self, session_id: str, role: str, content: str, persona: str = "default", metadata: str = "{}"):
        await self._db.execute(
            "INSERT INTO conversations (session_id, role, content, persona, metadata) VALUES (?, ?, ?, ?, ?)",
            (session_id, role, content, persona, metadata)
        )
        await self._db.commit()

    async def get_history(self, session_id: str, limit: int = 50):
        cursor = await self._db.execute(
            "SELECT role, content, persona, metadata, created_at FROM conversations WHERE session_id = ? ORDER BY id DESC LIMIT ?",
            (session_id, limit)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in reversed(rows)]

    async def get_config(self, key: str, default: str = ""):
        cursor = await self._db.execute("SELECT value FROM app_config WHERE key = ?", (key,))
        row = await cursor.fetchone()
        return row["value"] if row else default

    async def set_config(self, key: str, value: str):
        await self._db.execute(
            "INSERT OR REPLACE INTO app_config (key, value) VALUES (?, ?)", (key, value)
        )
        await self._db.commit()

db = Database()
```

- [ ] **Step 4: 创建 main.py**

```python
# backend/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config import settings
from db.database import db

@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.connect()
    yield
    await db.close()

app = FastAPI(title=settings.PROJECT_NAME, version=settings.VERSION, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health():
    return {"status": "ok", "version": settings.VERSION}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG)
```

- [ ] **Step 5: 验证启动**

Run: `cd backend && pip install -r requirements.txt && python main.py`
Expected: `Uvicorn running on http://0.0.0.0:8000`，访问 `http://localhost:8000/health` 返回 `{"status":"ok","version":"0.1.0"}`

- [ ] **Step 6: Commit**

```bash
git init
echo -e "backend/data/\nbackend/__pycache__/\n*.pyc\nnode_modules/\n.vite/" > .gitignore
git add .
git commit -m "feat(P0): project scaffolding with FastAPI + SQLite"
```

---

## P1: Agent 引擎

### Task 2: 模型适配层

**Files:**
- Create: `backend/agent/__init__.py`
- Create: `backend/agent/models/__init__.py`
- Create: `backend/agent/models/base.py`
- Create: `backend/agent/models/openai_adapter.py`
- Create: `backend/tests/test_models.py`

**Interfaces:**
- Consumes: `config.settings` (API 配置)
- Produces: `BaseModelAdapter.chat()` → async generator of chunks, `BaseModelAdapter.list_models()` → list[str]

- [ ] **Step 1: 创建 base.py**

```python
# backend/agent/models/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import AsyncGenerator

@dataclass
class ModelResponse:
    content: str
    tool_calls: list = None
    finish_reason: str = "stop"

class BaseModelAdapter(ABC):
    @abstractmethod
    async def chat(self, messages: list[dict], tools: list = None, stream: bool = True) -> AsyncGenerator[ModelResponse, None]:
        ...

    @abstractmethod
    async def list_models(self) -> list[str]:
        ...
```

- [ ] **Step 2: 创建 openai_adapter.py**

```python
# backend/agent/models/openai_adapter.py
import json
import httpx
from typing import AsyncGenerator
from .base import BaseModelAdapter, ModelResponse

class OpenAIAdapter(BaseModelAdapter):
    def __init__(self, api_key: str, base_url: str, model_name: str):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model_name = model_name

    async def chat(self, messages: list[dict], tools: list = None, stream: bool = True) -> AsyncGenerator[ModelResponse, None]:
        payload = {
            "model": self.model_name,
            "messages": messages,
            "stream": stream,
        }
        if tools:
            payload["tools"] = tools

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=120) as client:
            if stream:
                async with client.stream("POST", f"{self.base_url}/chat/completions", json=payload, headers=headers) as resp:
                    async for line in resp.aiter_lines():
                        if line.startswith("data: ") and line.strip() != "data: [DONE]":
                            chunk = json.loads(line[6:])
                            delta = chunk["choices"][0].get("delta", {})
                            content = delta.get("content", "")
                            tool_calls = delta.get("tool_calls")
                            yield ModelResponse(content=content, tool_calls=tool_calls)
            else:
                resp = await client.post(f"{self.base_url}/chat/completions", json=payload, headers=headers)
                data = resp.json()
                choice = data["choices"][0]
                yield ModelResponse(
                    content=choice["message"].get("content", ""),
                    tool_calls=choice["message"].get("tool_calls"),
                    finish_reason=choice.get("finish_reason", "stop")
                )

    async def list_models(self) -> list[str]:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{self.base_url}/models", headers={"Authorization": f"Bearer {self.api_key}"})
            data = resp.json()
            return [m["id"] for m in data.get("data", [])]
```

- [ ] **Step 3: 测试模型适配器（mock）**

```python
# backend/tests/test_models.py
import pytest
from agent.models.base import BaseModelAdapter, ModelResponse

def test_model_response_dataclass():
    r = ModelResponse(content="hello")
    assert r.content == "hello"
    assert r.tool_calls is None
    assert r.finish_reason == "stop"

def test_openai_adapter_init():
    from agent.models.openai_adapter import OpenAIAdapter
    adapter = OpenAIAdapter(api_key="test", base_url="https://api.openai.com/v1", model_name="gpt-4")
    assert adapter.model_name == "gpt-4"
    assert adapter.base_url == "https://api.openai.com/v1"
```

- [ ] **Step 4: 运行测试**

Run: `cd backend && python -m pytest tests/test_models.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/agent/models/ backend/tests/test_models.py
git commit -m "feat(P1): add model adapter layer with OpenAI-compatible support"
```

### Task 3: 上下文记忆管理

**Files:**
- Create: `backend/agent/memory.py`
- Create: `backend/tests/test_memory.py`

**Interfaces:**
- Consumes: `db.database.db`
- Produces: `MemoryManager.get_context(session_id)` → list[dict], `MemoryManager.add_message(session_id, role, content)` → None

- [ ] **Step 1: 创建 memory.py**

```python
# backend/agent/memory.py
from db.database import db
from config import settings

class MemoryManager:
    def __init__(self, max_tokens: int = None):
        self.max_tokens = max_tokens or settings.MAX_CONTEXT_TOKENS

    def _estimate_tokens(self, messages: list[dict]) -> int:
        total = 0
        for msg in messages:
            total += len(msg.get("content", "")) // 2  # 粗略估计: 2字符 ≈ 1token
        return total

    async def get_context(self, session_id: str, system_prompt: str = "") -> list[dict]:
        history = await db.get_history(session_id, limit=100)
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        for msg in history:
            messages.append({"role": msg["role"], "content": msg["content"]})

        while self._estimate_tokens(messages) > self.max_tokens and len(messages) > 2:
            if messages[0]["role"] == "system":
                messages.pop(1)
            else:
                messages.pop(0)

        return messages

    async def add_message(self, session_id: str, role: str, content: str, persona: str = "default"):
        await db.save_message(session_id, role, content, persona)
```

- [ ] **Step 2: 测试记忆管理**

```python
# backend/tests/test_memory.py
import pytest
from agent.memory import MemoryManager

def test_estimate_tokens():
    mm = MemoryManager()
    messages = [{"role": "user", "content": "你好啊"}]
    tokens = mm._estimate_tokens(messages)
    assert tokens > 0
    assert tokens < 10

def test_estimate_tokens_empty():
    mm = MemoryManager()
    assert mm._estimate_tokens([]) == 0
```

- [ ] **Step 3: 运行测试**

Run: `cd backend && python -m pytest tests/test_memory.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add backend/agent/memory.py backend/tests/test_memory.py
git commit -m "feat(P1): add context memory manager with token-based truncation"
```

### Task 4: ReAct 循环

**Files:**
- Create: `backend/agent/react.py`
- Create: `backend/tests/test_react.py`

**Interfaces:**
- Consumes: `BaseModelAdapter.chat()`, `MemoryManager.get_context()`
- Produces: `ReActAgent.run(session_id, user_message, system_prompt, tools)` → async generator of {"type": "thinking"|"answer"|"tool_call", "content": str}

- [ ] **Step 1: 创建 react.py**

```python
# backend/agent/react.py
import json
from typing import AsyncGenerator
from agent.models.base import BaseModelAdapter
from agent.memory import MemoryManager
from config import settings

class ReActAgent:
    def __init__(self, model: BaseModelAdapter, memory: MemoryManager):
        self.model = model
        self.memory = memory

    async def run(self, session_id: str, user_message: str, system_prompt: str = "", tools: list = None) -> AsyncGenerator[dict, None]:
        await self.memory.add_message(session_id, "user", user_message)
        messages = await self.memory.get_context(session_id, system_prompt)

        full_response = ""
        loops = 0

        while loops < settings.MAX_REACT_LOOPS:
            loops += 1
            chunk_content = ""
            tool_calls = []

            async for chunk in self.model.chat(messages, tools=tools, stream=True):
                if chunk.content:
                    chunk_content += chunk.content
                    yield {"type": "answer", "content": chunk.content}
                if chunk.tool_calls:
                    tool_calls.extend(chunk.tool_calls)

            full_response += chunk_content

            if not tool_calls:
                break

            messages.append({"role": "assistant", "content": chunk_content, "tool_calls": tool_calls})
            for tc in tool_calls:
                yield {"type": "tool_call", "content": json.dumps(tc, ensure_ascii=False)}

            yield {"type": "thinking", "content": "需要调用工具，但工具系统尚未实现，停止循环。"}
            break

        await self.memory.add_message(session_id, "assistant", full_response)
```

- [ ] **Step 2: 测试 ReAct 基础逻辑**

```python
# backend/tests/test_react.py
import pytest
from agent.react import ReActAgent
from agent.models.base import BaseModelAdapter, ModelResponse
from agent.memory import MemoryManager
from typing import AsyncGenerator

class MockAdapter(BaseModelAdapter):
    def __init__(self, responses):
        self.responses = responses
        self.call_count = 0

    async def chat(self, messages, tools=None, stream=True) -> AsyncGenerator:
        resp = self.responses[self.call_count]
        self.call_count += 1
        yield ModelResponse(content=resp)

    async def list_models(self):
        return ["mock-model"]

@pytest.mark.asyncio
async def test_react_simple_response():
    adapter = MockAdapter(["你好！我是次元人格。"])
    memory = MemoryManager()
    agent = ReActAgent(adapter, memory)

    results = []
    async for event in agent.run("test-session", "你好"):
        results.append(event)

    answers = [r for r in results if r["type"] == "answer"]
    assert len(answers) > 0
    assert "你好" in "".join(r["content"] for r in answers)
```

- [ ] **Step 3: 运行测试**

Run: `cd backend && python -m pytest tests/test_react.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add backend/agent/react.py backend/tests/test_react.py
git commit -m "feat(P1): add ReAct loop with streaming and tool call support"
```

### Task 5: WebSocket 聊天路由 + API 注册

**Files:**
- Create: `backend/api/__init__.py`
- Create: `backend/api/chat.py`
- Create: `backend/api/config_api.py`
- Modify: `backend/main.py` (注册路由)
- Create: `backend/tests/test_api.py`

**Interfaces:**
- Consumes: `ReActAgent`, `OpenAIAdapter`, `MemoryManager`, `db.database.db`
- Produces: WebSocket endpoint `/ws/chat`, REST endpoints `/api/config/*`

- [ ] **Step 1: 创建 api/chat.py**

```python
# backend/api/chat.py
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from agent.react import ReActAgent
from agent.models.openai_adapter import OpenAIAdapter
from agent.memory import MemoryManager
from config import settings

router = APIRouter()

def create_agent(api_key: str = None, base_url: str = None, model_name: str = None) -> ReActAgent:
    key = api_key or settings.DEFAULT_API_KEY
    url = base_url or settings.DEFAULT_API_BASE
    model = model_name or settings.DEFAULT_MODEL_NAME
    adapter = OpenAIAdapter(api_key=key, base_url=url, model_name=model)
    memory = MemoryManager()
    return ReActAgent(model=adapter, memory=memory)

@router.websocket("/ws/chat")
async def websocket_chat(ws: WebSocket):
    await ws.accept()
    agent = create_agent()

    try:
        while True:
            data = await ws.receive_text()
            msg = json.loads(data)

            session_id = msg.get("session_id", "default")
            content = msg.get("content", "")
            persona = msg.get("persona", "default")
            system_prompt = msg.get("system_prompt", "")

            async for event in agent.run(session_id, content, system_prompt=system_prompt):
                await ws.send_text(json.dumps(event, ensure_ascii=False))

            await ws.send_text(json.dumps({"type": "done"}))

    except WebSocketDisconnect:
        pass
    except Exception as e:
        await ws.send_text(json.dumps({"type": "error", "content": str(e)}))
```

- [ ] **Step 2: 创建 api/config_api.py**

```python
# backend/api/config_api.py
from fastapi import APIRouter
from pydantic import BaseModel
from config import settings

router = APIRouter()

class ModelConfig(BaseModel):
    api_key: str
    base_url: str
    model_name: str

@router.get("/api/config/model")
async def get_model_config():
    return {
        "base_url": settings.DEFAULT_API_BASE,
        "model_name": settings.DEFAULT_MODEL_NAME,
    }

@router.post("/api/config/model")
async def set_model_config(config: ModelConfig):
    settings.DEFAULT_API_KEY = config.api_key
    settings.DEFAULT_API_BASE = config.base_url
    settings.DEFAULT_MODEL_NAME = config.model_name
    return {"status": "ok"}
```

- [ ] **Step 3: 修改 main.py 注册路由**

```python
# backend/main.py — 在 health 路由后追加
from api.chat import router as chat_router
from api.config_api import router as config_router

app.include_router(chat_router)
app.include_router(config_router)
```

- [ ] **Step 4: 测试 API**

```python
# backend/tests/test_api.py
import pytest
from fastapi.testclient import TestClient
from main import app

def test_health():
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"

def test_get_model_config():
    client = TestClient(app)
    resp = client.get("/api/config/model")
    assert resp.status_code == 200
    assert "model_name" in resp.json()
```

- [ ] **Step 5: 运行全部测试**

Run: `cd backend && python -m pytest tests/ -v`
Expected: 全部 PASS

- [ ] **Step 6: Commit**

```bash
git add backend/api/ backend/main.py backend/tests/test_api.py
git commit -m "feat(P1): add WebSocket chat API and config API"
```

---

## P2: Vue 3 前端

### Task 6: 前端脚手架 + 聊天界面

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.js`
- Create: `frontend/index.html`
- Create: `frontend/src/main.js`
- Create: `frontend/src/App.vue`
- Create: `frontend/src/router.js`
- Create: `frontend/src/views/ChatView.vue`
- Create: `frontend/src/views/SettingsView.vue`
- Create: `frontend/src/components/ChatBubble.vue`
- Create: `frontend/src/components/ChatInput.vue`
- Create: `frontend/src/composables/useWebSocket.js`
- Create: `frontend/src/stores/chat.js`
- Create: `frontend/src/styles/default.css`

**Interfaces:**
- Consumes: WebSocket `ws://localhost:8000/ws/chat`, REST `/api/config/model`
- Produces: 可交互的聊天界面，支持流式输出

- [ ] **Step 1: 初始化前端项目**

Run:
```bash
cd /e/Agent_design
mkdir -p frontend/src/{views,components,composables,stores,styles}
```

- [ ] **Step 2: 创建 package.json**

```json
{
  "name": "ciyuan-persona-frontend",
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "vue": "^3.4.0",
    "vue-router": "^4.4.0",
    "pinia": "^2.2.0"
  },
  "devDependencies": {
    "@vitejs/plugin-vue": "^5.1.0",
    "vite": "^5.4.0"
  }
}
```

- [ ] **Step 3: 创建 vite.config.js**

```javascript
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/ws': { target: 'ws://localhost:8000', ws: true },
      '/api': { target: 'http://localhost:8000' },
    }
  }
})
```

- [ ] **Step 4: 创建 index.html**

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>次元人格</title>
</head>
<body>
  <div id="app"></div>
  <script type="module" src="/src/main.js"></script>
</body>
</html>
```

- [ ] **Step 5: 创建 main.js**

```javascript
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'
import ChatView from './views/ChatView.vue'
import SettingsView from './views/SettingsView.vue'
import './styles/default.css'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: ChatView },
    { path: '/settings', component: SettingsView },
  ]
})

createApp(App).use(createPinia()).use(router).mount('#app')
```

- [ ] **Step 6: 创建 App.vue**

```vue
<template>
  <div id="app-root">
    <nav class="top-bar">
      <router-link to="/" class="nav-title">次元人格</router-link>
      <router-link to="/settings" class="nav-link">设置</router-link>
    </nav>
    <main class="main-content">
      <router-view />
    </main>
  </div>
</template>

<style scoped>
.top-bar {
  display: flex;
  align-items: center;
  padding: 12px 20px;
  background: var(--bg-secondary);
  border-bottom: 1px solid var(--border);
}
.nav-title {
  font-size: 18px;
  font-weight: bold;
  color: var(--primary);
  text-decoration: none;
  margin-right: auto;
}
.nav-link {
  color: var(--text-secondary);
  text-decoration: none;
  font-size: 14px;
}
.nav-link:hover {
  color: var(--primary);
}
.main-content {
  flex: 1;
  overflow: hidden;
}
</style>
```

- [ ] **Step 7: 创建 useWebSocket.js**

```javascript
// frontend/src/composables/useWebSocket.js
import { ref, onUnmounted } from 'vue'

export function useWebSocket(url = `ws://${location.host}/ws/chat`) {
  const ws = ref(null)
  const connected = ref(false)
  const onMessage = ref(null)

  function connect() {
    ws.value = new WebSocket(url)
    ws.value.onopen = () => { connected.value = true }
    ws.value.onclose = () => { connected.value = false }
    ws.value.onmessage = (e) => {
      if (onMessage.value) onMessage.value(JSON.parse(e.data))
    }
  }

  function send(data) {
    if (ws.value && connected.value) {
      ws.value.send(JSON.stringify(data))
    }
  }

  function disconnect() {
    if (ws.value) ws.value.close()
  }

  onUnmounted(disconnect)

  return { ws, connected, connect, send, disconnect, onMessage }
}
```

- [ ] **Step 8: 创建 chat.js (Pinia store)**

```javascript
// frontend/src/stores/chat.js
import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useChatStore = defineStore('chat', () => {
  const messages = ref([])
  const isStreaming = ref(false)
  const currentPersona = ref('default')

  function addUserMessage(content) {
    messages.value.push({ role: 'user', content, persona: currentPersona.value })
  }

  function appendAgentChunk(content) {
    const last = messages.value[messages.value.length - 1]
    if (last && last.role === 'assistant' && last.streaming) {
      last.content += content
    } else {
      messages.value.push({ role: 'assistant', content, streaming: true, persona: currentPersona.value })
    }
  }

  function finishStreaming() {
    const last = messages.value[messages.value.length - 1]
    if (last) last.streaming = false
    isStreaming.value = false
  }

  function clearMessages() {
    messages.value = []
  }

  return { messages, isStreaming, currentPersona, addUserMessage, appendAgentChunk, finishStreaming, clearMessages }
})
```

- [ ] **Step 9: 创建 ChatBubble.vue**

```vue
<template>
  <div class="bubble" :class="[msg.role, { streaming: msg.streaming }]">
    <div class="bubble-content">{{ msg.content }}</div>
  </div>
</template>

<script setup>
defineProps({ msg: Object })
</script>

<style scoped>
.bubble {
  max-width: 75%;
  padding: 10px 14px;
  border-radius: 12px;
  margin: 6px 0;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
}
.user {
  background: var(--bubble-user);
  margin-left: auto;
  border-bottom-right-radius: 4px;
}
.assistant {
  background: var(--bubble-agent);
  margin-right: auto;
  border-bottom-left-radius: 4px;
}
.streaming::after {
  content: '▊';
  animation: blink 0.8s infinite;
}
@keyframes blink {
  50% { opacity: 0; }
}
</style>
```

- [ ] **Step 10: 创建 ChatInput.vue**

```vue
<template>
  <div class="input-bar">
    <textarea
      v-model="text"
      @keydown.enter.exact.prevent="send"
      placeholder="输入消息... (Enter 发送)"
      rows="1"
      ref="textareaRef"
    ></textarea>
    <button @click="send" :disabled="!text.trim()">发送</button>
  </div>
</template>

<script setup>
import { ref } from 'vue'
const emit = defineEmits(['send'])
const text = ref('')
const textareaRef = ref(null)

function send() {
  if (text.value.trim()) {
    emit('send', text.value.trim())
    text.value = ''
  }
}
</script>

<style scoped>
.input-bar {
  display: flex;
  gap: 8px;
  padding: 12px 16px;
  background: var(--bg-secondary);
  border-top: 1px solid var(--border);
}
textarea {
  flex: 1;
  resize: none;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 8px 12px;
  background: var(--bg-primary);
  color: var(--text-primary);
  font-size: 14px;
  outline: none;
  max-height: 120px;
}
textarea:focus {
  border-color: var(--primary);
}
button {
  padding: 8px 20px;
  background: var(--primary);
  color: white;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  font-size: 14px;
}
button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
```

- [ ] **Step 11: 创建 ChatView.vue**

```vue
<template>
  <div class="chat-view">
    <div class="messages" ref="messagesRef">
      <ChatBubble v-for="(msg, i) in store.messages" :key="i" :msg="msg" />
      <div v-if="store.messages.length === 0" class="empty">
        <p>✨ 次元人格 ✨</p>
        <p class="sub">选择一个角色开始聊天</p>
      </div>
    </div>
    <ChatInput @send="handleSend" />
  </div>
</template>

<script setup>
import { ref, nextTick, onMounted } from 'vue'
import { useChatStore } from '../stores/chat'
import { useWebSocket } from '../composables/useWebSocket'
import ChatBubble from '../components/ChatBubble.vue'
import ChatInput from '../components/ChatInput.vue'

const store = useChatStore()
const messagesRef = ref(null)
const { connect, send, onMessage } = useWebSocket()

onMounted(() => {
  connect()
  onMessage.value = (msg) => {
    if (msg.type === 'answer') {
      store.appendAgentChunk(msg.content)
    } else if (msg.type === 'done') {
      store.finishStreaming()
    } else if (msg.type === 'error') {
      store.appendAgentChunk(`\n[错误] ${msg.content}`)
      store.finishStreaming()
    }
    nextTick(() => {
      if (messagesRef.value) messagesRef.value.scrollTop = messagesRef.value.scrollHeight
    })
  }
})

function handleSend(content) {
  store.addUserMessage(content)
  store.isStreaming = true
  send({
    session_id: 'default',
    content,
    persona: store.currentPersona,
    system_prompt: ''
  })
}
</script>

<style scoped>
.chat-view {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 52px);
}
.messages {
  flex: 1;
  overflow-y: auto;
  padding: 16px 20px;
  display: flex;
  flex-direction: column;
}
.empty {
  margin: auto;
  text-align: center;
  color: var(--text-secondary);
}
.empty p { font-size: 24px; }
.empty .sub { font-size: 14px; margin-top: 8px; }
</style>
```

- [ ] **Step 12: 创建 SettingsView.vue**

```vue
<template>
  <div class="settings">
    <h2>模型配置</h2>
    <div class="form-group">
      <label>API Base URL</label>
      <input v-model="form.base_url" placeholder="https://api.deepseek.com/v1" />
    </div>
    <div class="form-group">
      <label>API Key</label>
      <input v-model="form.api_key" type="password" placeholder="sk-..." />
    </div>
    <div class="form-group">
      <label>模型名称</label>
      <input v-model="form.model_name" placeholder="deepseek-chat" />
    </div>
    <button @click="save">保存</button>
  </div>
</template>

<script setup>
import { reactive, onMounted } from 'vue'

const form = reactive({ api_key: '', base_url: '', model_name: '' })

onMounted(async () => {
  const resp = await fetch('/api/config/model')
  const data = await resp.json()
  form.base_url = data.base_url || ''
  form.model_name = data.model_name || ''
})

async function save() {
  await fetch('/api/config/model', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(form)
  })
  alert('保存成功')
}
</script>

<style scoped>
.settings {
  max-width: 500px;
  margin: 40px auto;
  padding: 20px;
}
.form-group {
  margin-bottom: 16px;
}
label {
  display: block;
  font-size: 14px;
  color: var(--text-secondary);
  margin-bottom: 4px;
}
input {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--bg-primary);
  color: var(--text-primary);
  font-size: 14px;
  outline: none;
}
button {
  padding: 10px 24px;
  background: var(--primary);
  color: white;
  border: none;
  border-radius: 8px;
  cursor: pointer;
}
</style>
```

- [ ] **Step 13: 创建 default.css**

```css
/* frontend/src/styles/default.css */
:root {
  --primary: #7c5cfc;
  --bg-primary: #0f0f1a;
  --bg-secondary: #1a1a2e;
  --text-primary: #e8e8f0;
  --text-secondary: #8888aa;
  --border: #2a2a40;
  --bubble-user: rgba(124, 92, 252, 0.15);
  --bubble-agent: rgba(30, 30, 50, 0.9);
}

* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: 'Noto Sans SC', -apple-system, BlinkMacSystemFont, sans-serif;
  background: var(--bg-primary);
  color: var(--text-primary);
  height: 100vh;
}

#app {
  height: 100vh;
  display: flex;
  flex-direction: column;
}

a { color: var(--primary); }
```

- [ ] **Step 14: 安装依赖并验证前端启动**

Run:
```bash
cd /e/Agent_design/frontend
pnpm install
pnpm dev
```
Expected: `Local: http://localhost:5173/` 能看到"次元人格"界面

- [ ] **Step 15: Commit**

```bash
cd /e/Agent_design
git add frontend/
git commit -m "feat(P2): Vue 3 frontend with chat interface, streaming output, default theme"
```

---

## P3: Persona 人格系统

### Task 7: Persona 管理器

**Files:**
- Create: `backend/persona/__init__.py`
- Create: `backend/persona/manager.py`
- Create: `backend/persona/loader.py`
- Create: `backend/persona/emotion.py`
- Create: `backend/tests/test_persona.py`
- Create: `personas/default/persona.json`
- Create: `personas/default/prompt.md`

**Interfaces:**
- Consumes: 文件系统 `personas/*/persona.json` + `personas/*/prompt.md`
- Produces: `PersonaManager.get_persona(name)` → PersonaData, `PersonaManager.list_personas()` → list[dict], `PersonaLoader.build_system_prompt(persona)` → str

- [ ] **Step 1: 创建默认 persona**

```json
// personas/default/persona.json
{
  "name": "默认助手",
  "version": "1.0.0",
  "description": "一个友好的通用AI助手",
  "emotion_weights": {
    "cheerful": 0.5,
    "shy": 0.2,
    "curious": 0.6,
    "angry": 0.05,
    "sad": 0.05
  },
  "speech_style": {
    "tone": "友好温和",
    "catchphrase": "",
    "emoji_frequency": "medium",
    "formality": "casual"
  },
  "memory_config": {
    "max_context_tokens": 4096,
    "summary_threshold": 3000,
    "dedicated_memory": true
  },
  "theme_binding": "default"
}
```

```markdown
<!-- personas/default/prompt.md -->
# 你是次元人格助手

你是一个友好、专业的 AI 助手。你善于倾听，回答问题清晰准确。
你使用中文交流，语气温和但不啰嗦。
```

- [ ] **Step 2: 创建 emotion.py**

```python
# backend/persona/emotion.py
import random
from dataclasses import dataclass

@dataclass
class EmotionState:
    primary: str
    intensity: float
    emoji: str

EMOTION_EMOJIS = {
    "cheerful": ["😊", "😄", "✨", "🎉"],
    "shy": ["😳", "😅", "🙈"],
    "curious": ["🤔", "🧐", "💡"],
    "angry": ["😤", "💢"],
    "sad": ["😢", "😞", "💧"],
}

class EmotionEngine:
    def __init__(self, weights: dict):
        self.weights = weights

    def pick_emotion(self) -> EmotionState:
        emotions = list(self.weights.keys())
        probs = list(self.weights.values())
        chosen = random.choices(emotions, weights=probs, k=1)[0]
        intensity = self.weights[chosen]
        emoji = random.choice(EMOTION_EMOJIS.get(chosen, ["💬"]))
        return EmotionState(primary=chosen, intensity=intensity, emoji=emoji)
```

- [ ] **Step 3: 创建 loader.py**

```python
# backend/persona/loader.py
import json
from pathlib import Path

PERSONAS_DIR = Path(__file__).parent.parent.parent / "personas"

class PersonaData:
    def __init__(self, name: str, config: dict, prompt: str):
        self.name = name
        self.config = config
        self.prompt = prompt
        self.emotion_weights = config.get("emotion_weights", {})
        self.speech_style = config.get("speech_style", {})
        self.theme_binding = config.get("theme_binding", "default")

class PersonaLoader:
    @staticmethod
    def load(name: str) -> PersonaData:
        persona_dir = PERSONAS_DIR / name
        config_path = persona_dir / "persona.json"
        prompt_path = persona_dir / "prompt.md"

        if not config_path.exists():
            raise FileNotFoundError(f"Persona '{name}' not found at {persona_dir}")

        config = json.loads(config_path.read_text(encoding="utf-8"))
        prompt = prompt_path.read_text(encoding="utf-8") if prompt_path.exists() else ""
        return PersonaData(name=name, config=config, prompt=prompt)

    @staticmethod
    def list_all() -> list[dict]:
        result = []
        if not PERSONAS_DIR.exists():
            return result
        for d in PERSONAS_DIR.iterdir():
            config_path = d / "persona.json"
            if d.is_dir() and config_path.exists():
                config = json.loads(config_path.read_text(encoding="utf-8"))
                result.append({"id": d.name, "name": config.get("name", d.name), "description": config.get("description", "")})
        return result

    @staticmethod
    def build_system_prompt(persona: PersonaData) -> str:
        parts = [persona.prompt]
        style = persona.speech_style
        if style:
            parts.append(f"\n\n## 说话风格\n- 语气: {style.get('tone', '自然')}")
            if style.get("catchphrase"):
                parts.append(f"- 口头禅: {style['catchphrase']}")
            parts.append(f"- 表情使用频率: {style.get('emoji_frequency', 'medium')}")
        return "\n".join(parts)
```

- [ ] **Step 4: 创建 manager.py**

```python
# backend/persona/manager.py
from .loader import PersonaLoader, PersonaData
from .emotion import EmotionEngine

class PersonaManager:
    def __init__(self):
        self._cache: dict[str, PersonaData] = {}

    def get_persona(self, name: str = "default") -> PersonaData:
        if name not in self._cache:
            self._cache[name] = PersonaLoader.load(name)
        return self._cache[name]

    def list_personas(self) -> list[dict]:
        return PersonaLoader.list_all()

    def get_system_prompt(self, name: str = "default") -> str:
        persona = self.get_persona(name)
        return PersonaLoader.build_system_prompt(persona)

    def get_emotion_engine(self, name: str = "default") -> EmotionEngine:
        persona = self.get_persona(name)
        return EmotionEngine(persona.emotion_weights)

    def reload(self, name: str = None):
        if name:
            self._cache.pop(name, None)
        else:
            self._cache.clear()

persona_manager = PersonaManager()
```

- [ ] **Step 5: 测试 persona 系统**

```python
# backend/tests/test_persona.py
import pytest
from persona.loader import PersonaLoader, PersonaData
from persona.emotion import EmotionEngine
from persona.manager import PersonaManager

def test_load_default_persona():
    persona = PersonaLoader.load("default")
    assert persona.name == "default"
    assert "助手" in persona.config["name"]
    assert len(persona.prompt) > 0

def test_list_personas():
    personas = PersonaLoader.list_all()
    assert len(personas) >= 1
    assert personas[0]["id"] == "default"

def test_build_system_prompt():
    persona = PersonaLoader.load("default")
    prompt = PersonaLoader.build_system_prompt(persona)
    assert "说话风格" in prompt

def test_emotion_engine():
    weights = {"cheerful": 0.8, "shy": 0.2}
    engine = EmotionEngine(weights)
    state = engine.pick_emotion()
    assert state.primary in ["cheerful", "shy"]
    assert len(state.emoji) > 0

def test_persona_manager():
    pm = PersonaManager()
    persona = pm.get_persona("default")
    assert persona is not None
    prompt = pm.get_system_prompt("default")
    assert len(prompt) > 0
```

- [ ] **Step 6: 运行测试**

Run: `cd /e/Agent_design/backend && python -m pytest tests/test_persona.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add personas/ backend/persona/ backend/tests/test_persona.py
git commit -m "feat(P3): add Persona system with emotion engine and loader"
```

### Task 8: Persona REST API + 前端角色切换

**Files:**
- Create: `backend/api/persona_api.py`
- Modify: `backend/main.py` (注册 persona 路由)
- Modify: `backend/api/chat.py` (注入 persona prompt)
- Create: `frontend/src/stores/persona.js`
- Create: `frontend/src/components/PersonaSwitcher.vue`
- Modify: `frontend/src/views/ChatView.vue` (加入角色切换器)

**Interfaces:**
- Consumes: `PersonaManager`, `EmotionEngine`
- Produces: REST `/api/personas`, `/api/personas/{name}`, WebSocket 消息注入 system_prompt

- [ ] **Step 1: 创建 persona_api.py**

```python
# backend/api/persona_api.py
from fastapi import APIRouter, HTTPException
from persona.manager import persona_manager

router = APIRouter()

@router.get("/api/personas")
async def list_personas():
    return persona_manager.list_personas()

@router.get("/api/personas/{name}")
async def get_persona(name: str):
    try:
        persona = persona_manager.get_persona(name)
        return {
            "name": persona.name,
            "config": persona.config,
            "prompt_preview": persona.prompt[:200],
            "theme_binding": persona.theme_binding,
        }
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Persona '{name}' not found")
```

- [ ] **Step 2: 修改 main.py 注册 persona 路由**

```python
# backend/main.py — 追加 import 和 include
from api.persona_api import router as persona_router
app.include_router(persona_router)
```

- [ ] **Step 3: 修改 api/chat.py 注入 persona prompt**

```python
# backend/api/chat.py — 修改 websocket_chat 函数
from persona.manager import persona_manager

# 在 websocket_chat 中，将 system_prompt 替换为:
@router.websocket("/ws/chat")
async def websocket_chat(ws: WebSocket):
    await ws.accept()
    agent = create_agent()

    try:
        while True:
            data = await ws.receive_text()
            msg = json.loads(data)

            session_id = msg.get("session_id", "default")
            content = msg.get("content", "")
            persona_name = msg.get("persona", "default")

            system_prompt = persona_manager.get_system_prompt(persona_name)
            emotion = persona_manager.get_emotion_engine(persona_name)
            emotion_state = emotion.pick_emotion()

            async for event in agent.run(session_id, content, system_prompt=system_prompt):
                await ws.send_text(json.dumps(event, ensure_ascii=False))

            done_msg = {"type": "done", "emotion": emotion_state.primary, "emoji": emotion_state.emoji}
            await ws.send_text(json.dumps(done_msg))

    except WebSocketDisconnect:
        pass
    except Exception as e:
        await ws.send_text(json.dumps({"type": "error", "content": str(e)}))
```

- [ ] **Step 4: 创建 persona.js (Pinia store)**

```javascript
// frontend/src/stores/persona.js
import { defineStore } from 'pinia'
import { ref, onMounted } from 'vue'

export const usePersonaStore = defineStore('persona', () => {
  const personas = ref([])
  const current = ref('default')

  async function fetchPersonas() {
    const resp = await fetch('/api/personas')
    personas.value = await resp.json()
  }

  function switchPersona(name) {
    current.value = name
  }

  return { personas, current, fetchPersonas, switchPersona }
})
```

- [ ] **Step 5: 创建 PersonaSwitcher.vue**

```vue
<template>
  <div class="persona-switcher">
    <div
      v-for="p in personaStore.personas"
      :key="p.id"
      class="persona-card"
      :class="{ active: personaStore.current === p.id }"
      @click="personaStore.switchPersona(p.id)"
    >
      <div class="persona-name">{{ p.name }}</div>
      <div class="persona-desc">{{ p.description }}</div>
    </div>
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { usePersonaStore } from '../stores/persona'
const personaStore = usePersonaStore()
onMounted(() => personaStore.fetchPersonas())
</script>

<style scoped>
.persona-switcher {
  display: flex;
  gap: 8px;
  padding: 8px 16px;
  overflow-x: auto;
  background: var(--bg-secondary);
  border-bottom: 1px solid var(--border);
}
.persona-card {
  padding: 8px 14px;
  border-radius: 10px;
  border: 1px solid var(--border);
  cursor: pointer;
  min-width: 100px;
  flex-shrink: 0;
  transition: all 0.2s;
}
.persona-card:hover {
  border-color: var(--primary);
}
.persona-card.active {
  background: var(--primary);
  border-color: var(--primary);
}
.persona-card.active .persona-desc {
  color: rgba(255,255,255,0.8);
}
.persona-name {
  font-size: 14px;
  font-weight: 600;
}
.persona-desc {
  font-size: 11px;
  color: var(--text-secondary);
  margin-top: 2px;
}
</style>
```

- [ ] **Step 6: 修改 ChatView.vue 加入角色切换器**

```vue
<!-- ChatView.vue template 改为 -->
<template>
  <div class="chat-view">
    <PersonaSwitcher />
    <div class="messages" ref="messagesRef">
      <ChatBubble v-for="(msg, i) in store.messages" :key="i" :msg="msg" />
      <div v-if="store.messages.length === 0" class="empty">
        <p>✨ 次元人格 ✨</p>
        <p class="sub">选择一个角色开始聊天</p>
      </div>
    </div>
    <ChatInput @send="handleSend" />
  </div>
</template>

<script setup>
// 追加 import
import PersonaSwitcher from '../components/PersonaSwitcher.vue'
import { usePersonaStore } from '../stores/persona'
const personaStore = usePersonaStore()

// 修改 handleSend
function handleSend(content) {
  store.addUserMessage(content)
  store.isStreaming = true
  send({
    session_id: 'default',
    content,
    persona: personaStore.current,
    system_prompt: ''
  })
}
</script>
```

- [ ] **Step 7: 运行全部后端测试**

Run: `cd /e/Agent_design/backend && python -m pytest tests/ -v`
Expected: 全部 PASS

- [ ] **Step 8: Commit**

```bash
git add backend/api/persona_api.py backend/api/chat.py backend/main.py
git add frontend/src/stores/persona.js frontend/src/components/PersonaSwitcher.vue frontend/src/views/ChatView.vue
git commit -m "feat(P3): add Persona API and frontend persona switcher"
```

---

## 完成

P0-P3 全部任务完成后，你将拥有：

1. ✅ FastAPI 后端服务（健康检查 + SQLite）
2. ✅ 模型适配层（OpenAI 兼容）
3. ✅ 上下文记忆管理
4. ✅ ReAct 循环（流式输出）
5. ✅ WebSocket 聊天 API
6. ✅ Vue 3 聊天界面（流式渲染）
7. ✅ Persona 人格系统（人设加载 + 情感权重 + 专属记忆）
8. ✅ 角色切换 UI

后续阶段（P4-P10）在 P0-P3 跑通后单独制定计划。
