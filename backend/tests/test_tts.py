import httpx
import pytest

from api.tts_api import _audio_media_type
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
