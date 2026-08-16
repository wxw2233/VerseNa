import os
from dataclasses import dataclass
from pathlib import Path

from tools.base import ToolContext


SENSITIVE_NAMES = {
    "access_token",
    ".git-credentials",
    ".netrc",
    ".npmrc",
    ".pypirc",
    "credentials",
    "credentials.json",
    "cookies",
    "login data",
    "local state",
    "web data",
    "wallet.dat",
    "id_rsa",
    "id_ed25519",
}

SENSITIVE_DIRECTORIES = {
    ".aws",
    ".azure",
    ".docker",
    ".gnupg",
    ".kube",
    ".ssh",
    "gcloud",
}

SENSITIVE_SUFFIXES = (
    ".db",
    ".kdbx",
    ".key",
    ".p12",
    ".pem",
    ".pfx",
    ".sqlite",
    ".sqlite3",
)


class ToolPathError(ValueError):
    pass


@dataclass(frozen=True)
class ToolPath:
    op_path: Path
    check_path: Path


def resolve_tool_path(context: ToolContext, value: str, *, default: str = ".") -> ToolPath:
    root = context.workspace.expanduser().resolve()
    raw = Path(value or default).expanduser()
    op_path = raw if raw.is_absolute() else root / raw
    op_path = Path(os.path.abspath(op_path))
    check_path = op_path.resolve(strict=False)

    root_norm = os.path.normcase(str(root))
    check_norm = os.path.normcase(str(check_path))
    try:
        inside = os.path.commonpath([root_norm, check_norm]) == root_norm
    except ValueError:
        inside = False
    if not inside:
        raise ToolPathError(f"路径超出工具工作区: {value}")
    if is_sensitive_path(check_path, root):
        raise ToolPathError(f"禁止访问敏感文件: {value}")
    return ToolPath(op_path=op_path, check_path=check_path)


def is_sensitive_path(path: Path, root: Path) -> bool:
    try:
        parts = path.relative_to(root).parts
    except ValueError:
        return True
    for part in parts:
        lowered = part.lower()
        if lowered.startswith(".env") or lowered in SENSITIVE_NAMES:
            return True
        if lowered.endswith(SENSITIVE_SUFFIXES):
            return True
        if lowered in SENSITIVE_DIRECTORIES:
            return True
    return False
