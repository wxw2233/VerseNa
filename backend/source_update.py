import asyncio
import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

from config import settings


class SourceUpdateError(RuntimeError):
    def __init__(self, message: str, status_code: int = 500):
        super().__init__(message)
        self.status_code = status_code


class SourceUpdateBusy(SourceUpdateError):
    def __init__(self):
        super().__init__("Another source update operation is already running", 409)


class SourceUpdater:
    def __init__(self, project_root: Path | None = None):
        self.project_root = Path(project_root or settings.BASE_DIR.parent).resolve()
        self.frontend_dir = self.project_root / "frontend"
        self.update_dir = self.project_root / ".versena-update"
        self.pending_file = self.update_dir / "pending"
        self._lock = asyncio.Lock()

    @property
    def busy(self) -> bool:
        return self._lock.locked()

    async def status(self) -> dict:
        result = await asyncio.to_thread(self._status_sync)
        result["busy"] = self.busy
        return result

    async def check(self) -> dict:
        if self.busy:
            raise SourceUpdateBusy()
        async with self._lock:
            result = await asyncio.to_thread(self._check_sync)
        result["busy"] = False
        return result

    async def apply(self) -> dict:
        if self.busy:
            raise SourceUpdateBusy()
        async with self._lock:
            result = await asyncio.to_thread(self._apply_sync)
        result["busy"] = False
        return result

    def _status_sync(self) -> dict:
        base = {
            "supported": False,
            "version": settings.VERSION,
            "branch": "",
            "commit": "",
            "commit_short": "",
            "upstream": "",
            "dirty": False,
            "ahead": 0,
            "behind": 0,
            "update_available": False,
            "pending": self.pending_file.is_file(),
            "restart_required": self.pending_file.is_file(),
            "message": "",
        }
        if not (self.project_root / ".git").exists():
            base["message"] = "Source updates are only available in a Git checkout"
            return base
        if not shutil.which("git"):
            base["message"] = "Git is not installed or is not available on PATH"
            return base

        branch = self._try_git(["symbolic-ref", "--quiet", "--short", "HEAD"])
        if not branch:
            base["message"] = "Source updates require a checked-out branch"
            return base
        upstream = self._try_git(
            ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"]
        )
        if not upstream:
            base.update({"branch": branch})
            base["message"] = "The current branch has no upstream tracking branch"
            return base

        commit = self._git(["rev-parse", "HEAD"])
        dirty = bool(self._git(["status", "--porcelain", "--untracked-files=no"]))
        ahead, behind = self._commit_counts(upstream)
        base.update(
            {
                "supported": True,
                "branch": branch,
                "commit": commit,
                "commit_short": commit[:7],
                "upstream": upstream,
                "dirty": dirty,
                "ahead": ahead,
                "behind": behind,
                "update_available": behind > 0 and ahead == 0,
            }
        )
        if dirty:
            base["message"] = "The source tree has uncommitted tracked changes"
        elif ahead and behind:
            base["message"] = "The local and upstream branches have diverged"
        elif behind:
            base["message"] = f"{behind} upstream commit(s) are available"
        elif ahead:
            base["message"] = f"The local branch is {ahead} commit(s) ahead"
        elif base["pending"]:
            base["message"] = "The previous update needs to finish building"
        else:
            base["message"] = "The source checkout is up to date"
        return base

    def _check_sync(self) -> dict:
        status = self._status_sync()
        if not status["supported"]:
            return status
        try:
            self._git(["fetch", "--quiet", "--prune"], timeout=180)
        except SourceUpdateError as exc:
            raise SourceUpdateError(f"Unable to fetch source updates: {exc}", 502) from exc
        return self._status_sync()

    def _apply_sync(self) -> dict:
        status = self._check_sync()
        if not status["supported"]:
            raise SourceUpdateError(status["message"], 409)
        if status["dirty"]:
            raise SourceUpdateError(
                "Commit or discard tracked source changes before updating", 409
            )
        if status["ahead"]:
            raise SourceUpdateError(
                "The local branch contains commits that are not on the upstream branch", 409
            )

        had_pending_update = self.pending_file.is_file()
        if status["behind"] == 0 and not had_pending_update:
            return {**status, "applied": False, "steps": []}

        npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
        if not npm:
            raise SourceUpdateError(
                "Node.js and npm are required to rebuild the source frontend", 409
            )

        requirements = self._requirements_file()
        package_lock = self.frontend_dir / "package-lock.json"
        old_requirements_hash = self._file_hash(requirements)
        old_package_lock_hash = self._file_hash(package_lock)
        steps = []

        self.update_dir.mkdir(parents=True, exist_ok=True)
        self.pending_file.write_text(status["commit"] + "\n", encoding="utf-8")

        if status["behind"]:
            self._git(["merge", "--ff-only", status["upstream"]], timeout=180)
            steps.append("source")

        requirements_changed = old_requirements_hash != self._file_hash(requirements)
        package_lock_changed = old_package_lock_hash != self._file_hash(package_lock)

        if had_pending_update or requirements_changed:
            self._run(
                [sys.executable, "-m", "pip", "install", "-r", str(requirements)],
                cwd=self.project_root,
                timeout=900,
            )
            steps.append("python_dependencies")

        if had_pending_update or package_lock_changed or not (self.frontend_dir / "node_modules").is_dir():
            self._run([npm, "ci"], cwd=self.frontend_dir, timeout=900)
            steps.append("frontend_dependencies")

        self._build_frontend(npm)
        steps.append("frontend")
        shutil.rmtree(self.update_dir, ignore_errors=True)

        result = self._status_sync()
        result.update(
            {
                "applied": True,
                "steps": steps,
                "restart_required": True,
                "message": "Source update completed; restart VerseNa to load backend changes",
            }
        )
        return result

    def _build_frontend(self, npm: str) -> None:
        build_output = self.update_dir / "frontend-dist"
        previous_output = self.update_dir / "previous-dist"
        shutil.rmtree(build_output, ignore_errors=True)
        shutil.rmtree(previous_output, ignore_errors=True)
        self._run(
            [
                npm,
                "run",
                "build",
                "--",
                "--outDir",
                str(build_output),
                "--emptyOutDir",
            ],
            cwd=self.frontend_dir,
            timeout=900,
        )
        if not (build_output / "index.html").is_file():
            raise SourceUpdateError("The updated frontend build did not produce index.html")

        current_output = self.frontend_dir / "dist"
        if current_output.exists():
            current_output.rename(previous_output)
        try:
            build_output.rename(current_output)
        except Exception:
            if previous_output.exists() and not current_output.exists():
                previous_output.rename(current_output)
            raise
        shutil.rmtree(previous_output, ignore_errors=True)

    def _requirements_file(self) -> Path:
        is_termux = bool(os.environ.get("TERMUX_VERSION")) or "com.termux" in sys.prefix
        filename = "requirements-termux.txt" if is_termux else "requirements-runtime.txt"
        path = self.project_root / "backend" / filename
        if not path.is_file():
            raise SourceUpdateError(f"Missing dependency file: {path}", 409)
        return path

    def _commit_counts(self, upstream: str) -> tuple[int, int]:
        output = self._try_git(["rev-list", "--left-right", "--count", f"HEAD...{upstream}"])
        if not output:
            return 0, 0
        left, right = output.split()
        return int(left), int(right)

    @staticmethod
    def _file_hash(path: Path) -> str:
        if not path.is_file():
            return ""
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def _try_git(self, args: list[str]) -> str:
        try:
            return self._git(args)
        except SourceUpdateError:
            return ""

    def _git(self, args: list[str], timeout: int = 30) -> str:
        return self._run(["git", *args], cwd=self.project_root, timeout=timeout)

    @staticmethod
    def _run(args: list[str], cwd: Path, timeout: int) -> str:
        try:
            completed = subprocess.run(
                args,
                cwd=str(cwd),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise SourceUpdateError(str(exc)) from exc
        output = "\n".join(part.strip() for part in (completed.stdout, completed.stderr) if part.strip())
        if completed.returncode != 0:
            detail = "\n".join(output.splitlines()[-12:])
            raise SourceUpdateError(detail or f"Command failed with exit code {completed.returncode}")
        return completed.stdout.strip()


source_updater = SourceUpdater()
