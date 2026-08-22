from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from db.database import db
from api.log_api import log_info, log_error
from config import settings
from pathlib import Path
import os
import string
import uuid

from skills.manager import skill_manager

router = APIRouter()
MAX_ACTIVE_SKILL_ARGUMENTS = 4000

class SessionCreate(BaseModel):
    name: str = ""
    theme_pack_id: str = None

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


class ToolSettingsUpdate(BaseModel):
    tool_workspace: str = None
    approval_mode: str = None


class SkillStateUpdate(BaseModel):
    active_command: str = None
    arguments: str = None


class DirectoryCreate(BaseModel):
    parent: str
    name: str


def _directory_roots():
    if os.name == "nt":
        return [
            Path(f"{letter}:\\")
            for letter in string.ascii_uppercase
            if Path(f"{letter}:\\").exists()
        ]
    roots = [Path("/"), Path.home().resolve()]
    return list(dict.fromkeys(roots))

@router.put("/api/sessions/{session_id}/rename")
async def rename_session(session_id: str, req: SessionRename):
    """重命名会话"""
    await db._db.execute(
        "UPDATE conversations SET session_id = ? WHERE session_id = ?",
        (req.name, session_id)
    )
    # 更新元数据
    meta = await db.get_session_meta(session_id)
    await db.set_session_meta(
        req.name,
        name=req.name,
        theme_pack_id=meta["theme_pack_id"],
        tool_workspace=meta["tool_workspace"],
        approval_mode=meta["approval_mode"],
        active_skill_command=meta["active_skill_command"],
        active_skill_arguments=meta["active_skill_arguments"],
        task_checkpoint=meta["task_checkpoint"],
    )
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


@router.get("/api/sessions/{session_id}/tool-settings")
async def get_session_tool_settings(session_id: str):
    meta = await db.get_session_meta(session_id)
    configured = meta.get("tool_workspace", "")
    workspace = Path(configured or settings.TOOL_WORKSPACE).expanduser().resolve()
    return {
        "tool_workspace": configured,
        "effective_workspace": str(workspace),
        "approval_mode": meta.get("approval_mode", "ask"),
        "is_default": not bool(configured),
    }


@router.put("/api/sessions/{session_id}/tool-settings")
async def update_session_tool_settings(session_id: str, req: ToolSettingsUpdate):
    updates = {}
    if req.tool_workspace is not None:
        raw_path = req.tool_workspace.strip()
        if raw_path:
            workspace = Path(raw_path).expanduser().resolve()
            if not workspace.exists():
                raise HTTPException(400, "工作目录不存在")
            if not workspace.is_dir():
                raise HTTPException(400, "工作目录必须是文件夹")
            updates["tool_workspace"] = str(workspace)
        else:
            updates["tool_workspace"] = ""
    if req.approval_mode is not None:
        if req.approval_mode not in {"ask", "auto"}:
            raise HTTPException(400, "审批模式必须是 ask 或 auto")
        updates["approval_mode"] = req.approval_mode
    await db.set_session_meta(session_id, **updates)
    return await get_session_tool_settings(session_id)


def _skill_state_payload(command_name: str, arguments: str = ""):
    command = skill_manager.get_command(command_name)
    if not command:
        return {"active": False, "command": "", "arguments": ""}
    return {
        "active": True,
        "command": command["command"],
        "skill_id": command["skill_id"],
        "skill_name": command["skill_name"],
        "description": command.get("description", ""),
        "arguments": arguments or "",
    }


@router.get("/api/sessions/{session_id}/skill-state")
async def get_session_skill_state(session_id: str):
    meta = await db.get_session_meta(session_id)
    state = _skill_state_payload(
        meta.get("active_skill_command", ""),
        meta.get("active_skill_arguments", ""),
    )
    if meta.get("active_skill_command") and not state["active"]:
        await db.set_session_meta(
            session_id,
            active_skill_command="",
            active_skill_arguments="",
        )
        try:
            await db.record_skill_event(
                session_id,
                "unknown",
                "cleared",
                command=meta.get("active_skill_command", ""),
                detail="已移除的技能指令自动清理",
            )
        except Exception:
            pass
    return state


