import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path):
    """创建临时数据库的测试客户端"""
    import db.database as db_mod
    from db.database import Database

    test_db = Database(db_path=tmp_path / "test.db")

    import main
    original_db = main.db
    # 替换全局 db 实例
    import api.session_api as session_api_mod
    db_mod.db = test_db
    session_api_mod.db = test_db
    main.db = test_db

    import asyncio
    loop = asyncio.new_event_loop()
    loop.run_until_complete(test_db.connect())

    from main import app
    with TestClient(app) as c:
        yield c

    loop.run_until_complete(test_db.close())
    loop.close()
    # 恢复
    db_mod.db = original_db
    session_api_mod.db = original_db
    main.db = original_db


def test_create_session(client):
    resp = client.post("/api/sessions", json={"name": ""})
    assert resp.status_code == 200
    data = resp.json()
    assert "session_id" in data
    assert data["session_id"].startswith("session_")


def test_create_session_with_name(client):
    resp = client.post("/api/sessions", json={"name": "my_session"})
    assert resp.status_code == 200
    assert resp.json()["session_id"] == "my_session"


def test_list_sessions_empty(client):
    resp = client.get("/api/sessions")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_sessions(client):
    # 先插入一条消息
    from db.database import db as global_db
    import asyncio
    # 使用 session_api 的 db
    import api.session_api as sm
    loop = asyncio.new_event_loop()
    loop.run_until_complete(sm.db.save_message("test_session", "user", "hello"))

    resp = client.get("/api/sessions")
    assert resp.status_code == 200
    sessions = resp.json()
    assert len(sessions) == 1
    assert sessions[0]["id"] == "test_session"
    assert sessions[0]["msg_count"] == 1


def test_get_session_history(client):
    import api.session_api as sm
    import asyncio
    loop = asyncio.new_event_loop()
    loop.run_until_complete(sm.db.save_message("hist_session", "user", "hi"))
    loop.run_until_complete(sm.db.save_message("hist_session", "assistant", "hello!"))

    resp = client.get("/api/sessions/hist_session/history")
    assert resp.status_code == 200
    history = resp.json()
    assert len(history) == 2
    assert history[0]["role"] == "user"
    assert history[1]["role"] == "assistant"


def test_delete_session(client):
    import api.session_api as sm
    import asyncio
    loop = asyncio.new_event_loop()
    loop.run_until_complete(sm.db.save_message("del_session", "user", "bye"))

    resp = client.delete("/api/sessions/del_session")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"

    # 确认已删除
    resp = client.get("/api/sessions")
    sessions = resp.json()
    assert all(s["id"] != "del_session" for s in sessions)
