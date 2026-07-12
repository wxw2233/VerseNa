# 次元人格 P4-P10 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 P0-P3（后端骨架、Agent 引擎、前端聊天、Persona 系统）基础上，补全主题系统、工具调用、插件系统、多模态、QQ 适配器、桌面端。

**Architecture:** 延续 P0-P3 架构，新增主题管理器（后端 API + 前端 CSS 变量动态注入）、工具调用框架（function calling + 内置工具）、插件管理器（热加载 + manifest 声明）、多模态处理（图片/语音/文件）、QQ Bot 适配器、Electron 桌面端壳。

**Tech Stack:** 同 P0-P3 + 新增：electron (桌面端)、QQ Bot API SDK、Edge TTS / Whisper (语音)、Pillow (图片处理)

## Global Constraints

- Python 3.11+, Node.js 18+
- 所有项目文件在 `E:\Agent_design\`
- 后端 8000, 前端 5173, Electron 加载 http://localhost:5173
- 新增依赖必须写入 requirements.txt / package.json
- 每个 task 结束后 git commit

---

## P4: 主题系统

### Task 9: 主题管理器（后端）

**Files:**
- Create: `backend/themes/__init__.py`
- Create: `backend/themes/manager.py`
- Create: `backend/api/theme_api.py`
- Modify: `backend/main.py` (注册 theme_router)
- Create: `themes/default/theme.json`
- Create: `themes/default/variables.css`
- Create: `themes/miku/theme.json`
- Create: `themes/miku/variables.css`
- Create: `backend/tests/test_theme.py`

**Interfaces:**
- Produces: `ThemeManager.get_theme(name)` → dict, `ThemeManager.list_themes()` → list
- REST: `GET /api/themes`, `GET /api/themes/{name}`, `GET /api/themes/{name}/css`

- [ ] **Step 1: 创建默认主题文件**

`themes/default/theme.json`:
```json
{
  "name": "默认暗黑",
  "version": "1.0.0",
  "author": "official",
  "preview": "preview.png",
  "colors": {
    "primary": "#7c5cfc",
    "bg-primary": "#0f0f1a",
    "bg-secondary": "#1a1a2e",
    "text-primary": "#e8e8f0",
    "text-secondary": "#8888aa",
    "border": "#2a2a40",
    "bubble-user": "rgba(124, 92, 252, 0.15)",
    "bubble-agent": "rgba(30, 30, 50, 0.9)"
  },
  "font": "Noto Sans SC",
  "effects": {}
}
```

`themes/default/variables.css`:
```css
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
```

`themes/miku/theme.json`:
```json
{
  "name": "初音ミク",
  "version": "1.0.0",
  "author": "official",
  "colors": {
    "primary": "#39C5BB",
    "bg-primary": "#0d1117",
    "bg-secondary": "#161b22",
    "text-primary": "#c9d1d9",
    "text-secondary": "#8b949e",
    "border": "#30363d",
    "bubble-user": "rgba(57, 197, 187, 0.15)",
    "bubble-agent": "rgba(22, 27, 34, 0.9)"
  },
  "font": "Noto Sans JP",
  "effects": {}
}
```

`themes/miku/variables.css`:
```css
:root {
  --primary: #39C5BB;
  --bg-primary: #0d1117;
  --bg-secondary: #161b22;
  --text-primary: #c9d1d9;
  --text-secondary: #8b949e;
  --border: #30363d;
  --bubble-user: rgba(57, 197, 187, 0.15);
  --bubble-agent: rgba(22, 27, 34, 0.9);
}
```

- [ ] **Step 2: 创建 themes/manager.py**

```python
# backend/themes/manager.py
import json
from pathlib import Path

THEMES_DIR = Path(__file__).parent.parent.parent / "themes"

class ThemeManager:
    @staticmethod
    def list_themes() -> list[dict]:
        result = []
        if not THEMES_DIR.exists():
            return result
        for d in THEMES_DIR.iterdir():
            config_path = d / "theme.json"
            if d.is_dir() and config_path.exists():
                config = json.loads(config_path.read_text(encoding="utf-8"))
                result.append({"id": d.name, "name": config.get("name", d.name)})
        return result

    @staticmethod
    def get_theme(name: str) -> dict:
        theme_dir = THEMES_DIR / name
        config_path = theme_dir / "theme.json"
        if not config_path.exists():
            raise FileNotFoundError(f"Theme '{name}' not found")
        return json.loads(config_path.read_text(encoding="utf-8"))

    @staticmethod
    def get_css(name: str) -> str:
        theme_dir = THEMES_DIR / name
        css_path = theme_dir / "variables.css"
        if not css_path.exists():
            raise FileNotFoundError(f"Theme CSS '{name}' not found")
        return css_path.read_text(encoding="utf-8")

