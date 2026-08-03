import sys
import asyncio
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

from db.database import Database


def test_reasoning_segments_are_compacted_for_persistence():
    from api.chat import _append_response_segment

    segments = []
    _append_response_segment(segments, {
        "type": "reasoning",
        "reasoning_id": "reasoning_1",
        "content": "",
        "status": "running",
    })
    _append_response_segment(segments, {
        "type": "reasoning",
        "reasoning_id": "reasoning_1",
        "content": "分析",
        "status": "running",
    })
    _append_response_segment(segments, {
        "type": "reasoning",
        "reasoning_id": "reasoning_1",
        "content": "完成",
        "status": "done",
        "duration_ms": 1200,
    })
    _append_response_segment(segments, {"type": "text", "content": "答"})
    _append_response_segment(segments, {"type": "text", "content": "案"})

    assert segments == [
        {
            "type": "reasoning",
            "reasoning_id": "reasoning_1",
            "content": "分析完成",
            "status": "done",
            "duration_ms": 1200,
        },
        {"type": "text", "content": "答案"},
    ]


@pytest.mark.asyncio
async def test_client_message_id_is_unique(tmp_path):
    database = Database(tmp_path / "idempotency.db")
    await database.connect()
    try:
        first = await database.save_message(
            "session-1",
            "user",
            "hello",
            client_message_id="client-1",
            metadata={"generation_id": "generation-1"},
        )
        duplicate = await database.save_message(
            "session-1",
            "user",
            "hello again",
            client_message_id="client-1",
            metadata={"generation_id": "generation-2"},
        )

        assert first is True
        assert duplicate is False
        history = await database.get_history("session-1")
        assert len(history) == 1
        assert history[0]["content"] == "hello"
        assert history[0]["client_message_id"] == "client-1"
        assert history[0]["generation_id"] == "generation-1"
    finally:
        await database.close()


def test_websocket_acknowledges_and_deduplicates(tmp_path, monkeypatch):
    import api.chat as chat_api
    import api.config_api as config_api
    import api.qq_api as qq_api
    import api.session_api as session_api
    import main

    chat_api.auth_manager.configure("")

    database = Database(tmp_path / "protocol.db")

    class FakeAgent:
        def __init__(self):
            self.calls = 0

        async def run(self, *args, **kwargs):
            self.calls += 1
            if args[1] == "wait for stop":
                stop_event = kwargs["stop_event"]
                yield {"type": "segment", "segment": {"type": "text", "content": "started"}}
                await asyncio.sleep(0.05)
                yield {
                    "type": "segment",
                    "segment": {
                        "type": "text",
                        "content": "wrong generation ignored" if not stop_event.is_set() else "stopped too early",
                    },
                }
                while not stop_event.is_set():
                    await asyncio.sleep(0.01)
                yield {"type": "segment", "segment": {"type": "text", "content": "stopped"}}
                yield {"type": "done", "emoji": ""}
                return
            yield {"type": "segment", "segment": {"type": "text", "content": "pong"}}
            yield {"type": "done", "emoji": ""}

    fake_agent = FakeAgent()

    async def create_fake_agent(*args, **kwargs):
        return fake_agent

    async def skip_qq_config_load():
        return None

    monkeypatch.setattr(main, "db", database)
    monkeypatch.setattr(chat_api, "db", database)
    monkeypatch.setattr(config_api, "db", database)
    monkeypatch.setattr(session_api, "db", database)
    monkeypatch.setattr(chat_api, "create_agent", create_fake_agent)
    monkeypatch.setattr(qq_api, "load_qq_config", skip_qq_config_load)

    payload = {
        "type": "message",
        "session_id": "protocol-session",
        "content": "ping",
        "persona": "default",
        "client_message_id": "client-fixed",
        "generation_id": "generation-fixed",
    }

    with TestClient(main.app) as client:
        with client.websocket_connect("/ws/chat") as websocket:
            websocket.send_json(payload)

            accepted = websocket.receive_json()
            segment = websocket.receive_json()
            done = websocket.receive_json()

            assert accepted == {
                "type": "accepted",
                "accepted": True,
                "duplicate": False,
                "status": "accepted",
                "client_message_id": "client-fixed",
                "generation_id": "generation-fixed",
                "request_type": "message",
            }
            assert segment["generation_id"] == "generation-fixed"
            assert segment["segment"]["content"] == "pong"
            assert done["type"] == "done"
            assert done["generation_id"] == "generation-fixed"

            websocket.send_json(payload)
            duplicate = websocket.receive_json()
            assert duplicate["type"] == "accepted"
            assert duplicate["duplicate"] is True
            assert duplicate["generation_id"] == "generation-fixed"
            assert duplicate["status"] == "completed"
            assert fake_agent.calls == 1

            stop_payload = {
                **payload,
                "content": "wait for stop",
                "client_message_id": "client-stop",
                "generation_id": "generation-stop",
            }
            websocket.send_json(stop_payload)
            assert websocket.receive_json()["type"] == "accepted"
            assert websocket.receive_json()["segment"]["content"] == "started"

            websocket.send_json({"type": "stop", "generation_id": "generation-other"})
            still_running = websocket.receive_json()
            assert still_running["segment"]["content"] == "wrong generation ignored"

            websocket.send_json({"type": "stop", "generation_id": "generation-stop"})
            stopped = websocket.receive_json()
            stop_done = websocket.receive_json()
            assert stopped["segment"]["content"] == "stopped"
            assert stopped["generation_id"] == "generation-stop"
            assert stop_done["type"] == "done"

            websocket.send_json(stop_payload)
            stopped_duplicate = websocket.receive_json()
            assert stopped_duplicate["duplicate"] is True
            assert stopped_duplicate["status"] == "stopped"

        history = client.get("/api/sessions/protocol-session/history").json()
        user_messages = [message for message in history if message["role"] == "user"]
        client_ids = [message["client_message_id"] for message in user_messages]
        assert client_ids.count("client-fixed") == 1
        assert client_ids.count("client-stop") == 1

    assert fake_agent.calls == 2
