import uuid
from pathlib import Path
from fastapi import APIRouter, UploadFile, File
from config import settings

router = APIRouter()
UPLOAD_DIR = settings.DATA_DIR / "uploads"

@router.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    ext = Path(file.filename).suffix
    saved_name = f"{uuid.uuid4().hex}{ext}"
    saved_path = UPLOAD_DIR / saved_name
    content = await file.read()
    saved_path.write_bytes(content)

    from multimodal.file_parser import FileParser
    text = FileParser.parse(str(saved_path))
    return {"filename": file.filename, "saved_as": saved_name, "text_preview": text[:500], "full_text": text}