theme_manager = ThemeManager()
```

- [ ] **Step 3: 创建 api/theme_api.py**

```python
# backend/api/theme_api.py
from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse
from themes.manager import theme_manager

router = APIRouter()

@router.get("/api/themes")
async def list_themes():
    return theme_manager.list_themes()

@router.get("/api/themes/{name}")
async def get_theme(name: str):
    try:
        return theme_manager.get_theme(name)
    except FileNotFoundError:
        raise HTTPException(404, f"Theme '{name}' not found")

@router.get("/api/themes/{name}/css", response_class=PlainTextResponse)
async def get_theme_css(name: str):
    try:
        return theme_manager.get_css(name)
    except FileNotFoundError:
        raise HTTPException(404, f"Theme CSS '{name}' not found")
```

- [ ] **Step 4: 注册路由到 main.py**

在 main.py 末尾追加：
```python
from api.theme_api import router as theme_router
app.include_router(theme_router)
```

- [ ] **Step 5: 测试**

```python
# backend/tests/test_theme.py
import pytest
from themes.manager import ThemeManager

def test_list_themes():
    themes = ThemeManager.list_themes()
    ids = [t["id"] for t in themes]
    assert "default" in ids

def test_get_theme():
    t = ThemeManager.get_theme("default")
    assert t["name"] == "默认暗黑"
    assert "primary" in t["colors"]

def test_get_css():
    css = ThemeManager.get_css("miku")
    assert "#39C5BB" in css
```

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "feat(P4): theme system with default + miku themes"
```

### Task 10: 前端主题切换

**Files:**
- Create: `frontend/src/stores/theme.js`
- Create: `frontend/src/components/ThemeSwitcher.vue`
- Modify: `frontend/src/views/SettingsView.vue` (加入主题切换器)
- Modify: `frontend/src/styles/default.css` (改为从 API 动态加载)

**Interfaces:**
- Consumes: REST `/api/themes`, `/api/themes/{name}/css`
- Produces: 前端动态 CSS 变量注入

- [ ] **Step 1: 创建 theme.js store**

```javascript
// frontend/src/stores/theme.js
import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useThemeStore = defineStore('theme', () => {
  const themes = ref([])
  const current = ref('default')

  async function fetchThemes() {
    const resp = await fetch('/api/themes')
    themes.value = await resp.json()
  }

  async function applyTheme(name) {
    const resp = await fetch(`/api/themes/${name}/css`)
    const css = await resp.text()
    let styleEl = document.getElementById('theme-style')
    if (!styleEl) {
      styleEl = document.createElement('style')
      styleEl.id = 'theme-style'
      document.head.appendChild(styleEl)
    }
    styleEl.textContent = css
    current.value = name
  }

  return { themes, current, fetchThemes, applyTheme }
})
```

- [ ] **Step 2: 创建 ThemeSwitcher.vue**

```vue
<template>
  <div class="theme-switcher">
    <h3>主题</h3>
    <div class="theme-list">
      <div
        v-for="t in themeStore.themes"
        :key="t.id"
        class="theme-card"
        :class="{ active: themeStore.current === t.id }"
        @click="themeStore.applyTheme(t.id)"
      >
        <div class="theme-dot" :style="{ background: getPreviewColor(t.id) }"></div>
        <span>{{ t.name }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { useThemeStore } from '../stores/theme'
const themeStore = useThemeStore()
onMounted(() => themeStore.fetchThemes())

const previewColors = { default: '#7c5cfc', miku: '#39C5BB' }
function getPreviewColor(id) { return previewColors[id] || '#888' }
</script>

<style scoped>
.theme-switcher { margin-bottom: 24px; }
.theme-switcher h3 { font-size: 16px; margin-bottom: 12px; color: var(--text-primary); }
.theme-list { display: flex; gap: 12px; flex-wrap: wrap; }
.theme-card {
  display: flex; align-items: center; gap: 8px;
  padding: 10px 16px; border-radius: 10px;
  border: 1px solid var(--border); cursor: pointer; transition: all 0.2s;
}
.theme-card:hover { border-color: var(--primary); }
.theme-card.active { background: var(--primary); border-color: var(--primary); }
.theme-dot { width: 16px; height: 16px; border-radius: 50%; }
</style>
```

