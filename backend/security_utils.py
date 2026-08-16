import re
import threading
from typing import Any


REDACTED = "[REDACTED]"
_known_secrets: set[str] = set()
_secret_lock = threading.RLock()

_PRIVATE_KEY_PATTERN = re.compile(
    r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----.*?"
    r"-----END (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----",
    re.IGNORECASE | re.DOTALL,
)
_PREFIXED_SECRET_PATTERN = re.compile(
    r"(?<![A-Za-z0-9])(?:"
    r"(?:sk|tp)-[A-Za-z0-9._-]{8,}"
    r"|(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{8,}"
    r")",
    re.IGNORECASE,
)
_BEARER_PATTERN = re.compile(
    r"(?i)(\bBearer\s+)[A-Za-z0-9._~+/-]{8,}={0,2}"
)
_KEY_VALUE_PATTERN = re.compile(
    r"""(?ix)
    (
      ["']?
      (?:[A-Z0-9_]*(?:API_KEY|ACCESS_TOKEN|APP_SECRET|PASSWORD|CREDENTIAL)
        |api[-_]?key|access[-_]?token|app[-_]?secret|password|credential|authorization)
      ["']?\s*[:=]\s*["']?
    )
    ([^\s"',;}&]{6,})
    """
)


def register_secret(value: Any) -> None:
    text = str(value or "").strip()
    if len(text) < 6 or text in {"true", "false", "null", "none"}:
        return
    with _secret_lock:
        _known_secrets.add(text)


def register_secret_tree(value: Any) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            lowered = str(key).lower()
            if any(part in lowered for part in ("key", "token", "secret", "password", "credential")):
                register_secret(item)
            else:
                register_secret_tree(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            register_secret_tree(item)


def redact_sensitive_text(value: Any) -> str:
    text = str(value if value is not None else "")
    with _secret_lock:
        known = sorted(_known_secrets, key=len, reverse=True)
    for secret in known:
        text = text.replace(secret, REDACTED)
    text = _PRIVATE_KEY_PATTERN.sub(REDACTED, text)
    text = _PREFIXED_SECRET_PATTERN.sub(REDACTED, text)
    text = _BEARER_PATTERN.sub(r"\1" + REDACTED, text)
    text = _KEY_VALUE_PATTERN.sub(r"\1" + REDACTED, text)
    return text


def redact_sensitive_data(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: redact_sensitive_data(item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact_sensitive_data(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_sensitive_data(item) for item in value)
    if isinstance(value, str):
        return redact_sensitive_text(value)
    return value
