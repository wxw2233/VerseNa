import pytest
from agent.memory import MemoryManager

def test_estimate_tokens():
    mm = MemoryManager()
    messages = [{"role": "user", "content": "你好啊"}]
    tokens = mm._estimate_tokens(messages)
    assert tokens > 0
    assert tokens < 10

def test_estimate_tokens_empty():
    mm = MemoryManager()
    assert mm._estimate_tokens([]) == 0
