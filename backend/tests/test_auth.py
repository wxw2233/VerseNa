import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from auth import (
    AuthManager,
    auth_manager,
    is_allowed_origin,
    is_loopback_host,
    print_access_token_panel,
    resolve_access_token,
    validate_network_configuration,
)
from config import settings
from main import app
from secret_store import secret_protector


TEST_TOKEN = "test-access-token-with-enough-entropy"


@pytest.fixture
def auth_client(monkeypatch):
    import api.qq_api as qq_api

    async def skip_qq_config_load():
        return None

    monkeypatch.setattr(qq_api, "load_qq_config", skip_qq_config_load)
    original_settings_token = settings.ACCESS_TOKEN
    auth_manager.configure(TEST_TOKEN)
    try:
        with TestClient(app) as client:
            yield client
    finally:
        settings.ACCESS_TOKEN = original_settings_token
        auth_manager.configure("")


def test_lan_listener_requires_a_strong_token():
    assert is_loopback_host("127.0.0.1")
    assert is_loopback_host("::1")
    assert not is_loopback_host("0.0.0.0")

    validate_network_configuration("127.0.0.1", "")
    with pytest.raises(RuntimeError, match="required"):
        validate_network_configuration("0.0.0.0", "")
    with pytest.raises(RuntimeError, match="at least"):
        validate_network_configuration("0.0.0.0", "short")
    validate_network_configuration("0.0.0.0", "123456")
    validate_network_configuration("0.0.0.0", TEST_TOKEN)
    assert is_allowed_origin("http://192.168.1.8:8002", "192.168.1.8:8002", ())
    assert not is_allowed_origin("http://evil.example", "192.168.1.8:8002", ())


def test_first_lan_start_generates_persistent_token(tmp_path, capsys):
    token_file = tmp_path / "access_token"
    token, generated = resolve_access_token("0.0.0.0", "", token_file)

    assert generated is True
    assert len(token) >= 20
    stored = token_file.read_text(encoding="utf-8").strip()
    assert secret_protector.is_protected(stored)
    assert secret_protector.unprotect(stored) == token
    assert token not in stored

    print_access_token_panel(token, 8002)
    panel = capsys.readouterr().out
    assert token in panel
    assert "http://<LAN-IP>:8002" in panel

    restored_token, generated_again = resolve_access_token("0.0.0.0", "", token_file)
    assert restored_token == token
    assert generated_again is False


def test_existing_environment_token_is_migrated_to_persistent_file(tmp_path):
    token_file = tmp_path / "access_token"
    dotenv_file = tmp_path / ".env"
    dotenv_file.write_text(
        f"VERSENA_HOST=0.0.0.0\nVERSENA_ACCESS_TOKEN={TEST_TOKEN}\n",
        encoding="utf-8",
    )

    token, initialized = resolve_access_token(
        "0.0.0.0", TEST_TOKEN, token_file, dotenv_file
    )

    assert token == TEST_TOKEN
    assert initialized is True
    stored = token_file.read_text(encoding="utf-8").strip()
    assert secret_protector.is_protected(stored)
    assert secret_protector.unprotect(stored) == TEST_TOKEN
    assert "VERSENA_ACCESS_TOKEN" not in dotenv_file.read_text(encoding="utf-8")
    assert "VERSENA_HOST=0.0.0.0" in dotenv_file.read_text(encoding="utf-8")

    restored_token, initialized_again = resolve_access_token(
        "0.0.0.0",
        "different-environment-token-with-enough-entropy",
        token_file,
    )
    assert restored_token == TEST_TOKEN
    assert initialized_again is False


