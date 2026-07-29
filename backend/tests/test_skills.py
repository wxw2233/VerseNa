import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from skills.manager import SkillManager


@pytest.fixture
def manager(tmp_path):
    return SkillManager(
        installed_dir=tmp_path / "installed",
        custom_dir=tmp_path / "custom",
    )


def write_skill(directory: Path, **overrides):
    directory.mkdir(parents=True, exist_ok=True)
    data = {
        "id": "sample-skill",
        "name": "Sample Skill",
        "description": "A test skill",
        "system_prompt": "Follow the complete sample instructions.",
        "knowledge": {"GUIDE.md": "knowledge-body-" + "x" * 600},
        **overrides,
    }
    (directory / "skill.json").write_text(json.dumps(data), encoding="utf-8")
    return data


def test_builtin_skills_are_discoverable(manager):
    diagnostics = manager.diagnostics()

    assert diagnostics["status"] == "ok"
    assert diagnostics["counts"]["builtin"] == 5
    assert "load_skill(skill_id)" in manager.get_skill_prompt()
    assert "`translator`" in manager.get_skill_prompt()


def test_custom_skill_loads_full_context(tmp_path):
    custom_dir = tmp_path / "custom"
    write_skill(custom_dir / "directory-name", id="custom-id")
    manager = SkillManager(tmp_path / "installed", custom_dir)

    skill = manager.get_skill("custom-id")
    context = manager.get_skill_context("custom-id")

    assert skill["source"] == "custom"
    assert "Follow the complete sample instructions." in context
    assert "knowledge-body-" in context
    assert len(context) > 600


def test_invalid_and_conflicting_skills_are_reported(tmp_path):
    custom_dir = tmp_path / "custom"
    write_skill(custom_dir / "invalid", id="../invalid")
    write_skill(custom_dir / "conflict", id="translator")
    manager = SkillManager(tmp_path / "installed", custom_dir)

    diagnostics = manager.diagnostics()

    assert diagnostics["status"] == "degraded"
    assert len(diagnostics["load_errors"]) == 2
    assert manager.get_skill("translator")["source"] == "builtin"


def test_install_and_delete_use_real_directory_for_custom_id(manager, monkeypatch):
    def fake_clone(command, **kwargs):
        destination = Path(command[-1])
        write_skill(destination, id="custom-id", name="Installed Skill")
        (destination / ".git").mkdir()
        return SimpleNamespace(returncode=0, stderr="")

    monkeypatch.setattr("skills.manager.subprocess.run", fake_clone)

    skill, error = manager.install_from_github("https://github.com/example/repository.git")

    assert error is None
    assert skill["id"] == "custom-id"
    assert (manager.installed_dir / "repository").exists()

    manager.delete_skill("custom-id")

    assert manager.get_skill("custom-id") is None
    assert not (manager.installed_dir / "repository").exists()


def test_failed_update_preserves_existing_skill(manager, monkeypatch):
    existing_dir = manager.installed_dir / "repository"
    write_skill(existing_dir, id="existing-id", name="Existing Skill")
    manager.reload()

    def clone_conflicting_skill(command, **kwargs):
        destination = Path(command[-1])
        write_skill(destination, id="translator", name="Conflict")
        return SimpleNamespace(returncode=0, stderr="")

    monkeypatch.setattr("skills.manager.subprocess.run", clone_conflicting_skill)

    skill, error = manager.install_from_github("https://github.com/example/repository")

    assert skill is None
    assert "内置技能冲突" in error
    assert existing_dir.exists()
    assert manager.get_skill("existing-id")["name"] == "Existing Skill"


@pytest.mark.parametrize(
    "url",
    [
        "http://github.com/owner/repo",
        "https://example.com/owner/repo",
        "file:///tmp/repo",
        "https://github.com/owner",
        "https://github.com/owner/repo/extra",
    ],
)
def test_install_rejects_non_github_repository_urls(manager, url):
    skill, error = manager.install_from_github(url)

    assert skill is None
    assert "仅支持" in error


@pytest.mark.asyncio
async def test_load_skill_tool_returns_full_context(manager, monkeypatch):
    write_skill(manager.custom_dir / "tool-directory", id="tool-skill")
    manager.reload()

    from tools.builtin import load_skill as load_skill_module

    monkeypatch.setattr(load_skill_module, "skill_manager", manager)
    result = json.loads(await load_skill_module.LoadSkillTool().execute("tool-skill"))

    assert result["success"] is True
    assert result["skill_id"] == "tool-skill"
    assert "knowledge-body-" in result["context"]
