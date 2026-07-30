import json
from pathlib import Path
from config import settings

PERSONAS_DIR = settings.CONTENT_DIR / "personas"

class PersonaData:
    def __init__(self, name: str, config: dict, prompt: str):
        self.name = name
        self.config = config
        self.prompt = prompt
        self.emotion_weights = config.get("emotion_weights", {})
        self.speech_style = config.get("speech_style", {})
        self.theme_binding = config.get("theme_binding", "default")
        self.temperature = config.get("temperature", 0.8)
        self.top_p = config.get("top_p", 0.9)

class PersonaLoader:
    @staticmethod
    def load(name: str) -> PersonaData:
        persona_dir = PERSONAS_DIR / name
        config_path = persona_dir / "persona.json"
        prompt_path = persona_dir / "prompt.md"

        if not config_path.exists():
            raise FileNotFoundError(f"Persona '{name}' not found at {persona_dir}")

        config = json.loads(config_path.read_text(encoding="utf-8"))
        prompt = prompt_path.read_text(encoding="utf-8") if prompt_path.exists() else ""
        return PersonaData(name=name, config=config, prompt=prompt)

    @staticmethod
    def list_all() -> list[dict]:
        result = []
        if not PERSONAS_DIR.exists():
            return result
        for d in PERSONAS_DIR.iterdir():
            config_path = d / "persona.json"
            if d.is_dir() and config_path.exists():
                config = json.loads(config_path.read_text(encoding="utf-8"))
                result.append({"id": d.name, "name": config.get("name", d.name), "description": config.get("description", "")})
        return result

    @staticmethod
    def build_system_prompt(persona: PersonaData) -> str:
        parts = [persona.prompt]
        style = persona.speech_style
        if style:
            parts.append(f"\n\n## 说话风格\n- 语气: {style.get('tone', '自然')}")
            if style.get("catchphrase"):
                parts.append(f"- 口头禅: {style['catchphrase']}")
            parts.append(f"- 表情使用频率: {style.get('emoji_frequency', 'medium')}")
        return "\n".join(parts)