def test_login_issues_cookie_and_logout_revokes_it(auth_client):
    status = auth_client.get("/api/auth/status")
    assert status.json() == {"required": True, "authenticated": False}
    assert auth_client.get("/api/config/model").status_code == 401

    rejected = auth_client.post("/api/auth/login", json={"token": "wrong-token"})
    assert rejected.status_code == 401

    accepted = auth_client.post("/api/auth/login", json={"token": TEST_TOKEN})
    assert accepted.status_code == 200
    assert accepted.cookies.get("versena_session")
    assert auth_client.get("/api/config/model").status_code == 200
    assert auth_client.get("/api/auth/status").json()["authenticated"] is True

    assert auth_client.post("/api/auth/logout").status_code == 403
    assert auth_client.post(
        "/api/auth/logout",
        headers={"Origin": "http://testserver"},
    ).status_code == 200
    assert auth_client.get("/api/config/model").status_code == 401


def test_authenticated_post_accepts_same_origin_referer(auth_client, monkeypatch):
    saved = {}

    async def set_config(key, value):
        saved[key] = value

    monkeypatch.setattr("api.config_api.db.set_config", set_config)
    assert auth_client.post("/api/auth/login", json={"token": TEST_TOKEN}).status_code == 200

    response = auth_client.post(
        "/api/config/agent",
        headers={"Referer": "http://testserver/settings"},
        json={"max_steps": 20, "max_history": 60},
    )

    assert response.status_code == 200
    assert "agent_max_steps" not in saved
    assert "agent_max_history" not in saved


def test_bearer_token_authentication(auth_client):
    response = auth_client.get(
        "/api/config/model",
        headers={"Authorization": f"Bearer {TEST_TOKEN}"},
    )
    assert response.status_code == 200


def test_authenticated_user_can_rotate_token(auth_client, tmp_path, monkeypatch):
    new_token = "new-test-access-token-with-enough-entropy"
    token_file = tmp_path / "access_token"
    monkeypatch.setattr(settings, "ACCESS_TOKEN_FILE", token_file)

    login = auth_client.post("/api/auth/login", json={"token": TEST_TOKEN})
    assert login.status_code == 200

    response = auth_client.put(
        "/api/auth/token",
        headers={"Origin": "http://testserver"},
        json={"current_token": TEST_TOKEN, "new_token": new_token},
    )
    assert response.status_code == 200
    stored = token_file.read_text(encoding="utf-8").strip()
    assert secret_protector.is_protected(stored)
    assert secret_protector.unprotect(stored) == new_token
    assert new_token not in stored
    assert auth_client.get("/api/auth/status").json()["authenticated"] is True

    assert auth_client.get(
        "/api/config/model",
        headers={"Authorization": f"Bearer {TEST_TOKEN}"},
    ).status_code == 401
    assert auth_client.get(
        "/api/config/model",
        headers={"Authorization": f"Bearer {new_token}"},
    ).status_code == 200


def test_login_attempts_are_rate_limited():
    manager = AuthManager(TEST_TOKEN)
    for _ in range(5):
        assert manager.can_attempt_login("client")
        manager.record_failed_login("client")
    assert not manager.can_attempt_login("client")
    manager.clear_failed_logins("client")
    assert manager.can_attempt_login("client")


def test_websocket_requires_authenticated_session(auth_client):
    with auth_client.websocket_connect("/ws/chat") as websocket:
        assert websocket.receive_json() == {"type": "auth_required"}
        with pytest.raises(WebSocketDisconnect) as closed:
            websocket.receive_json()
    assert closed.value.code == 4401


def test_websocket_accepts_login_cookie(auth_client):
    login = auth_client.post("/api/auth/login", json={"token": TEST_TOKEN})
    assert login.status_code == 200
    with auth_client.websocket_connect(
        "/ws/chat",
        headers={"Origin": "http://testserver"},
    ) as websocket:
        websocket.close()


def test_websocket_rejects_cross_site_cookie(auth_client):
    login = auth_client.post("/api/auth/login", json={"token": TEST_TOKEN})
    assert login.status_code == 200
    with auth_client.websocket_connect(
        "/ws/chat",
        headers={"Origin": "http://evil.example"},
    ) as websocket:
        assert websocket.receive_json() == {"type": "origin_rejected"}
        with pytest.raises(WebSocketDisconnect) as closed:
            websocket.receive_json()
    assert closed.value.code == 4403
