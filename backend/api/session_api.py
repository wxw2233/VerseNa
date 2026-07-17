from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from db.database import db
from api.log_api import log_info, log_error
import uuid

router = APIRouter()

class SessionCreate(BaseModel):
    name: str = ""

class SessionRename(BaseModel):
    name: str

@router.get("/api/sessions")
async def list_sessions():
    """获取所有会话列表，按 persona 分组"""
    rows = await db._db.execute(
        "SELECT session_id, MAX(persona) as persona, MAX(created_at) as last_msg, COUNT(*) as msg_count FROM conversations GROUP BY session_id ORDER BY last_msg DESC"
    )
    results = await rows.fetchall()
    sessions = []
    for r in results:
        sid = r["session_id"]
        meta = await db.get_session_meta(sid)
        sessions.append({
            "id": sid,
            "persona": r["persona"] or "default",
            "last_msg": r["last_msg"],
            "msg_count": r["msg_count"],
            "name": meta["name"],
            "theme_pack_id": meta["theme_pack_id"],
        })
    return sessions

class SessionUpdate(BaseModel):
    name: str = None
    theme_pack_id: str = None

@router.put("/api/sessions/{session_id}/rename")
async def rename_session(session_id: str, req: SessionRename):
    """重命名会话"""
    await db._db.execute(
        "UPDATE conversations SET session_id = ? WHERE session_id = ?",
        (req.name, session_id)
    )
    # 更新元数据
    meta = await db.get_session_meta(session_id)
    await db.set_session_meta(req.name, name=req.name, theme_pack_id=meta["theme_pack_id"])
    # 删除旧元数据
    await db._db.execute("DELETE FROM session_metadata WHERE session_id = ?", (session_id,))
    await db._db.commit()
    return {"status": "ok", "new_id": req.name}

@router.put("/api/sessions/{session_id}")
async def update_session(session_id: str, req: SessionUpdate):
    if req.name:
        await rename_session(session_id, SessionRename(name=req.name))
    if req.theme_pack_id:
        await db.set_session_meta(session_id, theme_pack_id=req.theme_pack_id)
    return {"status": "ok"}

@router.get("/api/sessions/{session_id}/history")
async def get_session_history(session_id: str, limit: int = 50):
    """获取指定会话的历史消息"""
    history = await db.get_history(session_id, limit)
    return history

@router.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str):
    """删除指定会话"""
    await db._db.execute("DELETE FROM conversations WHERE session_id = ?", (session_id,))
    await db._db.commit()
    return {"status": "ok"}

@router.post("/api/sessions")
async def create_session(req: SessionCreate):
    """创建新会话，返回 session_id"""
    new_id = req.name if req.name else f"session_{uuid.uuid4().hex[:8]}"
    return {"session_id": new_id}


@router.post("/api/sessions/{session_id}/auto-title")
async def auto_title(session_id: str, req: dict):
    """根据首句对话自动生成标题"""
    user_msg = req.get("user_message", "")[:100]
    assistant_msg = req.get("assistant_message", "")[:100]
    if not user_msg:
        return {"status": "skip"}

    # 检查当前名称是否还是 session_id（未手动改过）
    meta = await db.get_session_meta(session_id)
    if meta.get("name") and meta["name"] != session_id:
        return {"status": "already_named", "name": meta["name"]}

    try:
        from agent.models.openai_adapter import OpenAIAdapter
        from config import settings
        adapter = OpenAIAdapter(
            api_key=settings.DEFAULT_API_KEY,
            base_url=settings.DEFAULT_API_BASE,
            model_name=settings.DEFAULT_MODEL_NAME
        )
        prompt = f"给以下对话起一个简短的中文标题（10字以内），只返回标题，不要其他内容：\n用户：{user_msg}\n助手：{assistant_msg}"
        import asyncio

        async def get_title():
            async for chunk in adapter.chat([{"role": "user", "content": prompt}], stream=False):
                return chunk.content.strip().strip('"').strip("'").replace("\n", "")[:20]

        title = await asyncio.wait_for(get_title(), timeout=10)
        if title:
            await db.set_session_meta(session_id, name=title)
            log_info("Session", f"自动命名: {session_id} -> {title}")
            return {"status": "ok", "name": title}
    except Exception as e:
        log_error("Session", f"自动命名失败: {e}")

    return {"status": "skip"}
