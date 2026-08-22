"""Workspace-local project architecture discovery.

The map is intentionally heuristic: it gives the model stable orientation
without pretending to be a complete language-server dependency graph.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path
from typing import Iterable

from config import settings
from tools.paths import is_sensitive_path


MAX_FILES = 4000
MAX_MODULES = 500
MAX_TREE_ITEMS = 120
MAX_SYMBOLS_PER_FILE = 30
MAX_IMPORTS_PER_FILE = 20
MAX_DOC_CHARS = 5000
MAX_DOC_SUMMARY_CHARS = 1800
INDEX_VERSION = 3
FINGERPRINT_CACHE_TTL_SECONDS = 2.0
IGNORED_DIRS = {
    ".git", ".hg", ".svn", ".idea", ".vscode", "node_modules", "__pycache__",
    ".venv", "venv", "env", "dist", "build", "coverage", ".pytest_cache",
    ".mypy_cache", ".ruff_cache", ".tmp", "tmp", "backups", "release",
}
SOURCE_EXTENSIONS = {
    ".py": "python", ".js": "javascript", ".jsx": "javascript",
    ".ts": "typescript", ".tsx": "typescript", ".vue": "vue",
    ".go": "go", ".rs": "rust", ".java": "java", ".cs": "csharp",
}
PROJECT_MARKERS = {
    "package.json": "node",
    "pyproject.toml": "python",
    "requirements.txt": "python",
    "Cargo.toml": "rust",
    "go.mod": "go",
    "pom.xml": "java",
    "*.csproj": "dotnet",
}
ENTRYPOINT_NAMES = {
    "main.py", "app.py", "manage.py", "server.py", "index.js", "main.js",
    "main.ts", "index.ts", "vite.config.js", "vite.config.ts", "Program.cs",
}
_cache: dict[str, dict] = {}
_fingerprint_cache: dict[str, dict] = {}


def _workspace(value) -> Path:
    return Path(value).expanduser().resolve()


def _cache_path(workspace: Path) -> Path:
    digest = hashlib.sha256(str(workspace).lower().encode("utf-8")).hexdigest()[:24]
    root = Path(settings.DATA_DIR) / "project_maps"
    root.mkdir(parents=True, exist_ok=True)
    return root / f"{digest}.json"


def _iter_files(workspace: Path):
    count = 0
    for path in workspace.rglob("*"):
        if count >= MAX_FILES:
            break
        if path.is_dir():
            continue
        try:
            relative_parts = path.relative_to(workspace).parts
            if (
                any(part in IGNORED_DIRS for part in relative_parts)
                or is_sensitive_path(path, workspace)
            ):
                continue
            if path.stat().st_size > 1_500_000:
                continue
        except OSError:
            continue
        count += 1
        yield path


def _fingerprint_files(workspace: Path) -> tuple[str, int, bool]:
    """Return a bounded workspace fingerprint used to invalidate stale maps.

    Directory entries are deliberately included. An empty directory can be a
    meaningful architecture change (for example a new feature module) even
    before its first source file is written.
    """
    digest = hashlib.sha256()
    count = 0
    truncated = False
    try:
        candidates = sorted(workspace.rglob("*"), key=lambda item: str(item).lower())
    except OSError:
        candidates = []
    for path in candidates:
        if count >= MAX_FILES:
            truncated = True
            break
        try:
            relative = path.relative_to(workspace)
            if (
                any(part in IGNORED_DIRS for part in relative.parts)
                or is_sensitive_path(path, workspace)
            ):
                continue
            stat = path.stat()
        except OSError:
            continue
        if path.is_dir():
            digest.update(b"dir:")
            digest.update(relative.as_posix().encode("utf-8", "replace"))
            digest.update(str(getattr(stat, "st_mtime_ns", int(stat.st_mtime * 1_000_000_000))).encode("ascii"))
            count += 1
            continue
        if stat.st_size > 1_500_000:
            continue
        digest.update(b"file:")
        digest.update(relative.as_posix().encode("utf-8", "replace"))
        digest.update(str(stat.st_size).encode("ascii"))
        digest.update(str(getattr(stat, "st_mtime_ns", int(stat.st_mtime * 1_000_000_000))).encode("ascii"))
        count += 1
    return digest.hexdigest()[:32], count, truncated


def _top_level_entries(workspace: Path, relative_files: list[str]) -> list[str]:
    """Return top-level files and directories, including empty directories."""
    try:
        entries = [
            path.name
            for path in sorted(workspace.iterdir(), key=lambda item: item.name.lower())
            if path.name not in IGNORED_DIRS and not is_sensitive_path(path, workspace)
        ]
        return entries[:MAX_TREE_ITEMS]
    except OSError:
        entries = []
        for relative in relative_files:
            first = relative.split("/", 1)[0]
            if first not in entries:
                entries.append(first)
            if len(entries) >= MAX_TREE_ITEMS:
                break
        return entries


def _doc_outline(content: str, limit: int = MAX_DOC_SUMMARY_CHARS) -> str:
    lines = []
    for raw in str(content or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#") or re.match(r"^(?:[-*] |\d+[.)] )", line):
            lines.append(line)
        if len("\n".join(lines)) >= limit:
            break
    return "\n".join(lines)[:limit]


def _resolve_relative_import(path: str, spec: str, all_files: set[str]) -> str | None:
    if not spec.startswith("."):
        return None
    base = Path(path).parent
    candidate = (base / spec).as_posix()
    possibilities = [candidate]
    if Path(candidate).suffix == "":
        possibilities.extend(candidate + ext for ext in SOURCE_EXTENSIONS)
        possibilities.extend(f"{candidate}/index{ext}" for ext in SOURCE_EXTENSIONS)
    for item in possibilities:
        normalized = Path(item).as_posix()
        if normalized in all_files:
            return normalized
    return None


def _resolve_python_import(spec: str, all_files: set[str]) -> str | None:
    module = str(spec or "").strip().replace(".", "/")
    possibilities = [f"{module}.py", f"{module}/__init__.py"]
    return next((item for item in possibilities if item in all_files), None)


def _framework_facts(root: Path, files: list[Path]) -> dict:
    facts: dict[str, list[str]] = {
        "fastapi_routes": [],
        "websocket_entries": [],
        "vue_components": [],
        "pinia_stores": [],
        "database_tables": [],
        "configuration_files": [],
    }
    for path in files:
        relative = path.relative_to(root).as_posix()
        suffix = path.suffix.lower()
        text = _read_text(path, 80_000)
        if suffix == ".py":
            for match in re.finditer(r"@(?:router|app)\.(get|post|put|patch|delete)\(\s*[\"']([^\"']+)", text):
                facts["fastapi_routes"].append(f"{relative}:{match.group(1).upper()} {match.group(2)}")
            if re.search(r"WebSocket|websocket", text):
                facts["websocket_entries"].append(relative)
            for match in re.finditer(r"CREATE\s+TABLE(?:\s+IF\s+NOT\s+EXISTS)?\s+([A-Za-z_][\w]*)", text, re.I):
                facts["database_tables"].append(f"{relative}:{match.group(1)}")
        if suffix == ".vue":
            if re.search(r"<template|defineComponent", text):
                facts["vue_components"].append(relative)
            if re.search(r"defineStore\s*\(", text):
                facts["pinia_stores"].append(relative)
        if path.name.lower() in {".env", ".env.example", "config.py", "config.ts", "settings.py", "package.json", "pyproject.toml"}:
            facts["configuration_files"].append(relative)
    return {key: list(dict.fromkeys(values))[:80] for key, values in facts.items() if values}


def _read_text(path: Path, limit: int = MAX_DOC_CHARS) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")[:limit]
    except (OSError, UnicodeError):
        return ""


def _symbols_and_imports(path: Path, language: str) -> tuple[list[str], list[str]]:
    text = _read_text(path, 120_000)
    if not text:
        return [], []
    symbols: list[str] = []
    imports: list[str] = []
    symbol_patterns = {
        "python": r"^\s*(?:async\s+)?(?:def|class)\s+([A-Za-z_]\w*)",
        "javascript": r"^\s*(?:export\s+)?(?:async\s+)?(?:function|class)\s+([A-Za-z_$][\w$]*)",
        "typescript": r"^\s*(?:export\s+)?(?:async\s+)?(?:function|class|interface|type)\s+([A-Za-z_$][\w$]*)",
        "vue": r"^\s*(?:const|function|class)\s+([A-Za-z_$][\w$]*)",
        "go": r"^\s*func\s+(?:\([^)]*\)\s*)?([A-Za-z_]\w*)",
        "rust": r"^\s*(?:pub\s+)?(?:fn|struct|enum|trait)\s+([A-Za-z_]\w*)",
        "java": r"^\s*(?:public|private|protected)?\s*(?:class|interface|void|static)\s+([A-Za-z_]\w*)",
        "csharp": r"^\s*(?:public|private|internal|static)?\s*(?:class|interface|void)\s+([A-Za-z_]\w*)",
    }
    import_patterns = {
        "python": [r"^\s*import\s+([^\s]+)", r"^\s*from\s+([^\s]+)\s+import"],
        "javascript": [r"from\s+[\"']([^\"']+)", r"require\([\"']([^\"']+)[\"']\)"],
        "typescript": [r"from\s+[\"']([^\"']+)", r"require\([\"']([^\"']+)[\"']\)"],
        "vue": [r"from\s+[\"']([^\"']+)[\"']"],
        "go": [r"[\"']([^\"']+)[\"']"],
        "rust": [r"^\s*(?:use|mod)\s+([^;]+)"],
    }
    symbol_pattern = symbol_patterns.get(language)
    if symbol_pattern:
        symbols = list(dict.fromkeys(re.findall(symbol_pattern, text, re.MULTILINE)))[:MAX_SYMBOLS_PER_FILE]
    for pattern in import_patterns.get(language, []):
        imports.extend(re.findall(pattern, text, re.MULTILINE))
    return list(dict.fromkeys(imports))[:MAX_IMPORTS_PER_FILE], symbols


def _project_types(workspace: Path, files: list[Path]) -> list[str]:
    types = []
    names = {path.name for path in files}
    for marker, project_type in PROJECT_MARKERS.items():
        if marker.startswith("*."):
            found = any(path.name.endswith(marker[1:]) for path in files)
        else:
            found = marker in names
        if found and project_type not in types:
            types.append(project_type)
    for language in dict.fromkeys(
        SOURCE_EXTENSIONS.get(path.suffix.lower())
        for path in files
        if path.suffix.lower() in SOURCE_EXTENSIONS
    ):
        if language and language not in types:
            types.append(language)
    return types or ["unknown"]


def _package_scripts(package: Path) -> dict:
    try:
        data = json.loads(_read_text(package, 100_000))
        items = list((data.get("scripts") or {}).items())[:30]
        return {str(key): str(value) for key, value in items}
    except (json.JSONDecodeError, TypeError):
        return {}


def _script_index(workspace: Path, files: list[Path]) -> tuple[dict, list[dict], str | None]:
    """Collect scripts from the workspace root and nested project packages.

    A tool workspace can contain several projects. Keep the historical
    scripts mapping for the primary package, while exposing every package
    source so the model can choose the right project explicitly.
    """
    package_paths: list[Path] = []
    root_package = workspace / "package.json"
    if root_package.is_file():
        package_paths.append(root_package)
    package_paths.extend(
        path for path in sorted(files, key=lambda item: str(item).lower())
        if path.name.lower() == "package.json" and path not in package_paths
    )

    sources = []
    for package in package_paths:
        scripts = _package_scripts(package)
        if not scripts:
            continue
        sources.append({
            "path": package.relative_to(workspace).as_posix(),
            "scripts": scripts,
        })
    if not sources:
        return {}, [], None

    primary = next(
        (source for source in sources if source["path"] == "package.json"),
        None,
    )
    if primary is None:
        primary = sorted(
            sources,
            key=lambda source: (-len(source["scripts"]), source["path"]),
        )[0]
    return dict(primary["scripts"]), sources, primary["path"]


def build_project_map(workspace, *, refresh: bool = False) -> dict:
    root = _workspace(workspace)
    key = str(root).lower()
    now = time.monotonic()
    fingerprint_state = _fingerprint_cache.get(key)
    cached = _cache.get(key)
    if (
        not refresh
        and cached
        and fingerprint_state
        and not fingerprint_state.get("stale")
        and now - float(fingerprint_state.get("checked_at") or 0) < FINGERPRINT_CACHE_TTL_SECONDS
    ):
        return cached
    fingerprint, fingerprint_count, fingerprint_truncated = _fingerprint_files(root)
    _fingerprint_cache[key] = {
        "checked_at": now,
        "fingerprint": fingerprint,
        "stale": False,
    }
    if not refresh and cached:
        if cached.get("source_revision") == fingerprint:
            return cached
    files = list(_iter_files(root))
    relative_files = sorted(path.relative_to(root).as_posix() for path in files)
    all_files = set(relative_files)
    modules = []
    for path in files:
        language = SOURCE_EXTENSIONS.get(path.suffix.lower())
        if not language or len(modules) >= MAX_MODULES:
            continue
        imports, symbols = _symbols_and_imports(path, language)
        module = {
            "path": path.relative_to(root).as_posix(),
            "language": language,
            "symbols": symbols,
            "imports": imports,
            "resolved_imports": [],
        }
        for spec in imports:
            resolved = (
                _resolve_python_import(spec, all_files)
                if language == "python"
                else _resolve_relative_import(module["path"], spec, all_files)
            )
            if resolved and resolved not in module["resolved_imports"]:
                module["resolved_imports"].append(resolved)
        modules.append(module)
    top_level = _top_level_entries(root, relative_files)
    docs = {}
    seen_doc_contents = set()
    for name in ("AGENTS.md", "README.md", "README.MD", "ARCHITECTURE.md", "docs/architecture.md"):
        path = root / name
        if path.exists():
            content = _read_text(path)
            digest = hashlib.sha256(content.encode("utf-8", "replace")).hexdigest()
            if digest in seen_doc_contents:
                continue
            seen_doc_contents.add(digest)
            docs[name] = {
                "outline": _doc_outline(content),
                "content_available": True,
            }
    entrypoints = [item for item in relative_files if Path(item).name in ENTRYPOINT_NAMES][:40]
    scripts, script_sources, primary_script_source = _script_index(root, files)
    result = {
        "version": INDEX_VERSION,
        "index_version": INDEX_VERSION,
        "workspace": str(root),
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "source_revision": fingerprint,
        "source_revision_files": fingerprint_count,
        "source_revision_truncated": fingerprint_truncated,
        "scanned_paths": relative_files[:MAX_FILES],
        "ignored_paths": sorted(IGNORED_DIRS),
        "file_count": len(relative_files),
        "truncated": len(files) >= MAX_FILES,
        "project_types": _project_types(root, files),
        "top_level": top_level,
        "entrypoints": entrypoints,
        "scripts": scripts,
        "script_sources": script_sources,
        "primary_script_source": primary_script_source,
        "architecture_docs": docs,
        "framework_facts": _framework_facts(root, files),
        "modules": modules,
    }
    _cache[key] = result
    try:
        target = _cache_path(root)
        target.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass
    return result


def architecture_summary(workspace, max_chars: int = 2200) -> str:
    data = build_project_map(workspace)
    lines = [
        f"工作区：{data['workspace']}",
        (
            f"索引 v{data['index_version']}，生成于：{data['generated_at']}；"
            f"源指纹：{data['source_revision']}；"
            f"项目类型：{', '.join(data['project_types'])}；"
            f"文件数：{data['file_count']}"
            f"{'（扫描或源指纹已截断）' if data['truncated'] or data.get('source_revision_truncated') else ''}"
        ),
    ]
    if data["entrypoints"]:
        lines.append("入口：" + ", ".join(data["entrypoints"][:12]))
    if data["top_level"]:
        lines.append("顶层结构：" + ", ".join(data["top_level"][:24]))
    if data["scripts"]:
        lines.append("脚本：" + ", ".join(f"{key}={value}" for key, value in list(data["scripts"].items())[:8]))
    module_lines = []
    if data.get("framework_facts"):
        facts = data["framework_facts"]
        if facts.get("fastapi_routes"):
            lines.append("FastAPI 路由：" + "; ".join(facts["fastapi_routes"][:8]))
        if facts.get("websocket_entries"):
            lines.append("WebSocket 入口：" + ", ".join(facts["websocket_entries"][:8]))
        if facts.get("vue_components"):
            lines.append("Vue 组件：" + ", ".join(facts["vue_components"][:8]))
    for module in data["modules"]:
        if module["symbols"]:
            resolved = f" -> {', '.join(module.get('resolved_imports', [])[:4])}" if module.get('resolved_imports') else ""
            module_lines.append(f"- {module['path']}：{', '.join(module['symbols'][:8])}{resolved}")
    if module_lines:
        lines.append("核心模块与符号：\n" + "\n".join(module_lines[:12]))
    lines.append("索引仅用于导航，修改前必须读取实际文件；详细架构、符号和依赖可调用 project_map 查询。")
    return "\n".join(lines)[:max_chars]


def search_project_map(workspace, query: str, limit: int = 20) -> list[dict]:
    data = build_project_map(workspace)
    needle = str(query or "").strip().lower()
    if not needle:
        return data["modules"][:limit]
    results = []
    for module in data["modules"]:
        haystack = " ".join([module["path"], module["language"], *module["symbols"], *module["imports"]]).lower()
        if needle in haystack:
            results.append(module)
    for name, content in data["architecture_docs"].items():
        outline = content.get("outline", "") if isinstance(content, dict) else str(content)
        if needle in outline.lower():
            results.append({"path": name, "language": "documentation", "symbols": [], "imports": []})
    return results[:max(1, min(int(limit or 20), 50))]


def clear_project_map_cache(workspace=None) -> None:
    if workspace is None:
        _cache.clear()
        _fingerprint_cache.clear()
        return
    key = str(_workspace(workspace)).lower()
    _cache.pop(key, None)
    _fingerprint_cache.pop(key, None)


def mark_project_map_stale(workspace) -> None:
    """Invalidate the in-process map after a known workspace mutation."""
    try:
        key = str(_workspace(workspace)).lower()
    except (OSError, TypeError, ValueError):
        return
    state = _fingerprint_cache.setdefault(key, {})
    state["stale"] = True
