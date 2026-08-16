import base64
import ctypes
import hashlib
import json
import os
import secrets
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from config import settings
from security_utils import register_secret, register_secret_tree


DPAPI_PREFIX = "enc:dpapi:v1:"
FERNET_PREFIX = "enc:fernet:v1:"
SENSITIVE_CONFIG_KEYS = {
    "api_key",
    "model_providers",
    "qq_app_secret",
    "search_serpapi_key",
    "search_tavily_key",
    "search_bing_key",
}


class SecretStoreError(RuntimeError):
    pass


class _DataBlob(ctypes.Structure):
    _fields_ = [
        ("cbData", ctypes.c_ulong),
        ("pbData", ctypes.POINTER(ctypes.c_ubyte)),
    ]


def _dpapi_transform(data: bytes, *, decrypt: bool) -> bytes:
    if os.name != "nt":
        raise SecretStoreError("DPAPI secrets can only be decrypted by Windows")
    source_buffer = ctypes.create_string_buffer(data)
    source = _DataBlob(
        len(data),
        ctypes.cast(source_buffer, ctypes.POINTER(ctypes.c_ubyte)),
    )
    destination = _DataBlob()
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    if decrypt:
        success = crypt32.CryptUnprotectData(
            ctypes.byref(source),
            None,
            None,
            None,
            None,
            0x01,
            ctypes.byref(destination),
        )
    else:
        success = crypt32.CryptProtectData(
            ctypes.byref(source),
            "VerseNa secret",
            None,
            None,
            None,
            0x01,
            ctypes.byref(destination),
        )
    if not success:
        raise SecretStoreError(str(ctypes.WinError()))
    try:
        return ctypes.string_at(destination.pbData, destination.cbData)
    finally:
        kernel32.LocalFree(destination.pbData)


class SecretProtector:
    def __init__(self, key_file: Path | None = None, configured_key: str | None = None):
        self.key_file = Path(key_file or settings.SECRET_KEY_FILE)
        self.configured_key = (
            settings.SECRET_KEY if configured_key is None else configured_key
        )
        self._fernet = None

    @staticmethod
    def is_protected(value: str) -> bool:
        text = str(value or "")
        return text.startswith((DPAPI_PREFIX, FERNET_PREFIX))

    def protect(self, value: str) -> str:
        plaintext = str(value or "")
        if not plaintext or self.is_protected(plaintext):
            return plaintext
        register_secret(plaintext)
        self._register_structured_secrets(plaintext)
        if os.name == "nt":
            encrypted = _dpapi_transform(plaintext.encode("utf-8"), decrypt=False)
            return DPAPI_PREFIX + base64.urlsafe_b64encode(encrypted).decode("ascii")
        encrypted = self._get_fernet().encrypt(plaintext.encode("utf-8"))
        return FERNET_PREFIX + encrypted.decode("ascii")

    def unprotect(self, value: str) -> str:
        protected = str(value or "")
        if not protected:
            return ""
        try:
            if protected.startswith(DPAPI_PREFIX):
                encrypted = base64.urlsafe_b64decode(protected[len(DPAPI_PREFIX):])
                plaintext = _dpapi_transform(encrypted, decrypt=True).decode("utf-8")
            elif protected.startswith(FERNET_PREFIX):
                token = protected[len(FERNET_PREFIX):].encode("ascii")
                plaintext = self._get_fernet().decrypt(token).decode("utf-8")
            else:
                plaintext = protected
        except (ValueError, UnicodeError, InvalidToken, OSError) as exc:
            raise SecretStoreError("Stored VerseNa secret could not be decrypted") from exc
        register_secret(plaintext)
        self._register_structured_secrets(plaintext)
        return plaintext

    def _get_fernet(self) -> Fernet:
        if self._fernet is not None:
            return self._fernet
        if self.configured_key:
            raw = self.configured_key.encode("utf-8")
            try:
                self._fernet = Fernet(raw)
            except (ValueError, TypeError):
                derived = base64.urlsafe_b64encode(hashlib.sha256(raw).digest())
                self._fernet = Fernet(derived)
            return self._fernet

        self.key_file.parent.mkdir(parents=True, exist_ok=True)
        if self.key_file.is_file():
            key = self.key_file.read_bytes().strip()
        else:
            key = Fernet.generate_key()
            temporary = self.key_file.with_name(
                f".{self.key_file.name}.{secrets.token_hex(6)}.tmp"
            )
            try:
                temporary.write_bytes(key + b"\n")
                try:
                    temporary.chmod(0o600)
                except OSError:
                    pass
                os.replace(temporary, self.key_file)
            finally:
                temporary.unlink(missing_ok=True)
        try:
            self.key_file.chmod(0o600)
        except OSError:
            pass
        try:
            self._fernet = Fernet(key)
        except (ValueError, TypeError) as exc:
            raise SecretStoreError("Invalid VerseNa secret key file") from exc
        return self._fernet

    @staticmethod
    def _register_structured_secrets(value: str) -> None:
        try:
            register_secret_tree(json.loads(value))
        except (json.JSONDecodeError, TypeError):
            pass


secret_protector = SecretProtector()
