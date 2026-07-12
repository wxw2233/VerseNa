import pytest
from agent.models.base import BaseModelAdapter, ModelResponse

def test_model_response_dataclass():
    r = ModelResponse(content="hello")
    assert r.content == "hello"
    assert r.tool_calls == []
    assert r.finish_reason == "stop"

def test_openai_adapter_init():
    from agent.models.openai_adapter import OpenAIAdapter
    adapter = OpenAIAdapter(api_key="test", base_url="https://api.openai.com/v1", model_name="gpt-4")
    assert adapter.model_name == "gpt-4"
    assert adapter.base_url == "https://api.openai.com/v1"
