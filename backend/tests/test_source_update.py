import os
import shutil
import subprocess

import pytest

from source_update import SourceUpdateError, SourceUpdater


def run_git(cwd, *args):
    completed = subprocess.run(
        ["git", "-c", "user.name=VerseNa Test", "-c", "user.email=test@example.com", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    return completed.stdout.strip()


@pytest.mark.asyncio
async def test_source_update_is_disabled_outside_git_checkout(tmp_path):
    updater = SourceUpdater(tmp_path)

    status = await updater.status()

    assert status["supported"] is False
    assert "Git checkout" in status["message"]


@pytest.mark.asyncio
async def test_source_update_reports_upstream_commits(tmp_path, monkeypatch):
    tmp_path.joinpath(".git").mkdir()
    updater = SourceUpdater(tmp_path)
    commit = "1234567890abcdef1234567890abcdef12345678"

    def fake_git(args, timeout=30):
        command = tuple(args)
        if command[:4] == ("symbolic-ref", "--quiet", "--short", "HEAD"):
            return "master"
        if command[0] == "rev-parse" and "@{upstream}" in command:
            return "origin/master"
        if command == ("rev-parse", "HEAD"):
            return commit
        if command[0] == "status":
            return ""
        if command[0] == "rev-list":
            return "0 3"
        raise AssertionError(f"Unexpected git command: {args}")

    monkeypatch.setattr("source_update.shutil.which", lambda name: "/usr/bin/git")
    monkeypatch.setattr(updater, "_git", fake_git)

    status = await updater.status()

    assert status["supported"] is True
    assert status["branch"] == "master"
    assert status["upstream"] == "origin/master"
    assert status["commit_short"] == "1234567"
    assert status["behind"] == 3
    assert status["update_available"] is True


@pytest.mark.asyncio
async def test_source_update_rejects_dirty_checkout(tmp_path, monkeypatch):
    updater = SourceUpdater(tmp_path)
    monkeypatch.setattr(
        updater,
        "_check_sync",
        lambda: {
            "supported": True,
            "dirty": True,
            "ahead": 0,
            "behind": 1,
            "pending": False,
            "message": "dirty",
        },
    )

    with pytest.raises(SourceUpdateError, match="tracked source changes") as raised:
        await updater.apply()

    assert raised.value.status_code == 409


@pytest.mark.asyncio
async def test_source_update_fast_forwards_from_local_remote(tmp_path, monkeypatch):
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    run_git(checkout, "init")
    run_git(checkout, "checkout", "-B", "master")

    checkout.joinpath("backend").mkdir()
    checkout.joinpath("backend", "requirements-runtime.txt").write_text("", encoding="utf-8")
    checkout.joinpath("frontend").mkdir()
    checkout.joinpath("frontend", "package-lock.json").write_text("{}\n", encoding="utf-8")
    checkout.joinpath("README.md").write_text("first\n", encoding="utf-8")
    run_git(checkout, "add", ".")
    run_git(checkout, "commit", "-m", "initial")
    initial_commit = run_git(checkout, "rev-parse", "HEAD")

    checkout.joinpath("README.md").write_text("second\n", encoding="utf-8")
    run_git(checkout, "add", "README.md")
    run_git(checkout, "commit", "-m", "update")
    upstream_commit = run_git(checkout, "rev-parse", "HEAD")
    run_git(checkout, "remote", "add", "origin", ".")
    run_git(checkout, "update-ref", "refs/remotes/origin/master", upstream_commit)
    run_git(checkout, "reset", "--hard", initial_commit)
    run_git(checkout, "branch", "--set-upstream-to=origin/master", "master")

    checkout.joinpath("frontend", "node_modules").mkdir()
    updater = SourceUpdater(checkout)
    real_git = shutil.which("git")

    def fake_which(name):
        if name == "git":
            return real_git
        if name == ("npm.cmd" if os.name == "nt" else "npm"):
            return "npm"
        return None

    monkeypatch.setattr("source_update.shutil.which", fake_which)
    monkeypatch.setattr(updater, "_check_sync", updater._status_sync)
    monkeypatch.setattr(updater, "_build_frontend", lambda npm: None)

    result = await updater.apply()

    assert result["applied"] is True
    assert result["behind"] == 0
    assert result["restart_required"] is True
    assert checkout.joinpath("README.md").read_text(encoding="utf-8") == "second\n"
