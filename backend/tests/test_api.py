import pytest
from fastapi.testclient import TestClient
from main import app

def test_health():
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"

def test_get_model_config():
    client = TestClient(app)
    resp = client.get("/api/config/model")
    assert resp.status_code == 200
    assert "model_name" in resp.json()
