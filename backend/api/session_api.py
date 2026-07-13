from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from db.database import db
import uuid

router = APIRouter()

class SessionCreate(BaseModel):
    name: str = ""

@router.get("/api/sessions")
async def list_sessions():
    """获取所有会话列表"""
    rows = await db._db.execute(
        "SELECT DISTINCT session_id, MAX(created_at) as last_msg, COUNT(*) as msg_count FROM conversations GROUP BY session_id ORDER BY last_msg DESC"
    )
    results = await rows.fetchall()
    return [{"id": r["session_id"], "last_msg": r["last_msg"], "msg_count": r["msg_count"]} for r in results]

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
