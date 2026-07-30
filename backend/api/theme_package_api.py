import io
import json
import zipfile
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse
from config import settings

router = APIRouter()
THEMES_DIR = settings.CONTENT_DIR / "themes"

@router.get("/api/themes/{theme_id}/export")
async def export_theme(theme_id: str):
    """导出主题为 zip 文件"""
    theme_dir = THEMES_DIR / theme_id
    if not theme_dir.exists():
        raise HTTPException(404, f"Theme '{theme_id}' not found")
    
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        for file_path in theme_dir.rglob('*'):
            if file_path.is_file():
                arcname = str(file_path.relative_to(theme_dir))
                zf.write(file_path, arcname)
    
    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type='application/zip',
        headers={'Content-Disposition': f'attachment; filename="{theme_id}-theme.zip"'}
    )

@router.post("/api/themes/import")
async def import_theme(file: UploadFile = File(...)):
    """导入主题包（zip 文件）"""
    if not file.filename.endswith('.zip'):
        raise HTTPException(400, "Only .zip files are supported")
    
    content = await file.read()
    buffer = io.BytesIO(content)
    
    try:
        with zipfile.ZipFile(buffer, 'r') as zf:
            # 检查是否有 theme.json
            names = zf.namelist()
            has_theme_json = any(n.endswith('theme.json') for n in names)
            if not has_theme_json:
                raise HTTPException(400, "Invalid theme package: missing theme.json")
            
            # 从 theme.json 读取主题 ID
            for name in names:
                if name.endswith('theme.json') and '/' not in name:
                    config = json.loads(zf.read(name))
                    theme_id = config.get('name', '').lower().replace(' ', '_')
                    break
            else:
                # theme.json 在子目录，用文件名作为 ID
                theme_id = file.filename.replace('-theme.zip', '').replace('.zip', '')
            
            # 检查是否已存在
            target_dir = THEMES_DIR / theme_id
            if target_dir.exists():
                # 加后缀
                counter = 1
                while target_dir.exists():
                    target_dir = THEMES_DIR / f"{theme_id}_{counter}"
                    counter += 1
            
            # 解压
            target_dir.mkdir(parents=True, exist_ok=True)
            zf.extractall(target_dir)
            
            # 如果解压后有一个子目录，把内容移到外层
            items = list(target_dir.iterdir())
            if len(items) == 1 and items[0].is_dir():
                # 移动子目录内容到 target_dir
                subdir = items[0]
                for item in subdir.iterdir():
                    item.rename(target_dir / item.name)
                subdir.rmdir()
            
            return {"status": "ok", "theme_id": target_dir.name}
    
    except zipfile.BadZipFile:
        raise HTTPException(400, "Invalid zip file")

@router.post("/api/themes/import/bundle")
async def import_theme_bundle(file: UploadFile = File(...)):
    """导入主题包，如果包含 bundled_persona 则自动创建 persona"""
    result = await import_theme(file)
    theme_id = result["theme_id"]
    
    # 检查 bundled_persona
    theme_json = THEMES_DIR / theme_id / "theme.json"
    if theme_json.exists():
        config = json.loads(theme_json.read_text(encoding="utf-8"))
        bundled = config.get("bundled_persona")
        if bundled:
            persona_id = bundled.get("id", theme_id)
            persona_dir = THEMES_DIR.parent / "personas" / persona_id
            if not persona_dir.exists():
                persona_dir.mkdir(parents=True, exist_ok=True)
                persona_config = {
                    "name": bundled.get("name", persona_id),
                    "version": "1.0.0",
                    "description": bundled.get("description", ""),
                    "emotion_weights": bundled.get("emotion_weights", {}),
                    "speech_style": bundled.get("speech_style", {}),
                    "memory_config": {"max_context_tokens": 4096, "summary_threshold": 3000, "dedicated_memory": True},
                    "theme_binding": theme_id,
                }
                (persona_dir / "persona.json").write_text(json.dumps(persona_config, ensure_ascii=False, indent=2), encoding="utf-8")
                (persona_dir / "prompt.md").write_text(bundled.get("prompt", ""), encoding="utf-8")
                result["persona_created"] = persona_id
    
    return result
