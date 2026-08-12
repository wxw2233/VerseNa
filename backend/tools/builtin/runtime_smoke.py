import asyncio
import ipaddress
import json
import os
import socket
import subprocess
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import ProxyHandler, Request, build_opener

from tools.base import BaseTool, ToolContext
from tools.paths import ToolPathError, resolve_tool_path
from tools.results import tool_error, tool_result


MAX_BODY_BYTES = 100_000
MAX_TIMEOUT_SECONDS = 30


def _local_url(url: str) -> tuple[bool, str]:
    parsed = urlsplit((url or "").strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return False, "只允许检查 http/https 地址"
    host = parsed.hostname.lower()
    if host == "localhost":
        return True, ""
    try:
        addresses = {ipaddress.ip_address(host)}
    except ValueError:
        try:
            addresses = {
                ipaddress.ip_address(item[4][0])
                for item in socket.getaddrinfo(host, parsed.port or 80, type=socket.SOCK_STREAM)
            }
        except OSError:
            return False, "无法解析目标地址"
    if not addresses or not all(address.is_private or address.is_loopback or address.is_link_local for address in addresses):
        return False, "runtime_smoke 只允许检查本机或内网服务"
    return True, ""


def _read_body(response) -> bytes:
    return response.read(MAX_BODY_BYTES + 1)


def _http_smoke(url: str, expected_service: str, expected_version: str, expected_text: str, timeout: int) -> dict:
    request = Request(url, headers={"Accept": "application/json,text/plain;q=0.9"})
    started = time.monotonic()
    try:
        # 本地服务验证不能被 Clash/系统代理接管，否则可能检查到代理页面或其他服务。
        opener = build_opener(ProxyHandler({}))
        with opener.open(request, timeout=timeout) as response:
            status = int(response.status)
            body_bytes = _read_body(response)
            headers = dict(response.headers.items())
    except HTTPError as exc:
        status = int(exc.code)
        body_bytes = exc.read(MAX_BODY_BYTES + 1)
        headers = dict(exc.headers.items()) if exc.headers else {}
    except (URLError, TimeoutError, OSError) as exc:
        return {"success": False, "error": "CONNECTION_FAILED", "message": str(exc)}

    body = body_bytes[:MAX_BODY_BYTES].decode("utf-8", errors="replace")
    truncated = len(body_bytes) > MAX_BODY_BYTES
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        payload = None

    mismatches = []
    if status < 200 or status >= 300:
        mismatches.append(f"HTTP {status}")
    if expected_service and (not isinstance(payload, dict) or payload.get("service") != expected_service):
        mismatches.append(f"service != {expected_service}")
    if expected_version and (not isinstance(payload, dict) or payload.get("version") != expected_version):
        mismatches.append(f"version != {expected_version}")
    if expected_text and expected_text not in body:
        mismatches.append("响应中缺少 expected_text")

    data = {
        "url": url,
        "status": status,
        "elapsed_ms": round((time.monotonic() - started) * 1000),
        "identity": {
            "service": payload.get("service") if isinstance(payload, dict) else None,
            "version": payload.get("version") if isinstance(payload, dict) else None,
            "instance_id": payload.get("instance_id") if isinstance(payload, dict) else None,
        },
        "headers": {key.lower(): value for key, value in headers.items() if key.lower() in {"content-type", "server"}},
        "body": body,
        "truncated": truncated,
    }
    if mismatches:
        return {"success": False, "error": "WRONG_SERVICE_OR_UNHEALTHY", "message": "; ".join(mismatches), "data": data}
    return {"success": True, "message": "运行时 HTTP 冒烟通过", "data": data}


def _browser_script() -> str:
    return r'''
const { createRequire } = require('module');
const path = require('path');
const fs = require('fs');
const payload = JSON.parse(process.env.VERSENA_SMOKE_PAYLOAD || '{}');
 (async () => {
const requireFromProject = createRequire(path.join(payload.package_root, 'package.json'));
let puppeteer;
try { puppeteer = requireFromProject('puppeteer-core'); } catch (error) {
  try { puppeteer = requireFromProject('puppeteer'); } catch (fallbackError) {
    console.log(JSON.stringify({success: false, error: 'BROWSER_DEPENDENCY_MISSING', message: 'package_root 下未找到 puppeteer-core 或 puppeteer'}));
    process.exit(0);
  }
}
const candidates = [
  process.env.VERSENA_BROWSER_PATH,
  'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
  'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
  '/usr/bin/chromium', '/usr/bin/chromium-browser', '/data/data/com.termux/files/usr/bin/chromium'
].filter(Boolean);
const executablePath = candidates.find((item) => fs.existsSync(item));
let bundledPath = '';
if (!executablePath && typeof puppeteer.executablePath === 'function') {
  try { bundledPath = puppeteer.executablePath(); } catch (error) { bundledPath = ''; }
}
if (!executablePath && !bundledPath) {
  console.log(JSON.stringify({success: false, error: 'BROWSER_NOT_FOUND', message: '未找到 Chromium/Edge/Chrome'}));
  process.exit(0);
}
const browser = await puppeteer.launch({
  executablePath: executablePath || bundledPath,
  headless: true,
  args: ['--no-sandbox', '--disable-gpu', '--no-proxy-server'],
  defaultViewport: { width: payload.width || 1280, height: payload.height || 800 }
});
const page = await browser.newPage();
const errors = [];
page.on('console', (message) => { if (message.type() === 'error') errors.push('[console.error] ' + message.text()); });
page.on('pageerror', (error) => errors.push('[pageerror] ' + error.message));
let failure = null;
try {
  await page.goto(payload.url, { waitUntil: 'networkidle0', timeout: payload.timeout * 1000 });
  if (payload.wait_ms) await new Promise((resolve) => setTimeout(resolve, payload.wait_ms));
  for (const selector of payload.click || []) {
    await page.waitForSelector(selector, { timeout: payload.timeout * 1000 });
    await page.click(selector);
  }
  for (const selector of payload.selectors || []) {
    if (!await page.$(selector)) throw new Error('缺少选择器: ' + selector);
  }
  const text = await page.evaluate(() => document.body?.innerText || '');
  for (const expected of payload.expected_text || []) {
    if (!text.includes(expected)) throw new Error('页面缺少文本: ' + expected);
  }
  if (payload.screenshot) await page.screenshot({ path: payload.screenshot, fullPage: true });
} catch (error) {
  failure = error.message;
}
await browser.close();
console.log(JSON.stringify({success: !failure && errors.length === 0, error: failure || (errors.length ? 'BROWSER_CONSOLE_ERROR' : ''), message: failure || (errors.length ? errors.join('\n') : '浏览器冒烟通过'), console_errors: errors}));
})().catch((error) => {
  console.log(JSON.stringify({success: false, error: 'BROWSER_EXECUTION_FAILED', message: error.message}));
});
'''


class RuntimeSmokeTool(BaseTool):
    name = "runtime_smoke"
    description = (
        "验证本机或内网应用是否真实运行。http 模式会校验 HTTP 状态及 VerseNa 的 service/version/instance_id；"
        "browser 模式可用项目内 Puppeteer 打开页面、点击选择器、检查文本和控制台错误。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "mode": {"type": "string", "enum": ["http", "browser"]},
            "url": {"type": "string", "description": "本机或内网 HTTP 地址"},
            "expected_service": {"type": "string", "description": "期望服务名，默认 VerseNa"},
            "expected_version": {"type": "string", "description": "期望版本，可留空"},
            "expected_text": {"type": "string", "description": "HTTP 响应必须包含的文本"},
            "package_root": {"type": "string", "description": "browser 模式下包含 node_modules 的项目相对目录"},
            "selectors": {"type": "array", "items": {"type": "string"}, "description": "必须存在的 CSS 选择器"},
            "click": {"type": "array", "items": {"type": "string"}, "description": "按顺序点击的 CSS 选择器"},
            "screenshot": {"type": "string", "description": "工作区内截图路径，可留空"},
            "wait_ms": {"type": "integer", "minimum": 0, "maximum": 10000},
            "width": {"type": "integer", "minimum": 320, "maximum": 3000},
            "height": {"type": "integer", "minimum": 240, "maximum": 3000},
            "timeout": {"type": "integer", "minimum": 1, "maximum": MAX_TIMEOUT_SECONDS},
        },
        "required": ["mode", "url"],
        "additionalProperties": False,
    }

    async def execute(
        self,
        mode: str = "",
        url: str = "",
        expected_service: str = "VerseNa",
        expected_version: str = "",
        expected_text: str = "",
        package_root: str = ".",
        selectors: list[str] | None = None,
        click: list[str] | None = None,
        screenshot: str = "",
        wait_ms: int = 0,
        width: int = 1280,
        height: int = 800,
        timeout: int = 15,
        _context: ToolContext | None = None,
        **kwargs,
    ) -> str:
        if not _context:
            return tool_error("MISSING_CONTEXT", "工具执行上下文不可用")
        if mode not in {"http", "browser"}:
            return tool_error("INVALID_MODE", "mode 必须是 http 或 browser")
        allowed, reason = _local_url(url)
        if not allowed:
            return tool_error("INVALID_RUNTIME_URL", reason)
        timeout = max(1, min(int(timeout), MAX_TIMEOUT_SECONDS))
        if mode == "http":
            result = await asyncio.to_thread(_http_smoke, url, expected_service, expected_version, expected_text, timeout)
            return tool_result(result["success"], data=result.get("data"), error=result.get("error", ""), message=result.get("message", ""))

        try:
            package_path = resolve_tool_path(_context, package_root).check_path
            if not package_path.is_dir():
                return tool_error("INVALID_PACKAGE_ROOT", f"项目目录不存在: {package_root}")
            if not package_path.joinpath("package.json").is_file():
                return tool_error("INVALID_PACKAGE_ROOT", f"项目目录缺少 package.json: {package_root}")
            screenshot_path = ""
            if screenshot:
                screenshot_path = str(resolve_tool_path(_context, screenshot).op_path)
        except ToolPathError as exc:
            return tool_error("WORKSPACE_VIOLATION", str(exc))

        payload = {
            "url": url,
            "package_root": str(package_path),
            "selectors": (selectors or [])[:50],
            "click": (click or [])[:20],
            "expected_text": ([expected_text] if expected_text else [])[:20],
            "screenshot": screenshot_path,
            "wait_ms": max(0, min(int(wait_ms), 10000)),
            "width": max(320, min(int(width), 3000)),
            "height": max(240, min(int(height), 3000)),
            "timeout": timeout,
        }
        env = os.environ.copy()
        env["VERSENA_SMOKE_PAYLOAD"] = json.dumps(payload, ensure_ascii=False)
        node = "node.exe" if os.name == "nt" else "node"
        try:
            completed = await asyncio.to_thread(
                subprocess.run,
                [node, "--input-type=commonjs", "-e", _browser_script()],
                cwd=str(package_path),
                env=env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout + 10,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            return tool_error("BROWSER_EXECUTION_FAILED", str(exc))
        output = completed.stdout.strip().splitlines()[-1] if completed.stdout.strip() else ""
        try:
            result = json.loads(output)
        except json.JSONDecodeError:
            return tool_error("BROWSER_EXECUTION_FAILED", (completed.stderr or completed.stdout or "浏览器脚本无有效输出")[-3000:])
        if completed.returncode != 0 and result.get("success"):
            result["success"] = False
        return tool_result(result.get("success", False), data=result, error=result.get("error", ""), message=result.get("message", ""))


def register(registry):
    registry.register(RuntimeSmokeTool())
