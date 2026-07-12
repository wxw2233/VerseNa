from .loader import PersonaLoader, PersonaData
from .emotion import EmotionEngine

class PersonaManager:
    def __init__(self):
        self._cache: dict[str, PersonaData] = {}

    def get_persona(self, name: str = "default") -> PersonaData:
        if name not in self._cache:
            self._cache[name] = PersonaLoader.load(name)
        return self._cache[name]

    def list_personas(self) -> list[dict]:
        return PersonaLoader.list_all()

    def get_system_prompt(self, name: str = "default") -> str:
        persona = self.get_persona(name)
        return PersonaLoader.build_system_prompt(persona)

    def get_emotion_engine(self, name: str = "default") -> EmotionEngine:
        persona = self.get_persona(name)
        return EmotionEngine(persona.emotion_weights)

    def reload(self, name: str = None):
        if name:
            self._cache.pop(name, None)
        else:
            self._cache.clear()

persona_manager = PersonaManager()
