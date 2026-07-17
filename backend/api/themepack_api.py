import json
import io
import zipfile
from pathlib import Path
from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Any, Optional
from themepacks.manager import pack_manager

router = APIRouter()

class PackCreate(BaseModel):
    id: str
    name: str
    persona_ref: str = ""
    theme_ref: str = ""

class PackUpdate(BaseModel):
    name: Optional[str] = None
    character: Optional[dict] = None
    theme: Optional[dict] = None

@router.get("/api/themepacks")
async def list_packs():
    return pack_manager.list_packs()

@router.get("/api/themepacks/{pack_id}")
async def get_pack(pack_id: str):
    pack_dir = pack_manager.get_pack_dir(pack_id)
    if not pack_dir.exists():
        raise HTTPException(404, f"Pack '{pack_id}' not found")
    result = {}
    # 读 pack.json
    pack_json = pack_dir / "pack.json"
    if pack_json.exists():
        result.update(json.loads(pack_json.read_text(encoding="utf-8")))
    # 读 persona
    persona_json = pack_dir / "persona.json"
    if persona_json.exists():
        result["character"] = json.loads(persona_json.read_text(encoding="utf-8"))
    prompt_md = pack_dir / "prompt.md"
    if prompt_md.exists() and "character" in result:
        result["character"]["prompt"] = prompt_md.read_text(encoding="utf-8")
    # 读 theme
    theme_json = pack_dir / "theme.json"
    if theme_json.exists():
        result["theme"] = json.loads(theme_json.read_text(encoding="utf-8"))
    vars_css = pack_dir / "variables.css"
    if vars_css.exists():
        result["variables_css"] = vars_css.read_text(encoding="utf-8")
    # assets 列表
    assets_dir = pack_dir / "assets"
    if assets_dir.exists():
        result["assets_list"] = [f.name for f in assets_dir.iterdir() if f.is_file()]
    return result

@router.post("/api/themepacks")
async def create_pack(req: PackCreate):
    try:
        return pack_manager.create_pack(req.id, req.name, req.persona_ref, req.theme_ref)
    except ValueError as e:
        raise HTTPException(400, str(e))

