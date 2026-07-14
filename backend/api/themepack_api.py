import json
import io
import zipfile
from pathlib import Path
from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from themepacks.manager import pack_manager

router = APIRouter()

class PackCreate(BaseModel):
    id: str
    name: str
    persona_ref: str = ""
    theme_ref: str = ""

class PackUpdate(BaseModel):
    name: str = ""

@router.get("/api/themepacks")
async def list_packs():
    return pack_manager.list_packs()

@router.get("/api/themepacks/{pack_id}")
async def get_pack(pack_id: str):
    pack = pack_manager.get_pack(pack_id)
    if not pack:
        raise HTTPException(404, f"Pack '{pack_id}' not found")
    return pack

@router.post("/api/themepacks")
async def create_pack(req: PackCreate):
    try:
        return pack_manager.create_pack(req.id, req.name, req.persona_ref, req.theme_ref)
    except ValueError as e:
        raise HTTPException(400, str(e))

@router.put("/api/themepacks/{pack_id}")
async def update_pack(pack_id: str, req: PackUpdate):
    try:
        return pack_manager.update_pack(pack_id, name=req.name)
    except ValueError as e:
        raise HTTPException(404, str(e))

@router.delete("/api/themepacks/{pack_id}")
async def delete_pack(pack_id: str):
    try:
        pack_manager.delete_pack(pack_id)
        return {"status": "ok"}
    except ValueError as e:
        raise HTTPException(400, str(e))

@router.get("/api/themepacks/{pack_id}/export")
async def export_pack(pack_id: str):
    pack_dir = pack_manager.get_pack_dir(pack_id)
    if not pack_dir.exists():
        raise HTTPException(404, f"Pack '{pack_id}' not found")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        for file_path in pack_dir.rglob('*'):
            if file_path.is_file():
                zf.write(file_path, file_path.relative_to(pack_dir))
    buffer.seek(0)
    return StreamingResponse(buffer, media_type='application/zip',
        headers={'Content-Disposition': f'attachment; filename="{pack_id}.zip"'})