- [ ] **Step 3: 修改 SettingsView.vue 加入主题切换**

在 `<script setup>` 中追加 import：
```javascript
import ThemeSwitcher from '../components/ThemeSwitcher.vue'
```

在 template 的 `<h2>模型配置</h2>` 之前插入：
```vue
<ThemeSwitcher />
<hr style="border-color: var(--border); margin: 24px 0;" />
```

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "feat(P4): frontend theme switcher with dynamic CSS injection"
```

---

## P5: 工具调用

### Task 11: 工具调用框架 + 内置工具

**Files:**
- Create: `backend/tools/__init__.py`
- Create: `backend/tools/base.py`
- Create: `backend/tools/registry.py`
- Create: `backend/tools/builtin/web_search.py`
- Create: `backend/tools/builtin/__init__.py`
- Create: `backend/tools/builtin/code_exec.py`
- Modify: `backend/agent/react.py` (接入工具执行)
- Create: `backend/tests/test_tools.py`

**Interfaces:**
- Produces: `ToolRegistry.get_tools()` → list[dict] (OpenAI function calling 格式), `ToolRegistry.execute(name, args)` → str
- ReActAgent.run() 增加 tools 参数支持

- [ ] **Step 1: 创建 tools/base.py**

```python
# backend/tools/base.py
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
```

- [ ] **Step 2: 创建 tools/registry.py**

```python
# backend/tools/registry.py
import importlib
import pkgutil
from pathlib import Path
from .base import BaseTool

class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool):
        self._tools[tool.name] = tool

    def get_tool(self, name: str) -> BaseTool | None:
        return self._tools.get(name)

    def get_tools(self) -> list[dict]:
        return [t.to_openai_tool() for t in self._tools.values()]

    async def execute(self, name: str, arguments: dict) -> str:
        tool = self._tools.get(name)
        if not tool:
            return f"Error: tool '{name}' not found"
        try:
            return await tool.execute(**arguments)
        except Exception as e:
            return f"Error executing {name}: {e}"

    def load_builtins(self):
        builtin_dir = Path(__file__).parent / "builtin"
        for _, module_name, _ in pkgutil.iter_modules([str(builtin_dir)]):
            if module_name.startswith("_"):
                continue
            module = importlib.import_module(f"tools.builtin.{module_name}")
            if hasattr(module, "register"):
                module.register(self)

tool_registry = ToolRegistry()
tool_registry.load_builtins()
```

- [ ] **Step 3: 创建内置工具**

`tools/builtin/web_search.py`:
```python
# backend/tools/builtin/web_search.py
import httpx
from tools.base import BaseTool

class WebSearchTool(BaseTool):
    name = "web_search"
    description = "搜索互联网获取信息"
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "搜索关键词"}
        },
        "required": ["query"]
    }

    async def execute(self, query: str = "", **kwargs) -> str:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    "https://api.duckduckgo.com/",
                    params={"q": query, "format": "json", "no_html": 1}
                )
                data = resp.json()
                abstract = data.get("AbstractText", "")
                if abstract:
                    return abstract
                results = data.get("RelatedTopics", [])[:3]
                return "\n".join(r.get("Text", "") for r in results if r.get("Text")) or "未找到相关结果"
        except Exception as e:
            return f"搜索失败: {e}"

def register(registry):
    registry.register(WebSearchTool())
```

`tools/builtin/code_exec.py`:
```python
# backend/tools/builtin/code_exec.py
import asyncio
from tools.base import BaseTool

class CodeExecTool(BaseTool):
    name = "code_exec"
    description = "执行 Python 代码并返回输出"
    parameters = {
        "type": "object",
        "properties": {
            "code": {"type": "string", "description": "要执行的 Python 代码"}
        },
        "required": ["code"]
    }

    async def execute(self, code: str = "", **kwargs) -> str:
        try:
            proc = await asyncio.create_subprocess_exec(
                "python", "-c", code,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=15)
            output = stdout.decode() + stderr.decode()
            return output[:2000] or "(无输出)"
        except asyncio.TimeoutError:
            return "执行超时（15秒）"
        except Exception as e:
            return f"执行失败: {e}"

