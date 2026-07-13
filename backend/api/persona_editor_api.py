import json
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()
PERSONAS_DIR = Path(__file__).parent.parent.parent / "personas"


class PersonaCreate(BaseModel):
    id: str
    name: str
    description: str = ""
    prompt: str = ""
    emotion_weights: dict = {"cheerful": 0.5, "shy": 0.2, "curious": 0.5, "angry": 0.1, "sad": 0.1}
    speech_style: dict = {"tone": "友好", "catchphrase": "", "emoji_frequency": "medium", "formality": "casual"}
    theme_binding: str = "default"


@router.post("/api/personas/create")
async def create_persona(req: PersonaCreate):
    persona_dir = PERSONAS_DIR / req.id
    if persona_dir.exists():
        raise HTTPException(400, f"Persona '{req.id}' already exists")
    persona_dir.mkdir(parents=True, exist_ok=True)
    config = {
        "name": req.name,
        "version": "1.0.0",
        "description": req.description,
        "emotion_weights": req.emotion_weights,
        "speech_style": req.speech_style,
        "memory_config": {"max_context_tokens": 4096, "summary_threshold": 3000, "dedicated_memory": True},
        "theme_binding": req.theme_binding,
    }
    (persona_dir / "persona.json").write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    (persona_dir / "prompt.md").write_text(req.prompt, encoding="utf-8")
    return {"status": "ok", "id": req.id}


@router.put("/api/personas/{persona_id}")
async def update_persona(persona_id: str, req: PersonaCreate):
    persona_dir = PERSONAS_DIR / persona_id
    if not persona_dir.exists():
        raise HTTPException(404, f"Persona '{persona_id}' not found")
    config = {
        "name": req.name,
        "version": "1.0.0",
        "description": req.description,
        "emotion_weights": req.emotion_weights,
        "speech_style": req.speech_style,
        "memory_config": {"max_context_tokens": 4096, "summary_threshold": 3000, "dedicated_memory": True},
        "theme_binding": req.theme_binding,
    }
    (persona_dir / "persona.json").write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    (persona_dir / "prompt.md").write_text(req.prompt, encoding="utf-8")
    # 清除缓存
    from persona.manager import persona_manager
    persona_manager.reload(persona_id)
    return {"status": "ok"}


@router.delete("/api/personas/{persona_id}")
async def delete_persona(persona_id: str):
    persona_dir = PERSONAS_DIR / persona_id
    if not persona_dir.exists():
        raise HTTPException(404, f"Persona '{persona_id}' not found")
    if persona_id == "default":
        raise HTTPException(400, "Cannot delete default persona")
    import shutil
    shutil.rmtree(persona_dir)
    from persona.manager import persona_manager
    persona_manager.reload(persona_id)
    return {"status": "ok"}


@router.get("/api/personas/{persona_id}/full")
async def get_persona_full(persona_id: str):
    persona_dir = PERSONAS_DIR / persona_id
    config_path = persona_dir / "persona.json"
    prompt_path = persona_dir / "prompt.md"
    if not config_path.exists():
        raise HTTPException(404, f"Persona '{persona_id}' not found")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    prompt = prompt_path.read_text(encoding="utf-8") if prompt_path.exists() else ""
    return {"id": persona_id, "config": config, "prompt": prompt}
