import asyncio

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from skills.manager import skill_manager
from security_utils import redact_sensitive_text

router = APIRouter()


class SkillInstallReq(BaseModel):
    url: str


@router.get("/api/skills")
async def list_skills():
    return skill_manager.list_skills()


@router.get("/api/skills/status")
async def skill_status():
    return skill_manager.diagnostics()


@router.get("/api/skills/commands")
async def list_skill_commands():
    return [
        {
            "command": "compact",
            "name": "上下文压缩",
            "description": "手动整理当前会话的旧上下文，保留最近工作记录",
            "skill_id": "builtin",
            "skill_name": "VerseNa 内置指令",
            "source": "builtin",
            "aliases": [],
        },
        *skill_manager.list_commands(),
    ]


@router.get("/api/skills/{skill_id}")
async def get_skill(skill_id: str):
    skill = skill_manager.get_skill(skill_id)
    if not skill:
        raise HTTPException(404, f"技能 '{skill_id}' 不存在")
    return skill


@router.post("/api/skills/install")
async def install_skill(req: SkillInstallReq):
    data, error = await asyncio.to_thread(skill_manager.install_from_github, req.url)
    if error:
        raise HTTPException(400, redact_sensitive_text(error))
    return {"status": "ok", "skill": data}


@router.delete("/api/skills/{skill_id}")
async def delete_skill(skill_id: str):
    try:
        await asyncio.to_thread(skill_manager.delete_skill, skill_id)
        return {"status": "ok"}
    except ValueError as e:
        raise HTTPException(400, redact_sensitive_text(e))
