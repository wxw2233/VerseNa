import uuid
import base64
from pathlib import Path
from fastapi import APIRouter, UploadFile, File
from config import settings

router = APIRouter()
UPLOAD_DIR = settings.DATA_DIR / "uploads"

IMAGE_TYPES = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg"}


@router.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    ext = Path(file.filename).suffix.lower()
    saved_name = f"{uuid.uuid4().hex}{ext}"
    saved_path = UPLOAD_DIR / saved_name
    content = await file.read()
    saved_path.write_bytes(content)

    # 图片文件：返回 base64 data URL
    if ext in IMAGE_TYPES:
        mime_map = {
            ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".png": "image/png", ".gif": "image/gif",
            ".webp": "image/webp", ".bmp": "image/bmp",
            ".svg": "image/svg+xml",
        }
        mime = mime_map.get(ext, "image/jpeg")
        b64 = base64.b64encode(content).decode("utf-8")
        data_url = f"data:{mime};base64,{b64}"
        return {
            "filename": file.filename,
            "saved_as": saved_name,
            "text_preview": f"[图片: {file.filename}]",
            "full_text": f"[图片: {file.filename}]",
            "is_image": True,
            "image_url": f"/api/uploads/{saved_name}",
            "image_data_url": data_url,
            "mime": mime,
        }

    # 文本/文档文件：解析文本
    from multimodal.file_parser import FileParser
    text = FileParser.parse(str(saved_path))
    return {
        "filename": file.filename,
        "saved_as": saved_name,
        "text_preview": text[:500],
        "full_text": text,
        "is_image": False,
    }


@router.get("/api/uploads/{filename}")
async def get_upload(filename: str):
    """获取已上传的文件"""
    from fastapi.responses import FileResponse
    file_path = UPLOAD_DIR / filename
    if not file_path.exists():
        from fastapi import HTTPException
        raise HTTPException(404, "文件不存在")
    return FileResponse(str(file_path))