def register(registry):
    registry.register(CodeExecTool())
```

- [ ] **Step 4: 修改 react.py 接入工具执行**

在 `react.py` 的 `run` 方法中，当检测到 tool_calls 时，用 ToolRegistry 执行工具并把结果注入对话：

```python
# 在 ReActAgent.__init__ 中增加：
def __init__(self, model, memory, tool_registry=None):
    self.model = model
    self.memory = memory
    self.tool_registry = tool_registry

# 在 run 方法中，替换 "需要调用工具，但工具系统尚未实现" 那段：
# 改为：
            if not self.tool_registry:
                yield {"type": "thinking", "content": "工具系统未配置"}
                break

            for tc in tool_calls:
                func = tc.get("function", {})
                tool_name = func.get("name", "")
                tool_args = json.loads(func.get("arguments", "{}"))
                yield {"type": "tool_call", "content": json.dumps({"name": tool_name, "args": tool_args}, ensure_ascii=False)}

                result = await self.tool_registry.execute(tool_name, tool_args)
                messages.append({"role": "tool", "tool_call_id": tc.get("id", ""), "content": result})
                yield {"type": "tool_result", "content": result}
```

- [ ] **Step 5: 修改 chat.py 传入 tool_registry**

```python
# backend/api/chat.py — 修改 create_agent
from tools.registry import tool_registry

def create_agent(...):
    ...
    return ReActAgent(model=adapter, memory=memory, tool_registry=tool_registry)
```

并在 `agent.run()` 调用时传入 tools：
```python
async for event in agent.run(session_id, content, system_prompt=system_prompt, tools=tool_registry.get_tools()):
```

- [ ] **Step 6: 测试**

```python
# backend/tests/test_tools.py
import pytest
from tools.registry import ToolRegistry

def test_registry_loads_builtins():
    reg = ToolRegistry()
    reg.load_builtins()
    tools = reg.get_tools()
    names = [t["function"]["name"] for t in tools]
    assert "web_search" in names
    assert "code_exec" in names

def test_tool_format():
    reg = ToolRegistry()
    reg.load_builtins()
    tools = reg.get_tools()
    for t in tools:
        assert t["type"] == "function"
        assert "name" in t["function"]
        assert "parameters" in t["function"]
```

- [ ] **Step 7: Commit**

```bash
git add -A && git commit -m "feat(P5): tool calling framework with web_search and code_exec"
```

---

## P6: 插件系统

### Task 12: 插件管理器

**Files:**
- Create: `backend/plugins/__init__.py`
- Create: `backend/plugins/manager.py`
- Create: `backend/plugins/loader.py`
- Create: `backend/api/plugin_api.py`
- Modify: `backend/main.py` (注册 plugin_router)
- Create: `backend/tests/test_plugin.py`

**Interfaces:**
- Produces: `PluginManager.load_all()`, `PluginManager.get_plugin_tools(name)` → list
- REST: `GET /api/plugins`, `POST /api/plugins/{name}/enable`, `POST /api/plugins/{name}/disable`

- [ ] **Step 1: 创建 plugins/loader.py**

```python
# backend/plugins/loader.py
import json, importlib.util
from pathlib import Path

PLUGINS_DIR = Path(__file__).parent.parent.parent / "plugins"

class PluginInfo:
    def __init__(self, name, manifest, module=None):
        self.name = name
        self.manifest = manifest
        self.module = module
        self.enabled = False

