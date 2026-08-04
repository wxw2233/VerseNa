import base64

import httpx
import pytest

from api.tts_api import _audio_media_type
from config import settings
from tts import adapter as tts_adapter


@pytest.mark.parametrize(
    ("audio", "expected"),
    [
        (b"RIFF\x00\x00\x00\x00WAVEdata", "audio/wav"),
        (b"OggSdata", "audio/ogg"),
        (b"fLaCdata", "audio/flac"),
        (b"\x00\x00\x00\x18ftypM4A ", "audio/mp4"),
        (b"ID3data", "audio/mpeg"),
    ],
)
def test_audio_media_type_detects_common_formats(audio, expected):
    assert _audio_media_type(audio) == expected


def test_reference_audio_supports_external_termux_data_directory(tmp_path, monkeypatch):
    content_dir = tmp_path / "source"
    data_dir = tmp_path / "data"
    audio_path = data_dir / "themepacks" / "character" / "assets" / "ref_audio.ogg"
    audio_path.parent.mkdir(parents=True)
    audio_path.write_bytes(b"OggSreference")
    monkeypatch.setattr(settings, "CONTENT_DIR", content_dir)
    monkeypatch.setattr(settings, "DATA_DIR", data_dir)

    found, mime_type = tts_adapter.find_reference_audio("character")

    assert found == audio_path.resolve()
    assert mime_type == "audio/ogg"


@pytest.mark.asyncio
async def test_mimo_tts_sends_theme_audio_on_every_request(tmp_path, monkeypatch):
    content_dir = tmp_path / "source"
    data_dir = tmp_path / "data"
    reference = b"ID3theme-reference-audio"
    audio_path = content_dir / "themepacks" / "character" / "assets" / "ref_audio.mp3"
    audio_path.parent.mkdir(parents=True)
    audio_path.write_bytes(reference)
    monkeypatch.setattr(settings, "CONTENT_DIR", content_dir)
    monkeypatch.setattr(settings, "DATA_DIR", data_dir)
    captured = {}

    class FakeResponse:
        status_code = 200

        def json(self):
            return {
                "choices": [
                    {"message": {"audio": {"data": base64.b64encode(b"RIFF\0\0\0\0WAVEresult").decode("ascii")}}}
                ]
            }

    async def fake_post(url, timeout, **kwargs):
        captured["url"] = url
        captured["timeout"] = timeout
        captured.update(kwargs)
        return FakeResponse()

    monkeypatch.setattr(tts_adapter, "_post_with_network_fallback", fake_post)

    result = await tts_adapter._mimo_tts(
        "test-key",
        "https://mimo.example/v1",
        "mimo-v2.5-tts-voiceclone",
        "hello",
        "character",
    )

    voice = captured["json"]["audio"]["voice"]
    prefix, encoded = voice.split(",", 1)
    assert captured["url"] == "https://mimo.example/v1/chat/completions"
    assert prefix == "data:audio/mpeg;base64"
    assert base64.b64decode(encoded) == reference
    assert result.startswith(b"RIFF")


def test_reference_audio_error_identifies_theme_pack(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "CONTENT_DIR", tmp_path / "source")
    monkeypatch.setattr(settings, "DATA_DIR", tmp_path / "data")

    with pytest.raises(tts_adapter.TTSSynthesisError, match="character") as raised:
        tts_adapter.find_reference_audio("character")

    assert raised.value.status_code == 422


@pytest.mark.asyncio
async def test_tts_network_request_retries_without_environment_proxy(monkeypatch):
    attempts = []

    class FakeResponse:
        status_code = 200

    class FakeClient:
        def __init__(self, trust_env=True, **kwargs):
            self.trust_env = trust_env

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, **kwargs):
            attempts.append(self.trust_env)
            if self.trust_env:
                raise httpx.ConnectError("proxy unavailable", request=httpx.Request("POST", url))
            return FakeResponse()

    monkeypatch.setattr(tts_adapter.httpx, "AsyncClient", FakeClient)

    response = await tts_adapter._post_with_network_fallback(
        "https://tts.example/v1/audio/speech",
        timeout=10,
        json={"input": "hello"},
    )

    assert response.status_code == 200
    assert attempts == [True, False]


@pytest.mark.asyncio
async def test_openai_compatible_tts_uses_complete_api_key(monkeypatch):
    request = {}

    class FakeResponse:
        status_code = 200
        content = b"ID3audio"

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, **kwargs):
            request["url"] = url
            request.update(kwargs)
            return FakeResponse()

    monkeypatch.setattr(tts_adapter.httpx, "AsyncClient", lambda **kwargs: FakeClient())
    api_key = "full-secret-api-key-value"

    audio = await tts_adapter.synthesize(
        {
            "provider": "custom",
            "model": "tts-model",
            "api_key": api_key,
            "base_url": "https://tts.example/v1",
            "tts_endpoint": "/audio/speech",
        },
        "hello",
    )

    assert audio == b"ID3audio"
    assert request["headers"]["Authorization"] == f"Bearer {api_key}"
