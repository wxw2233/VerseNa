import json

import pytest

from agent.project_map import architecture_summary, build_project_map, search_project_map
from tools.base import ToolContext
from tools.builtin.project_map import ProjectMapTool
from tools.builtin.file_manager import FileManagerTool


def test_project_map_discovers_entrypoints_symbols_and_scripts(tmp_path, monkeypatch):
    from config import settings

    monkeypatch.setattr(settings, "DATA_DIR", tmp_path / "data")
    (tmp_path / "package.json").write_text(
        '{"scripts":{"test":"vitest","build":"vite build"}}', encoding="utf-8"
    )
    (tmp_path / "main.py").write_text(
        "from app.service import run\n\nclass Runner:\n    pass\n\ndef start():\n    return run()\n",
        encoding="utf-8",
    )
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "service.py").write_text(
        "def run():\n    return True\n", encoding="utf-8"
    )

    data = build_project_map(tmp_path, refresh=True)
    modules = {item["path"]: item for item in data["modules"]}

    assert "python" in data["project_types"]
    assert "node" in data["project_types"]
    assert "main.py" in data["entrypoints"]
    assert data["scripts"]["test"] == "vitest"
    assert "Runner" in modules["main.py"]["symbols"]
    assert "app.service" in modules["main.py"]["imports"]
    assert search_project_map(tmp_path, "Runner")[0]["path"] == "main.py"
    assert "main.py" in architecture_summary(tmp_path)


def test_project_map_discovers_scripts_from_nested_project(tmp_path, monkeypatch):
    from config import settings

    monkeypatch.setattr(settings, "DATA_DIR", tmp_path / "data")
    project = tmp_path / "phys-tower"
    project.mkdir()
    (project / "package.json").write_text(
        '{"scripts":{"dev":"vite","test":"vitest run"}}', encoding="utf-8"
    )
    (project / "vite.config.ts").write_text(
        "export default {}", encoding="utf-8"
    )

    data = build_project_map(tmp_path, refresh=True)

    assert data["scripts"] == {"dev": "vite", "test": "vitest run"}
    assert data["primary_script_source"] == "phys-tower/package.json"
    assert data["script_sources"] == [{
        "path": "phys-tower/package.json",
        "scripts": {"dev": "vite", "test": "vitest run"},
    }]


def test_project_map_cache_can_be_invalidated_after_known_mutation(tmp_path, monkeypatch):
    from agent import project_map
    from config import settings

    monkeypatch.setattr(settings, "DATA_DIR", tmp_path / "data")
    source = tmp_path / "main.py"
    source.write_text("def first():\n    return 1\n", encoding="utf-8")
    project_map.clear_project_map_cache(tmp_path)
    first = project_map.build_project_map(tmp_path, refresh=True)

    source.write_text("def second():\n    return 2\n", encoding="utf-8")
    project_map.mark_project_map_stale(tmp_path)
    second = project_map.build_project_map(tmp_path)
    symbols = {symbol for module in second["modules"] for symbol in module["symbols"]}

    assert first["source_revision"] != second["source_revision"]
    assert "second" in symbols
    assert "first" not in symbols


def test_project_map_excludes_sensitive_paths_from_index_and_search(tmp_path, monkeypatch):
    from config import settings

    monkeypatch.setattr(settings, "DATA_DIR", tmp_path / "data")
    (tmp_path / "main.py").write_text("def safe_entry():\n    return True\n", encoding="utf-8")
    (tmp_path / ".env").write_text("API_KEY=private-value", encoding="utf-8")
    (tmp_path / "private.key").write_text("private-key-material", encoding="utf-8")
    ssh_dir = tmp_path / ".ssh"
    ssh_dir.mkdir()
    (ssh_dir / "id_ed25519").write_text("private-ssh-key", encoding="utf-8")

    data = build_project_map(tmp_path, refresh=True)

    assert data["scanned_paths"] == ["main.py"]
    assert ".env" not in data["top_level"]
    assert "private.key" not in data["top_level"]
    assert ".ssh" not in data["top_level"]
    assert search_project_map(tmp_path, "private") == []


@pytest.mark.asyncio
async def test_project_map_tool_stays_inside_context_workspace(tmp_path, monkeypatch):
    from config import settings

    monkeypatch.setattr(settings, "DATA_DIR", tmp_path / "data")
    (tmp_path / "index.ts").write_text("export function boot() {}", encoding="utf-8")
    context = ToolContext("project-map", tmp_path)
    tool = ProjectMapTool()

    result = json.loads(await tool.execute(action="search", query="boot", _context=context))
    assert result["success"] is True
    assert result["data"]["results"][0]["path"] == "index.ts"

    outside = tmp_path.parent / "outside-project-map-secret.txt"
    outside.write_text("do not scan", encoding="utf-8")
    try:
        result = json.loads(await tool.execute(
            action="search", query="outside-project-map-secret", _context=context
        ))
        assert result["data"]["results"] == []
    finally:
        outside.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_project_map_inspect_is_paged_and_keeps_index_provenance(tmp_path, monkeypatch):
    from config import settings

    monkeypatch.setattr(settings, "DATA_DIR", tmp_path / "data")
    for index in range(4):
        (tmp_path / f"module_{index}.py").write_text(
            f"def symbol_{index}():\n    return {index}\n", encoding="utf-8"
        )
    context = ToolContext("project-map-page", tmp_path)
    result = json.loads(await ProjectMapTool().execute(
        action="inspect", offset=1, limit=2, _context=context,
    ))
    data = result["data"]

    assert result["success"] is True
    assert data["index_version"]
    assert data["source_revision"]
    assert data["module_total"] == 4
    assert data["module_offset"] == 1
    assert len(data["modules"]) == 2
    assert data["module_next_offset"] == 3


@pytest.mark.asyncio
async def test_file_manager_mkdir_invalidates_project_map_cache(tmp_path, monkeypatch):
    from agent import project_map
    from config import settings

    monkeypatch.setattr(settings, "DATA_DIR", tmp_path / "data")
    (tmp_path / "main.py").write_text("def boot():\n    return True\n", encoding="utf-8")
    project_map.clear_project_map_cache(tmp_path)
    first = project_map.build_project_map(tmp_path, refresh=True)

    context = ToolContext("project-map-mkdir", tmp_path, approval_mode="auto")
    result = json.loads(await FileManagerTool().execute(
        action="mkdir", path="generated/nested", _context=context,
    ))
    second = project_map.build_project_map(tmp_path)

    assert result["success"] is True
    assert (tmp_path / "generated" / "nested").is_dir()
    assert first["source_revision"] != second["source_revision"]