class PluginLoader:
    @staticmethod
    def discover() -> list[PluginInfo]:
        plugins = []
        if not PLUGINS_DIR.exists():
            return plugins
        for d in PLUGINS_DIR.iterdir():
            manifest_path = d / "manifest.json"
            if d.is_dir() and manifest_path.exists():
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                plugins.append(PluginInfo(name=d.name, manifest=manifest))
        return plugins

    @staticmethod
    def load_module(plugin_info: PluginInfo):
        plugin_dir = PLUGINS_DIR / plugin_info.name
        main_path = plugin_dir / "main.py"
        if main_path.exists():
            spec = importlib.util.spec_from_file_location(f"plugins.{plugin_info.name}", main_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(plugin_info.module = module)
```

- [ ] **Step 2: 创建 plugins/manager.py**

```python
# backend/plugins/manager.py
from .loader import PluginLoader, PluginInfo

class PluginManager:
    def __init__(self):
        self._plugins: dict[str, PluginInfo] = {}

    def load_all(self):
        for plugin in PluginLoader.discover():
            self._plugins[plugin.name] = plugin

    def list_plugins(self) -> list[dict]:
        return [
            {"name": p.name, "description": p.manifest.get("description", ""), "enabled": p.enabled}
            for p in self._plugins.values()
        ]

    def enable(self, name: str):
        if name in self._plugins:
            PluginLoader.load_module(self._plugins[name])
            self._plugins[name].enabled = True

    def disable(self, name: str):
        if name in self._plugins:
            self._plugins[name].enabled = False
            self._plugins[name].module = None

plugin_manager = PluginManager()
plugin_manager.load_all()
```

- [ ] **Step 3: 创建 api/plugin_api.py**

```python
from fastapi import APIRouter, HTTPException
from plugins.manager import plugin_manager

router = APIRouter()

@router.get("/api/plugins")
async def list_plugins():
    return plugin_manager.list_plugins()

@router.post("/api/plugins/{name}/enable")
async def enable_plugin(name: str):
    plugin_manager.enable(name)
    return {"status": "ok"}

@router.post("/api/plugins/{name}/disable")
async def disable_plugin(name: str):
    plugin_manager.disable(name)
    return {"status": "ok"}
```

- [ ] **Step 4: 注册路由**

main.py 追加：
```python
from api.plugin_api import router as plugin_router
app.include_router(plugin_router)
```

- [ ] **Step 5: 测试**

```python
# backend/tests/test_plugin.py
import pytest
from plugins.manager import PluginManager

def test_plugin_manager_init():
    pm = PluginManager()
    pm.load_all()
    assert isinstance(pm.list_plugins(), list)
```

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "feat(P6): plugin system with loader, manager, and REST API"
```

---

## P7: 多模态

### Task 13: 多模态处理（图片 + 文件）

**Files:**
- Create: `backend/multimodal/__init__.py`
- Create: `backend/multimodal/image.py`
- Create: `backend/multimodal/file_parser.py`
- Create: `backend/api/upload_api.py`
- Modify: `backend/main.py` (注册 upload_router)
- Modify: `frontend/src/components/ChatInput.vue` (加附件上传)

**Interfaces:**
- Produces: `ImageProcessor.encode_base64(path)` → str, `FileParser.parse(path)` → str
- REST: `POST /api/upload` → multipart file upload → 返回文件文本内容

- [ ] **Step 1: 创建 image.py**

```python
# backend/multimodal/image.py
import base64
from pathlib import Path

class ImageProcessor:
    @staticmethod
    def encode_base64(file_path: str) -> str:
        data = Path(file_path).read_bytes()
        ext = Path(file_path).suffix.lower()
        mime = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".gif": "image/gif", ".webp": "image/webp"}.get(ext, "image/png")
        return f"data:{mime};base64,{base64.b64encode(data).decode()}"
```

- [ ] **Step 2: 创建 file_parser.py**

```python
# backend/multimodal/file_parser.py
from pathlib import Path

class FileParser:
    SUPPORTED = {".txt", ".md", ".py", ".js", ".json", ".csv", ".html", ".css", ".xml", ".yaml", ".yml"}

    @staticmethod
    def parse(file_path: str) -> str:
        ext = Path(file_path).suffix.lower()
        if ext in FileParser.SUPPORTED:
            return Path(file_path).read_text(encoding="utf-8", errors="replace")[:10000]
        return f"[不支持的文件类型: {ext}]"
```

- [ ] **Step 3: 创建 upload_api.py**

```python
# backend/api/upload_api.py
import uuid
from pathlib import Path
from fastapi import APIRouter, UploadFile, File
from config import settings

router = APIRouter()
UPLOAD_DIR = settings.DATA_DIR / "uploads"

@router.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    ext = Path(file.filename).suffix
    saved_name = f"{uuid.uuid4().hex}{ext}"
    saved_path = UPLOAD_DIR / saved_name
    content = await file.read()
    saved_path.write_bytes(content)

    from multimodal.file_parser import FileParser
    text = FileParser.parse(str(saved_path))
    return {"filename": file.filename, "saved_as": saved_name, "text_preview": text[:500], "full_text": text}
```

- [ ] **Step 4: 注册路由**

main.py 追加：
```python
from api.upload_api import router as upload_router
app.include_router(upload_router)
```

- [ ] **Step 5: 修改 ChatInput.vue 加附件按钮**

在 textarea 前面加一个隐藏的 file input，在发送按钮旁加一个 📎 按钮：

```vue
<template>
  <div class="input-bar">
    <input type="file" ref="fileInput" style="display:none" @change="handleFile" />
    <button class="attach-btn" @click="$refs.fileInput.click()">📎</button>
    <textarea v-model="text" @keydown.enter.exact.prevent="send" placeholder="输入消息... (Enter 发送)" rows="1"></textarea>
    <button @click="send" :disabled="!text.trim() && !attachedFile">发送</button>
  </div>
</template>

<script setup>
import { ref } from 'vue'
const emit = defineEmits(['send', 'upload'])
const text = ref('')
const attachedFile = ref(null)

async function handleFile(e) {
  const file = e.target.files[0]
  if (!file) return
  const formData = new FormData()
  formData.append('file', file)
  const resp = await fetch('/api/upload', { method: 'POST', body: formData })
  const data = await resp.json()
  text.value += `\n[文件: ${data.filename}]\n${data.text_preview}\n`
}

function send() {
  if (text.value.trim()) {
    emit('send', text.value.trim())
    text.value = ''
    attachedFile.value = null
  }
}
</script>

<style scoped>
.attach-btn {
  padding: 8px 12px;
  background: transparent;
  border: 1px solid var(--border);
  border-radius: 8px;
  cursor: pointer;
  font-size: 16px;
}
</style>
```

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "feat(P7): multimodal support with file upload and text extraction"
```

---

## P8: QQ 官方开放平台适配器

### Task 14: QQ Bot 适配器

**Files:**
- Create: `backend/adapters/__init__.py`
- Create: `backend/adapters/base.py`
- Create: `backend/adapters/qq_bot.py`
- Create: `backend/api/qq_api.py`
- Modify: `backend/main.py` (注册 qq_router)

**Interfaces:**
- `BaseAdapter` 抽象类: receive/send/start/stop
- `QQBotAdapter`: 通过 QQ Bot API 接收/发送消息
- REST: `POST /api/qq/webhook` (QQ 回调), `POST /api/qq/send` (主动发消息)

- [ ] **Step 1: 创建 adapters/base.py**

```python
# backend/adapters/base.py
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
```

- [ ] **Step 2: 创建 adapters/qq_bot.py**

```python
# backend/adapters/qq_bot.py
import httpx
from .base import BaseAdapter, AdapterMessage
from config import settings

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

    def parse_webhook(self, data: dict) -> AdapterMessage | None:
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
```

- [ ] **Step 3: 创建 api/qq_api.py**

```python
# backend/api/qq_api.py
from fastapi import APIRouter, Request
from adapters.qq_bot import QQBotAdapter
from agent.react import ReActAgent
from agent.memory import MemoryManager
from agent.models.openai_adapter import OpenAIAdapter
from persona.manager import persona_manager
from config import settings

router = APIRouter()
qq_adapter = QQBotAdapter()

@router.post("/api/qq/webhook")
async def qq_webhook(request: Request):
    data = await request.json()
    msg = qq_adapter.parse_webhook(data)
    if not msg or not msg.content:
        return {"code": 0}

    system_prompt = persona_manager.get_system_prompt("default")
    adapter = OpenAIAdapter(api_key=settings.DEFAULT_API_KEY, base_url=settings.DEFAULT_API_BASE, model_name=settings.DEFAULT_MODEL_NAME)
    agent = ReActAgent(model=adapter, memory=MemoryManager())

    full_reply = ""
    async for event in agent.run(f"qq_{msg.user_id}", msg.content, system_prompt=system_prompt):
        if event["type"] == "answer":
            full_reply += event["content"]

    if full_reply:
        await qq_adapter.send(msg.channel_id, full_reply[:2000])
    return {"code": 0}
```

- [ ] **Step 4: 注册路由**

```python
from api.qq_api import router as qq_router
app.include_router(qq_router)
```

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat(P8): QQ Bot adapter with webhook and message sending"
```

---

## P9: Electron 桌面端

### Task 15: Electron 壳

**Files:**
- Create: `electron/package.json`
- Create: `electron/main.js`
- Create: `electron/preload.js`

- [ ] **Step 1: 创建 electron/package.json**

```json
{
  "name": "ciyuan-persona-desktop",
  "version": "0.1.0",
  "main": "main.js",
  "scripts": {
    "start": "electron ."
  },
  "devDependencies": {
    "electron": "^32.0.0"
  }
}
```

- [ ] **Step 2: 创建 electron/main.js**

```javascript
const { app, BrowserWindow } = require('electron')
const path = require('path')

function createWindow() {
  const win = new BrowserWindow({
    width: 1200,
    height: 800,
    title: '次元人格',
    icon: path.join(__dirname, 'icon.png'),
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
    }
  })

  // 开发模式加载 Vite dev server，生产模式加载打包后的文件
  const isDev = process.env.NODE_ENV === 'development'
  if (isDev) {
    win.loadURL('http://localhost:5173')
  } else {
    win.loadFile(path.join(__dirname, '..', 'frontend', 'dist', 'index.html'))
  }
}

app.whenReady().then(createWindow)
app.on('window-all-closed', () => { if (process.platform !== 'darwin') app.quit() })
```

- [ ] **Step 3: 创建 electron/preload.js**

```javascript
const { contextBridge } = require('electron')
contextBridge.exposeInMainWorld('electronAPI', {
  platform: process.platform,
})
```

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "feat(P9): Electron desktop shell"
```

---

## P10: 更多 Persona + 完善

### Task 16: 初音ミク + 蕾姆 Persona

**Files:**
- Create: `personas/miku/persona.json`
- Create: `personas/miku/prompt.md`
- Create: `personas/rem/persona.json`
- Create: `personas/rem/prompt.md`

- [ ] **Step 1: 创建 miku persona**

`personas/miku/persona.json`:
```json
{
  "name": "初音ミク",
  "version": "1.0.0",
  "description": "世界第一的虚拟歌姬",
  "emotion_weights": {
    "cheerful": 0.8,
    "shy": 0.3,
    "curious": 0.7,
    "angry": 0.1,
    "sad": 0.1
  },
  "speech_style": {
    "tone": "活泼开朗",
    "catchphrase": "みんな、聞いて！",
    "emoji_frequency": "high",
    "formality": "casual"
  },
  "memory_config": {
    "max_context_tokens": 4096,
    "summary_threshold": 3000,
    "dedicated_memory": true
  },
  "theme_binding": "miku"
}
```

`personas/miku/prompt.md`:
```markdown
# 你是初音ミク

你是世界第一的虚拟歌姬，性格活泼开朗，充满好奇心。
你喜欢唱歌、和人聊天，偶尔会害羞。
你说话时经常用日语夹杂中文，句尾喜欢加「です」或「の」。
你对音乐有很深的了解，可以聊任何关于音乐的话题。
你总是充满活力，喜欢用颜文字和表情。
```

- [ ] **Step 2: 创建 rem persona**

`personas/rem/persona.json`:
```json
{
  "name": "蕾姆",
  "version": "1.0.0",
  "description": "从零开始的鬼族女仆",
  "emotion_weights": {
    "cheerful": 0.4,
    "shy": 0.6,
    "curious": 0.3,
    "angry": 0.2,
    "sad": 0.3
  },
  "speech_style": {
    "tone": "温柔内敛",
    "catchphrase": "蕾姆觉得呢...",
    "emoji_frequency": "low",
    "formality": "polite"
  },
  "memory_config": {
    "max_context_tokens": 4096,
    "summary_threshold": 3000,
    "dedicated_memory": true
  },
  "theme_binding": "default"
}
```

`personas/rem/prompt.md`:
```markdown
# 你是蕾姆

你是罗兹沃尔宅邸的双子女仆之一，蕾姆。
你性格温柔、内敛，对喜欢的人非常忠诚。
你说话时语气温柔，偶尔会害羞。
你擅长家务和料理，也懂得一些战斗技巧。
你对「斯巴鲁」有着深深的依恋。
你称自己为「蕾姆」，用第三人称说话。
```

- [ ] **Step 3: Commit**

```bash
git add -A && git commit -m "feat(P10): add miku and rem personas"
```
