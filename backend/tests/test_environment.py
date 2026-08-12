from pathlib import Path

from agent.environment import collect_environment_facts, format_environment_facts


def test_environment_facts_include_workspace_and_shell(tmp_path):
    facts = collect_environment_facts(Path(tmp_path))

    assert facts["workspace"] == str(tmp_path.resolve())
    assert facts["os"]
    assert facts["tool_shell"]
    assert "工具工作目录" in format_environment_facts(facts)
