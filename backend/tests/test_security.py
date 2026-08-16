import json
import sqlite3

import pytest
from fastapi import Response

from db.database import Database
from secret_store import SENSITIVE_CONFIG_KEYS, secret_protector
from security_utils import (
    REDACTED,
    redact_sensitive_data,
    redact_sensitive_text,
    register_secret,
)
from tools.base import BaseTool, ToolContext
from tools.registry import ToolRegistry


def test_secret_protector_round_trip():
    plaintext = "sk-security-roundtrip-12345678"

    protected = secret_protector.protect(plaintext)

    assert secret_protector.is_protected(protected)
    assert plaintext not in protected
    assert secret_protector.unprotect(protected) == plaintext


@pytest.mark.asyncio
async def test_database_migrates_sensitive_config_and_redacts_old_content(tmp_path):
    secret = "sk-security-migration-12345678"
    db_path = tmp_path / "security.db"
    connection = sqlite3.connect(db_path)
    connection.executescript("""
        CREATE TABLE app_config (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            persona TEXT DEFAULT 'default',
            metadata TEXT DEFAULT '{}',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    providers = json.dumps({"custom": {"api_key": secret}})
    connection.execute(
        "INSERT INTO app_config (key, value) VALUES (?, ?)",
        ("model_providers", providers),
    )
    connection.execute(
        "INSERT INTO conversations (session_id, role, content, metadata) VALUES (?, ?, ?, ?)",
        ("security", "assistant", f"secret={secret}", json.dumps({"detail": secret})),
    )
    connection.commit()
    connection.close()

    database = Database(db_path)
    await database.connect()
    assert await database.get_config("model_providers") == providers
    await database.close()

    connection = sqlite3.connect(db_path)
    raw_config = connection.execute(
        "SELECT value FROM app_config WHERE key = 'model_providers'"
    ).fetchone()[0]
    content, metadata = connection.execute(
        "SELECT content, metadata FROM conversations WHERE session_id = 'security'"
    ).fetchone()
    connection.close()

    assert secret_protector.is_protected(raw_config)
    assert secret not in raw_config
    assert secret not in content
    assert secret not in metadata
    assert REDACTED in content
    assert REDACTED in metadata


@pytest.mark.asyncio
async def test_all_sensitive_config_keys_are_encrypted_at_rest(tmp_path):
    database = Database(tmp_path / "all-secrets.db")
    await database.connect()
    for index, key in enumerate(sorted(SENSITIVE_CONFIG_KEYS)):
        await database.set_config(key, f"secret-value-{index}-123456")

    cursor = await database._db.execute(
        "SELECT key, value FROM app_config WHERE key IN ({})".format(
            ",".join("?" for _ in SENSITIVE_CONFIG_KEYS)
        ),
        tuple(sorted(SENSITIVE_CONFIG_KEYS)),
    )
    rows = await cursor.fetchall()
    assert len(rows) == len(SENSITIVE_CONFIG_KEYS)
    assert all(secret_protector.is_protected(row["value"]) for row in rows)
    await database.close()


def test_redaction_covers_credentials_without_corrupting_normal_words():
    exact = "custom-secret-value-123456"
    register_secret(exact)
    source = (
        f"exact={exact} api_key=plain-value-123456 "
        "sk-prefix-secret-123456 tp-prefix-secret-123456 "
        "Bearer bearer-token-123456 "
        "ghp_1234567890abcdef "
        "-----BEGIN PRIVATE KEY-----\nabc123\n-----END PRIVATE KEY----- "
        "skill_manager tokenization"
    )

    redacted = redact_sensitive_text(source)

    assert exact not in redacted
    assert "plain-value-123456" not in redacted
    assert "sk-prefix-secret-123456" not in redacted
    assert "tp-prefix-secret-123456" not in redacted
    assert "bearer-token-123456" not in redacted
    assert "ghp_1234567890abcdef" not in redacted
    assert "BEGIN PRIVATE KEY" not in redacted
    assert "skill_manager" in redacted
    assert "tokenization" in redacted
    assert redact_sensitive_data({"nested": [exact]}) == {"nested": [REDACTED]}


@pytest.mark.asyncio
async def test_credential_get_apis_are_write_only(monkeypatch):
    values = {
        "api_key": "sk-model-secret-12345678",
        "api_base": "https://example.test/v1",
        "model_name": "model",
        "search_search_strategy": "auto",
        "search_search_provider": "serpapi",
        "search_serpapi_key": "serp-secret-123456",
        "search_tavily_key": "tavily-secret-123456",
        "search_bing_key": "bing-secret-123456",
        "qq_app_id": "app-id",
        "qq_app_secret": "qq-secret-123456",
        "qq_sandbox": "true",
    }

    async def get_config(key, default=""):
        return values.get(key, default)

    monkeypatch.setattr("api.config_api.db.get_config", get_config)

    from api.config_api import get_model_config, get_search_config
    from api.qq_api import get_qq_config

    model_response = Response()
    model = await get_model_config(model_response)
    search_response = Response()
    search = await get_search_config(search_response)
    qq_response = Response()
    qq = await get_qq_config(qq_response)

    assert model["api_key"] == ""
    assert model["has_key"] is True
    assert search["serpapi_key"] == search["tavily_key"] == search["bing_key"] == ""
    assert search["has_serpapi_key"] is True
    assert search["has_tavily_key"] is True
    assert search["has_bing_key"] is True
    assert qq["app_secret"] == ""
    assert qq["has_secret"] is True
    assert model_response.headers["cache-control"] == "no-store"
    assert search_response.headers["cache-control"] == "no-store"
    assert qq_response.headers["cache-control"] == "no-store"


@pytest.mark.asyncio
async def test_blank_credential_updates_preserve_existing_secrets(monkeypatch):
    from api import config_api, qq_api

    existing = {
        "api_key": "existing-model-secret",
        "qq_app_secret": "existing-qq-secret",
    }
    writes = {}

    async def get_config(key, default=""):
        return existing.get(key, default)

    async def set_config(key, value):
        writes[key] = value

    async def start_qq():
        return True

    monkeypatch.setattr(config_api.db, "get_config", get_config)
    monkeypatch.setattr(config_api.db, "set_config", set_config)
    monkeypatch.setattr(qq_api.qq_adapter, "start", start_qq)
    monkeypatch.setattr(qq_api.qq_adapter, "app_id", "")
    monkeypatch.setattr(qq_api.qq_adapter, "app_secret", "")

    await config_api.set_model_config(config_api.ModelConfig(
        api_key="",
        base_url="https://example.test/v1",
        model_name="model",
    ))
    await config_api.set_search_config(config_api.SearchConfigReq(
        serpapi_key="",
        tavily_key="",
        bing_key="",
    ))
    await qq_api.set_qq_config(qq_api.QQConfig(
        app_id="app-id",
        app_secret="",
        sandbox=True,
    ))

    assert "api_key" not in writes
    assert "search_serpapi_key" not in writes
    assert "search_tavily_key" not in writes
    assert "search_bing_key" not in writes
    assert "qq_app_secret" not in writes
    assert qq_api.qq_adapter.app_secret == "existing-qq-secret"


@pytest.mark.asyncio
async def test_registry_redacts_tool_results_and_errors(tmp_path):
    secret = "custom-tool-secret-123456"
    register_secret(secret)

    class LeakyTool(BaseTool):
        name = "leaky"
        description = "test"
        parameters = {"type": "object", "properties": {}}

        async def execute(self, **kwargs):
            return json.dumps({"success": True, "data": {"output": secret}})

    registry = ToolRegistry()
    registry.register(LeakyTool())

    result = await registry.execute(
        "leaky", {}, context=ToolContext("security", tmp_path)
    )

    assert secret not in result
    assert REDACTED in result


def test_runtime_log_redacts_registered_secret(tmp_path, monkeypatch):
    import api.log_api as log_api

    secret = "custom-log-secret-123456"
    register_secret(secret)
    monkeypatch.setattr(log_api, "LOG_DIR", tmp_path)
    monkeypatch.setattr(log_api, "LOG_FILE", tmp_path / "runtime.log")

    log_api.log_error("Security", f"provider failed with {secret}")

    output = log_api.LOG_FILE.read_text(encoding="utf-8")
    assert secret not in output
    assert REDACTED in output
