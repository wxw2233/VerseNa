import json
import io
import zipfile
from pathlib import Path
from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Any, Optional
from themepacks.manager import pack_manager
from config import settings

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
        persona_dest = settings.CONTENT_DIR / "personas" / pack_id
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
            "highlight": "--highlight",
            "textPrimary": "--text-primary",
            "textSecondary": "--text-secondary",
            "border": "--border",
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

    # 同步到 themes/ 目录
    import shutil as _st2
    theme_dest = settings.CONTENT_DIR / "themes" / pack_id
    theme_dest.mkdir(parents=True, exist_ok=True)
    src = pack_dir / "variables.css"
    if src.exists():
        _st2.copy2(src, theme_dest / "variables.css")
    src = pack_dir / "theme.json"
    if src.exists():
        _st2.copy2(src, theme_dest / "theme.json")
    assets_src = pack_dir / "assets"
    if assets_src.exists():
        assets_dest = theme_dest / "assets"
        assets_dest.mkdir(exist_ok=True)
        for f in assets_src.iterdir():
            if f.is_file():
                _st2.copy2(f, assets_dest / f.name)

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
    from api.log_api import log_info, log_error
    pack_dir = pack_manager.get_pack_dir(pack_id)
    if not pack_dir.exists():
        raise HTTPException(404, f"Pack '{pack_id}' not found")
    try:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            for file_path in pack_dir.rglob('*'):
                if file_path.is_file():
                    arcname = file_path.relative_to(pack_dir).as_posix()
                    zf.write(file_path, arcname)
        buffer.seek(0)
        size = buffer.getbuffer().nbytes
        log_info("Themepack", f"导出成功: {pack_id}, 大小: {size} bytes")
        from fastapi.responses import Response
        return Response(
            content=buffer.getvalue(),
            media_type='application/zip',
            headers={
                'Content-Disposition': 'attachment; filename="themepack.zip"',
            }
        )
    except Exception as e:
        log_error("Themepack", f"导出失败: {e}")
        raise HTTPException(500, f"导出失败: {e}")

@router.post("/api/themepacks/import")
async def import_pack(file: UploadFile = File(...)):
    import shutil
    from api.log_api import log_info, log_error

    content = await file.read()
    log_info("Themepack", f"导入请求: file={file.filename}, size={len(content)}")

    try:
        buffer = io.BytesIO(content)
        with zipfile.ZipFile(buffer, 'r') as zf:
            # 找到 pack.json 来确定 id
            pack_json_name = None
            for name in zf.namelist():
                # 处理可能的嵌套目录
                if name.endswith('pack.json') or name.endswith('/pack.json'):
                    pack_json_name = name
                    break
            if not pack_json_name:
                raise HTTPException(400, "无效的主题包：找不到 pack.json")

            pack_data = json.loads(zf.read(pack_json_name))
            pack_id = pack_data.get('id', 'imported_' + str(int(__import__('time').time())))
            pack_dir = pack_manager.get_pack_dir(pack_id)

            # 清理旧目录
            if pack_dir.exists():
                shutil.rmtree(pack_dir)
            pack_dir.mkdir(parents=True, exist_ok=True)

            # 解压，处理可能的嵌套目录
            for member in zf.namelist():
                # 获取文件在 zip 中的实际路径
                # 如果 pack.json 在子目录里，需要去掉前缀
                if pack_json_name.count('/') > 0:
                    prefix = pack_json_name.rsplit('/', 1)[0] + '/'
                    if member.startswith(prefix):
                        arcname = member[len(prefix):]
                    else:
                        arcname = member
                else:
                    arcname = member

                if not arcname:  # 跳过目录条目
                    continue

                target = pack_dir / arcname
                if member.endswith('/'):
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(member) as src, open(target, 'wb') as dst:
                        dst.write(src.read())

            # 验证解压结果
            if not (pack_dir / "pack.json").exists():
                log_error("Themepack", f"导入后找不到 pack.json: {pack_dir}")
                raise HTTPException(500, "导入失败：解压后找不到 pack.json")

            log_info("Themepack", f"导入成功: {pack_id}")
            return {"status": "ok", "id": pack_id, "name": pack_data.get('name', pack_id)}

    except HTTPException:
        raise
    except zipfile.BadZipFile:
        raise HTTPException(400, "无效的 ZIP 文件")
    except Exception as e:
        log_error("Themepack", f"导入失败: {e}")
        raise HTTPException(500, f"导入失败: {e}")

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
        persona_dest = settings.CONTENT_DIR / "personas" / persona_ref
        persona_dest.mkdir(parents=True, exist_ok=True)
        for f in ["persona.json", "prompt.md"]:
            src = pack_dir / f
            if src.exists():
                shutil.copy2(src, persona_dest / f)
        # 重载 persona 配置
        try:
            from persona.manager import persona_manager
            persona_manager.reload(persona_ref)
        except Exception:
            pass
    # 更新 theme
    if theme_ref:
        theme_dest = settings.CONTENT_DIR / "themes" / theme_ref
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
