from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from skills.manager import skill_manager

router = APIRouter()


class SkillInstallReq(BaseModel):
    url: str


@router.get("/api/skills")
async def list_skills():
    return skill_manager.list_skills()


@router.get("/api/skills/{skill_id}")
async def get_skill(skill_id: str):
    skill = skill_manager.get_skill(skill_id)
    if not skill:
        raise HTTPException(404, f"技能 '{skill_id}' 不存在")
    return skill


@router.post("/api/skills/install")
async def install_skill(req: SkillInstallReq):
    data, error = skill_manager.install_from_github(req.url)
    if error:
        raise HTTPException(400, error)
    return {"status": "ok", "skill": data}


@router.delete("/api/skills/{skill_id}")
async def delete_skill(skill_id: str):
    try:
        skill_manager.delete_skill(skill_id)
        return {"status": "ok"}
    except ValueError as e:
        raise HTTPException(400, str(e))
