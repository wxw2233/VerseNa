import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from skills.manager import SkillManager
from tools.base import ToolContext
from tools.registry import ToolRegistry


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


def write_skill_command(directory: Path, name="brainstorming", description="Explore the idea first."):
    command_dir = directory / "skills" / name
    command_dir.mkdir(parents=True, exist_ok=True)
    (command_dir / "SKILL.md").write_text(
        "\n".join([
            "---",
            f"name: {name}",
            f'description: "{description}"',
            "---",
            "",
            f"# {name}",
            "Follow this slash command exactly.",
        ]),
        encoding="utf-8",
    )
    return command_dir


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


def test_installed_skill_discovers_and_resolves_slash_commands(manager):
    skill_dir = manager.installed_dir / "command-package"
    write_skill(skill_dir, id="command-package", name="Command Package")
    write_skill_command(skill_dir)
    manager.reload()

    commands = {item["command"]: item for item in manager.list_commands()}
    resolved = manager.resolve_slash_command("/brainstorming design a notes app")
    context = manager.get_skill_context("brainstorming")

    assert commands["brainstorming"]["skill_id"] == "command-package"
    assert commands["brainstorming"]["aliases"] == ["command-package:brainstorming"]
    assert resolved["arguments"] == "design a notes app"
    assert "Follow this slash command exactly." in context
    assert "`/brainstorming`" in manager.get_skill_prompt()


def test_explicit_skill_command_metadata_is_supported(manager):
    write_skill(
        manager.custom_dir / "explicit-package",
        id="explicit-package",
        commands=[{
            "name": "review",
            "description": "Review the supplied work.",
            "prompt": "Inspect the work before answering.",
        }],
    )
    manager.reload()

    assert manager.resolve_slash_command("/review")['skill_id'] == "explicit-package"
    assert "Inspect the work before answering." in manager.get_command_context("review")


def test_chat_slash_command_prompt_loads_command_context(manager):
    skill_dir = manager.installed_dir / "chat-command-package"
    write_skill(skill_dir, id="chat-command-package", name="Chat Command Package")
    write_skill_command(skill_dir, name="plan", description="Plan before implementation.")
    manager.reload()

    from api.chat import _skill_command_system_prompt

    prompt = _skill_command_system_prompt("/plan build a calendar", manager)

    assert "`/plan`" in prompt
    assert "build a calendar" in prompt
    assert "Follow this slash command exactly." in prompt


def test_chat_slash_command_prompt_keeps_active_command_across_turns(manager):
    skill_dir = manager.installed_dir / "persistent-command-package"
    write_skill(skill_dir, id="persistent-command-package", name="Persistent Package")
    write_skill_command(skill_dir, name="brainstorming")
    manager.reload()

    from api.chat import _skill_command_system_prompt

    prompt = _skill_command_system_prompt(
        "ok，继续",
        manager,
        active_command="brainstorming",
        active_arguments="设计函数图像工具",
    )

    assert "当前会话持续启用 `/brainstorming`" in prompt
    assert "设计函数图像工具" in prompt
    assert "不要怀疑或讨论它是否已加载" in prompt
    assert "Follow this slash command exactly." in prompt


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


@pytest.mark.asyncio
async def test_load_skill_tool_runs_through_registry(manager, monkeypatch):
    write_skill(manager.custom_dir / "registry-tool-directory", id="registry-tool-skill")
    manager.reload()

    from tools.builtin import load_skill as load_skill_module

    monkeypatch.setattr(load_skill_module, "skill_manager", manager)
    registry = ToolRegistry()
    registry.load_builtins()
    context = ToolContext("skill-test", manager.custom_dir.parent)

    result = json.loads(await registry.execute(
        "load_skill",
        {"skill_id": "registry-tool-skill"},
        context=context,
    ))

    assert result["success"] is True
    assert result["skill_id"] == "registry-tool-skill"
    assert "knowledge-body-" in result["context"]


@pytest.mark.asyncio
async def test_load_skill_tool_switches_session_active_command(manager, monkeypatch):
    write_skill(manager.custom_dir / "next-step", id="writing-plans")
    manager.reload()

    saved = {}

    class FakeDatabase:
        async def set_session_meta(self, session_id, **updates):
            saved["session_id"] = session_id
            saved.update(updates)

    from tools.builtin import load_skill as load_skill_module

    monkeypatch.setattr(load_skill_module, "skill_manager", manager)
    monkeypatch.setattr(load_skill_module, "db", FakeDatabase())
    context = ToolContext("workflow-session", manager.custom_dir.parent)

    result = json.loads(await load_skill_module.LoadSkillTool().execute(
        "writing-plans",
        _context=context,
    ))

    assert result["success"] is True
    assert result["active_command"] == "writing-plans"
    assert saved == {
        "session_id": "workflow-session",
        "active_skill_command": "writing-plans",
        "active_skill_arguments": "",
    }
