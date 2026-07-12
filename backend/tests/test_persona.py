import pytest
from persona.loader import PersonaLoader, PersonaData
from persona.emotion import EmotionEngine
from persona.manager import PersonaManager

def test_load_default_persona():
    persona = PersonaLoader.load("default")
    assert persona.name == "default"
    assert "助手" in persona.config["name"]
    assert len(persona.prompt) > 0

def test_list_personas():
    personas = PersonaLoader.list_all()
    assert len(personas) >= 1
    assert personas[0]["id"] == "default"

def test_build_system_prompt():
    persona = PersonaLoader.load("default")
    prompt = PersonaLoader.build_system_prompt(persona)
    assert "说话风格" in prompt

def test_emotion_engine():
    weights = {"cheerful": 0.8, "shy": 0.2}
    engine = EmotionEngine(weights)
    state = engine.pick_emotion()
    assert state.primary in ["cheerful", "shy"]
    assert len(state.emoji) > 0

def test_persona_manager():
    pm = PersonaManager()
    persona = pm.get_persona("default")
    assert persona is not None
    prompt = pm.get_system_prompt("default")
    assert len(prompt) > 0
