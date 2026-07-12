import pytest
import pytest_asyncio
from agent.react import ReActAgent
from agent.models.base import BaseModelAdapter, ModelResponse
from agent.memory import MemoryManager
from db.database import db
from typing import AsyncGenerator

class MockAdapter(BaseModelAdapter):
    def __init__(self, responses):
        self.responses = responses
        self.call_count = 0

    async def chat(self, messages, tools=None, stream=True) -> AsyncGenerator:
        resp = self.responses[self.call_count]
        self.call_count += 1
        yield ModelResponse(content=resp)

    async def list_models(self):
        return ["mock-model"]

@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    """Initialize in-memory database for tests."""
    db.db_path = ":memory:"
    await db.connect()
    yield
    await db.close()

@pytest.mark.asyncio
async def test_react_simple_response():
    adapter = MockAdapter(["你好！我是次元人格。"])
    memory = MemoryManager()
    agent = ReActAgent(adapter, memory)

    results = []
    async for event in agent.run("test-session", "你好"):
        results.append(event)

    answers = [r for r in results if r["type"] == "answer"]
    assert len(answers) > 0
    assert "你好" in "".join(r["content"] for r in answers)
