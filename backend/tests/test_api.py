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