@router.put("/api/themepacks/{pack_id}")
async def update_pack(pack_id: str, req: PackUpdate):
    pack_dir = pack_manager.get_pack_dir(pack_id)
    if not pack_dir.exists():
        raise HTTPException(404, f"Pack '{pack_id}' not found")

    # 更新 pack.json 中的 name
    if req.name is not None:
        pack_json = pack_dir / "pack.json"
        if pack_json.exists():
            pack_data = json.loads(pack_json.read_text(encoding="utf-8"))
            pack_data["name"] = req.name
            pack_json.write_text(json.dumps(pack_data, ensure_ascii=False, indent=2), encoding="utf-8")

    # 更新角色配置
    if req.character is not None:
        import shutil
        char = dict(req.character)
        prompt = char.pop("prompt", None)
        if prompt is not None:
            (pack_dir / "prompt.md").write_text(prompt, encoding="utf-8")
        (pack_dir / "persona.json").write_text(
            json.dumps(char, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        # 同步到 personas/{pack_id}/
        persona_dest = Path(__file__).parent.parent.parent / "personas" / pack_id
        persona_dest.mkdir(parents=True, exist_ok=True)
        for f in ["persona.json", "prompt.md"]:
            src = pack_dir / f
            if src.exists():
                shutil.copy2(src, persona_dest / f)
        # 更新 persona_ref
        if pack_json.exists():
            pd = json.loads(pack_json.read_text(encoding="utf-8"))
            pd["persona_ref"] = pack_id
            pack_json.write_text(json.dumps(pd, ensure_ascii=False, indent=2), encoding="utf-8")

    # 更新主题配置
    if req.theme is not None:
        import shutil as _shutil
        theme_data = dict(req.theme)
        colors = theme_data.pop("colors", {})
        fonts = theme_data.pop("fonts", {})
        spacing = theme_data.pop("spacing", {})

        # 写 theme.json
        theme_json_path = pack_dir / "theme.json"
        if theme_json_path.exists():
            existing = json.loads(theme_json_path.read_text(encoding="utf-8"))
        else:
            existing = {"name": "Custom", "version": "1.0.0"}
        if "name" in theme_data:
            existing["name"] = theme_data["name"]
        if colors:
            existing.setdefault("colors", {}).update(colors)
        theme_json_path.write_text(
            json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        # 写 variables.css
        css_vars = []
        css_map = {
            "primary": "--primary",
            "bgPrimary": "--bg-primary",
            "bgSecondary": "--bg-secondary",
            "textPrimary": "--text-primary",
            "textSecondary": "--text-secondary",
            "border": "--border",
            "bubbleUser": "--bubble-user",
            "bubbleAgent": "--bubble-agent",
        }
        for key, css_var in css_map.items():
            if key in colors:
                css_vars.append(f"  {css_var}: {colors[key]};")
        font_map = {
            "family": "--font-family",
            "sizeBase": ("--font-size-base", "px"),
            "sizeSmall": ("--font-size-small", "px"),
            "lineHeight": ("--line-height", ""),
        }
        for key, val in font_map.items():
            if key in fonts:
                if isinstance(val, tuple):
                    css_vars.append(f"  {val[0]}: {fonts[key]}{val[1]};")
                else:
                    css_vars.append(f"  {val}: {fonts[key]};")
        # spacing 已在 T2 中移除，不再生成 CSS 变量
        spacing = spacing

        if css_vars:
            (pack_dir / "variables.css").write_text(
                ":root {\n" + "\n".join(css_vars) + "\n}\n", encoding="utf-8"
            )

    return {"status": "ok"}

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

@router.post("/api/themepacks/import")
async def import_pack(file: UploadFile = File(...)):
    import tempfile, shutil
    content = await file.read()
    buffer = io.BytesIO(content)
    with zipfile.ZipFile(buffer, 'r') as zf:
        # 找到 pack.json 来确定 id
        pack_json_name = None
        for name in zf.namelist():
            if name.endswith('pack.json'):
                pack_json_name = name
                break
        if not pack_json_name:
            raise HTTPException(400, "Invalid theme pack: no pack.json found")
        pack_data = json.loads(zf.read(pack_json_name))
        pack_id = pack_data.get('id', 'imported_' + str(int(__import__('time').time())))
        pack_dir = pack_manager.get_pack_dir(pack_id)
        if pack_dir.exists():
            shutil.rmtree(pack_dir)
        zf.extractall(pack_dir)
    return {"status": "ok", "id": pack_id}

@router.post("/api/themepacks/{pack_id}/apply")
async def apply_pack_to_sessions(pack_id: str):
    pack_dir = pack_manager.get_pack_dir(pack_id)
    if not pack_dir.exists():
        raise HTTPException(404, f"Pack '{pack_id}' not found")
    # 复制 pack 内容到 personas/ 和 themes/
    import shutil
    pack_json = pack_dir / "pack.json"
    if not pack_json.exists():
        raise HTTPException(400, "Invalid pack")
    pack_data = json.loads(pack_json.read_text(encoding="utf-8"))
    persona_ref = pack_data.get("persona_ref", "")
    theme_ref = pack_data.get("theme_ref", "")
    # 更新 persona
    if persona_ref:
        persona_dest = Path(__file__).parent.parent.parent / "personas" / persona_ref
        persona_dest.mkdir(parents=True, exist_ok=True)
        for f in ["persona.json", "prompt.md"]:
            src = pack_dir / f
            if src.exists():
                shutil.copy2(src, persona_dest / f)
    # 更新 theme
    if theme_ref:
        theme_dest = Path(__file__).parent.parent.parent / "themes" / theme_ref
        theme_dest.mkdir(parents=True, exist_ok=True)
        for f in ["theme.json", "variables.css"]:
            src = pack_dir / f
            if src.exists():
                shutil.copy2(src, theme_dest / f)
        assets_src = pack_dir / "assets"
        if assets_src.exists():
            assets_dest = theme_dest / "assets"
            assets_dest.mkdir(exist_ok=True)
            for f in assets_src.iterdir():
                if f.is_file():
                    shutil.copy2(f, assets_dest / f.name)
    return {"status": "ok", "persona": persona_ref, "theme": theme_ref}
