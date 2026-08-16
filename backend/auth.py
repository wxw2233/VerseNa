import hmac
import ipaddress
import os
import secrets
import time
from collections import defaultdict, deque
from pathlib import Path
from urllib.parse import urlsplit
from dotenv import dotenv_values, unset_key

from config import settings
from secret_store import SecretStoreError, secret_protector
from security_utils import register_secret


SESSION_COOKIE_NAME = "versena_session"
MIN_ACCESS_TOKEN_LENGTH = 6
LOGIN_WINDOW_SECONDS = 60
MAX_LOGIN_ATTEMPTS = 5


def is_loopback_host(host: str) -> bool:
    normalized = (host or "").strip().strip("[]").lower()
    if normalized == "localhost":
        return True
    try:
        return ipaddress.ip_address(normalized).is_loopback
    except ValueError:
        return False


def validate_network_configuration(host: str, access_token: str) -> None:
    if access_token and len(access_token) < MIN_ACCESS_TOKEN_LENGTH:
        raise RuntimeError(
            f"VERSENA_ACCESS_TOKEN must contain at least {MIN_ACCESS_TOKEN_LENGTH} characters"
        )
    if not is_loopback_host(host) and not access_token:
        raise RuntimeError(
            "VERSENA_ACCESS_TOKEN is required when VerseNa listens outside localhost"
        )


def is_allowed_origin(origin: str, host: str, allowed_origins: tuple[str, ...]) -> bool:
    if not origin:
        return False
    normalized_origin = origin.rstrip("/")
    if normalized_origin in {item.rstrip("/") for item in allowed_origins}:
        return True
    if normalized_origin == "null":
        return False
    parsed = urlsplit(normalized_origin)
    return parsed.scheme in {"http", "https"} and parsed.netloc.lower() == host.lower()


def persist_access_token(access_token: str, token_file: Path) -> None:
    token_file = Path(token_file)
    token_file.parent.mkdir(parents=True, exist_ok=True)
    temporary_file = token_file.with_name(f".{token_file.name}.{secrets.token_hex(6)}.tmp")
    try:
        temporary_file.write_text(
            secret_protector.protect(access_token) + "\n",
            encoding="utf-8",
        )
        try:
            temporary_file.chmod(0o600)
        except OSError:
            pass
        os.replace(temporary_file, token_file)
    finally:
        temporary_file.unlink(missing_ok=True)


def resolve_access_token(
    host: str,
    configured_token: str,
    token_file: Path,
    dotenv_path: Path | None = None,
) -> tuple[str, bool]:
    token_file = Path(token_file)
    stored_token = ""
    stored_value = ""
    if token_file.is_file():
        stored_value = token_file.read_text(encoding="utf-8").strip()
        try:
            stored_token = secret_protector.unprotect(stored_value)
        except SecretStoreError as exc:
            raise RuntimeError(
                "VerseNa access token could not be decrypted for this OS user"
            ) from exc

    access_token = stored_token or (configured_token or "").strip()
    register_secret(access_token)
    initialized = False
    if not access_token and not is_loopback_host(host):
        access_token = secrets.token_urlsafe(32)

    validate_network_configuration(host, access_token)
    if stored_token and not secret_protector.is_protected(stored_value):
        persist_access_token(stored_token, token_file)
    elif access_token and not stored_token:
        persist_access_token(access_token, token_file)
        initialized = True
    if access_token and dotenv_path:
        dotenv_path = Path(dotenv_path)
        try:
            if dotenv_path.is_file() and dotenv_values(dotenv_path).get("VERSENA_ACCESS_TOKEN"):
                unset_key(str(dotenv_path), "VERSENA_ACCESS_TOKEN")
        except OSError:
            pass
    return access_token, initialized


def print_access_token_panel(access_token: str, port: int) -> None:
    border = "=" * 68
    print(f"\n{border}", flush=True)
    print(" VerseNa LAN access token", flush=True)
    print(f" URL:   http://<LAN-IP>:{port}", flush=True)
    print(f" TOKEN: {access_token}", flush=True)
    print(" Keep this token private. It is only printed when first stored.", flush=True)
    print(f"{border}\n", flush=True)


class AuthManager:
    def __init__(self, access_token: str = "", session_ttl_seconds: int = 604800):
        self.session_ttl_seconds = session_ttl_seconds
        self._access_token = ""
        self._sessions: dict[str, float] = {}
        self._failed_logins: dict[str, deque[float]] = defaultdict(deque)
        self.configure(access_token)

    @property
    def required(self) -> bool:
        return bool(self._access_token)

    def configure(self, access_token: str) -> None:
        self._access_token = (access_token or "").strip()
        self._sessions.clear()
        self._failed_logins.clear()

    def validate_access_token(self, candidate: str) -> bool:
        if not self.required or not candidate:
            return False
        return hmac.compare_digest(self._access_token, candidate)

    def create_session(self) -> str:
        self._purge_expired_sessions()
        session_id = secrets.token_urlsafe(32)
        self._sessions[session_id] = time.time() + self.session_ttl_seconds
        return session_id

    def revoke_session(self, session_id: str) -> None:
        if session_id:
            self._sessions.pop(session_id, None)

    def validate_session(self, session_id: str) -> bool:
        if not session_id:
            return False
        expires_at = self._sessions.get(session_id, 0)
        if expires_at <= time.time():
            self._sessions.pop(session_id, None)
            return False
        return True

    def authenticate(self, authorization: str = "", session_id: str = "") -> bool:
        if not self.required:
            return True
        if authorization.startswith("Bearer "):
            return self.validate_access_token(authorization[7:].strip())
        return self.validate_session(session_id)

    def authenticate_bearer(self, authorization: str = "") -> bool:
        return authorization.startswith("Bearer ") and self.validate_access_token(
            authorization[7:].strip()
        )

    def can_attempt_login(self, client_id: str) -> bool:
        attempts = self._recent_attempts(client_id)
        return len(attempts) < MAX_LOGIN_ATTEMPTS

    def record_failed_login(self, client_id: str) -> None:
        self._recent_attempts(client_id).append(time.time())

    def clear_failed_logins(self, client_id: str) -> None:
        self._failed_logins.pop(client_id, None)

    def _recent_attempts(self, client_id: str) -> deque[float]:
        now = time.time()
        attempts = self._failed_logins[client_id or "unknown"]
        while attempts and attempts[0] <= now - LOGIN_WINDOW_SECONDS:
            attempts.popleft()
        return attempts

    def _purge_expired_sessions(self) -> None:
        now = time.time()
        expired = [session_id for session_id, expiry in self._sessions.items() if expiry <= now]
        for session_id in expired:
            self._sessions.pop(session_id, None)


_effective_token, _token_initialized = resolve_access_token(
    settings.HOST,
    settings.ACCESS_TOKEN,
    settings.ACCESS_TOKEN_FILE,
    settings.BASE_DIR / ".env",
)
settings.ACCESS_TOKEN = _effective_token
if _token_initialized:
    print_access_token_panel(_effective_token, settings.PORT)

auth_manager = AuthManager(_effective_token, settings.AUTH_SESSION_TTL_SECONDS)