@router.put("/api/sessions/{session_id}/skill-state")
async def update_session_skill_state(session_id: str, req: SkillStateUpdate):
    command_name = (req.active_command or "").strip().lstrip("/")
    arguments = (req.arguments or "").strip()[:MAX_ACTIVE_SKILL_ARGUMENTS]
    if not command_name:
        previous = await db.get_session_meta(session_id)
        await db.set_session_meta(
            session_id,
            active_skill_command="",
            active_skill_arguments="",
        )
        previous_state = _skill_state_payload(previous.get("active_skill_command", ""))
        try:
            await db.record_skill_event(
                session_id,
                previous_state.get("skill_id") or "unknown",
                "cleared",
                command=previous.get("active_skill_command", ""),
                detail="用户关闭当前活动技能",
            )
        except Exception:
            pass
        return _skill_state_payload("")

    command = skill_manager.get_command(command_name)
    if not command:
        raise HTTPException(404, "技能指令不存在或已被移除")
    await db.set_session_meta(
        session_id,
        active_skill_command=command["command"],
        active_skill_arguments=arguments,
    )
    try:
        await db.record_skill_event(
            session_id,
            command["skill_id"],
            "loaded",
            command=command["command"],
            detail="由会话技能面板加载",
        )
        await db.record_skill_event(
            session_id,
            command["skill_id"],
            "activated",
            command=command["command"],
            detail="由会话技能面板激活",
        )
    except Exception:
        pass
    return _skill_state_payload(command["command"], arguments)


@router.get("/api/tools/directories")
async def browse_tool_directories(path: str = ""):
    current = Path(path).expanduser().resolve() if path else Path.home().resolve()
    if not current.exists():
        raise HTTPException(404, "目录不存在")
    if not current.is_dir():
        raise HTTPException(400, "路径必须是文件夹")
    try:
        directories = sorted(
            (entry for entry in current.iterdir() if entry.is_dir()),
            key=lambda entry: entry.name.lower(),
        )
    except PermissionError:
        raise HTTPException(403, "没有权限浏览此目录")
    except OSError as exc:
        raise HTTPException(400, f"无法浏览目录: {exc}")

    parent = current.parent if current.parent != current else None
    return {
        "current": str(current),
        "parent": str(parent) if parent else None,
        "directories": [
            {"name": entry.name, "path": str(entry)}
            for entry in directories[:500]
        ],
        "truncated": len(directories) > 500,
        "roots": [
            {"name": str(root), "path": str(root)}
            for root in _directory_roots()
        ],
    }


@router.post("/api/tools/directories", status_code=201)
async def create_tool_directory(req: DirectoryCreate):
    parent = Path(req.parent).expanduser().resolve()
    name = req.name.strip()

    if not parent.exists():
        raise HTTPException(404, "父目录不存在")
    if not parent.is_dir():
        raise HTTPException(400, "父路径必须是文件夹")
    if not name or name in {".", ".."} or any(char in name for char in '/\\'):
        raise HTTPException(400, "文件夹名称无效")

    directory = parent / name
    try:
        directory.mkdir()
    except FileExistsError:
        raise HTTPException(409, "同名文件或文件夹已存在")
    except PermissionError:
        raise HTTPException(403, "没有权限在此目录中新建文件夹")
    except OSError as exc:
        raise HTTPException(400, f"无法新建文件夹: {exc}")

    return {"name": directory.name, "path": str(directory.resolve())}

@router.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str):
    """删除指定会话"""
    await db._db.execute("DELETE FROM conversations WHERE session_id = ?", (session_id,))
    await db._db.execute("DELETE FROM session_metadata WHERE session_id = ?", (session_id,))
    await db._db.commit()
    return {"status": "ok"}

@router.post("/api/sessions")
async def create_session(req: SessionCreate):
    """创建新会话，返回 session_id"""
    new_id = req.name if req.name else f"session_{uuid.uuid4().hex[:8]}"
    # 保存主题包关联
    if req.theme_pack_id:
        await db.set_session_meta(new_id, theme_pack_id=req.theme_pack_id)
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
