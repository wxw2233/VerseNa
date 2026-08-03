import pytest
from fastapi.testclient import TestClient
from main import app
from auth import is_loopback_host
from config import settings

@pytest.fixture
def client(monkeypatch):
    import api.qq_api as qq_api

    async def skip_qq_config_load():
        return None

    monkeypatch.setattr(qq_api, "load_qq_config", skip_qq_config_load)
    with TestClient(app) as test_client:
        yield test_client


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_backend_defaults_to_localhost():
    assert is_loopback_host("127.0.0.1")
    assert is_loopback_host("localhost")

def test_get_model_config(client):
    resp = client.get("/api/config/model")
    assert resp.status_code == 200
    assert "model_name" in resp.json()


def test_agent_config_can_be_saved_and_loaded(client, monkeypatch):
    saved = {}

    async def get_config(key, default=""):
        return saved.get(key, default)

    async def set_config(key, value):
        saved[key] = value

    monkeypatch.setattr("api.config_api.db.get_config", get_config)
    monkeypatch.setattr("api.config_api.db.set_config", set_config)

    payload = {
        "max_steps": 24,
        "max_history": 80,
        "max_context": 64000,
        "max_tokens": 4096,
        "custom_instructions": "Keep answers concise.",
    }
    response = client.post("/api/config/agent", json=payload)

    assert response.status_code == 200
    assert client.get("/api/config/agent").json() == payload


def test_model_dump_supports_pydantic_v1(monkeypatch):
    import api.config_api as config_api

    class LegacyModel:
        def dict(self, **kwargs):
            return {"kwargs": kwargs}

    monkeypatch.setattr(config_api, "PYDANTIC_V2", False)

    assert config_api._model_dump(LegacyModel(), exclude_none=True) == {
        "kwargs": {"exclude_none": True}
    }


def test_source_update_status_api(client, monkeypatch):
    async def status():
        return {
            "supported": True,
            "version": "1.1.0",
            "branch": "master",
            "commit_short": "abcdef0",
            "upstream": "origin/master",
            "dirty": False,
            "ahead": 0,
            "behind": 0,
            "update_available": False,
            "pending": False,
            "restart_required": False,
            "message": "up to date",
        }

    monkeypatch.setattr("api.update_api.source_updater.status", status)

    response = client.get("/api/update/status")

    assert response.status_code == 200
    assert response.json()["branch"] == "master"


def test_tool_workspace_api(client, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "TOOL_WORKSPACE", tmp_path / "workspace")

    response = client.get("/api/tools/workspace")

    assert response.status_code == 200
    assert response.json()["path"] == str(tmp_path / "workspace")
    assert (tmp_path / "workspace").is_dir()


def test_cors_allows_local_frontend_only(client):
    allowed = client.options(
        "/health",
        headers={
            "Origin": "http://127.0.0.1:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    blocked = client.options(
        "/health",
        headers={
            "Origin": "https://example.com",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"
    assert blocked.status_code == 400
    assert "access-control-allow-origin" not in blocked.headers


def test_frontend_is_served_with_spa_fallback(client, tmp_path, monkeypatch):
    frontend_dist = tmp_path / "dist"
    frontend_dist.mkdir()
    frontend_dist.joinpath("index.html").write_text(
        '<div id="app">VerseNa</div>',
        encoding="utf-8",
    )
    frontend_dist.joinpath("version.txt").write_text("1.1.0", encoding="utf-8")
    monkeypatch.setattr(settings, "FRONTEND_DIST", frontend_dist)

    assert "VerseNa" in client.get("/").text
    assert "VerseNa" in client.get("/settings").text
    assert client.get("/version.txt").text == "1.1.0"
    assert client.get("/api/does-not-exist").status_code == 404
