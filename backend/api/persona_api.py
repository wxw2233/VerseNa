from fastapi import APIRouter, HTTPException
from persona.manager import persona_manager

router = APIRouter()

@router.get("/api/personas")
async def list_personas():
    return persona_manager.list_personas()

@router.get("/api/personas/{name}")
async def get_persona(name: str):
    try:
        persona = persona_manager.get_persona(name)
        return {
            "name": persona.name,
            "config": persona.config,
            "prompt_preview": persona.prompt[:200],
            "theme_binding": persona.theme_binding,
        }
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Persona '{name}' not found")
