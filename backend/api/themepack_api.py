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
from pet_config import PET_ACTIONS, read_pet_config, validate_pet_animations, validate_pet_placements

router = APIRouter()
PET_IMAGE_EXTENSIONS = {".png", ".webp", ".jpg", ".jpeg", ".gif"}
PET_ZIP_MAX_COMPRESSED_BYTES = 100 * 1024 * 1024
PET_ZIP_MAX_UNCOMPRESSED_BYTES = 200 * 1024 * 1024
PET_ZIP_MAX_FRAME_BYTES = 12 * 1024 * 1024
PET_ZIP_MAX_FRAMES = 999


def _pack_theme_id(pack_dir: Path, pack_id: str) -> str:
    pack_json = pack_dir / "pack.json"
    if not pack_json.exists():
        return pack_id
    try:
        return json.loads(pack_json.read_text(encoding="utf-8")).get("theme_ref") or pack_id
    except (json.JSONDecodeError, OSError):
        return pack_id


def _sync_pet_asset(pack_dir: Path, pack_id: str, filename: str, content: Optional[bytes]):
    theme_id = _pack_theme_id(pack_dir, pack_id)
    targets = {theme_id, pack_id}
    for target_id in targets:
        assets_dir = settings.CONTENT_DIR / "themes" / target_id / "assets"
        if content is None:
            (assets_dir / filename).unlink(missing_ok=True)
        else:
            assets_dir.mkdir(parents=True, exist_ok=True)
            (assets_dir / filename).write_bytes(content)


def _replace_pet_action_frames(pack_dir: Path, pack_id: str, action: str, frames):
    assets_dir = pack_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    for existing in assets_dir.glob(f"pet-{action}-*"):
        if existing.is_file():
            existing.unlink()

    theme_id = _pack_theme_id(pack_dir, pack_id)
    runtime_dirs = [
        settings.CONTENT_DIR / "themes" / target_id / "assets"
        for target_id in {theme_id, pack_id}
    ]
    for runtime_dir in runtime_dirs:
        if runtime_dir.exists():
            for existing in runtime_dir.glob(f"pet-{action}-*"):
                if existing.is_file():
                    existing.unlink()

    for filename, content in frames:
        (assets_dir / filename).write_bytes(content)
        for runtime_dir in runtime_dirs:
            runtime_dir.mkdir(parents=True, exist_ok=True)
            (runtime_dir / filename).write_bytes(content)


def _read_pet_zip_frames(content: bytes, action: str):
    if len(content) > PET_ZIP_MAX_COMPRESSED_BYTES:
        raise HTTPException(400, "ZIP file must not exceed 100 MB")
    try:
        archive = zipfile.ZipFile(io.BytesIO(content))
    except zipfile.BadZipFile:
        raise HTTPException(400, "Invalid ZIP file")

    with archive:
        entries = []
        total_size = 0
        for info in archive.infolist():
            if info.is_dir():
                continue
            normalized = info.filename.replace("\\", "/")
            filename = normalized.rsplit("/", 1)[-1]
            if not filename or filename.startswith(".") or "__MACOSX" in normalized.split("/"):
                continue
            suffix = Path(filename).suffix.lower()
            if suffix not in PET_IMAGE_EXTENSIONS:
                continue
            if len(filename) < 4 or not filename[:3].isdigit() or filename[:3] == "000":
                raise HTTPException(400, f"Frame '{filename}' must start with a three-digit sequence such as 001")
            if info.flag_bits & 0x1:
                raise HTTPException(400, "Encrypted ZIP entries are not supported")
            if info.file_size > PET_ZIP_MAX_FRAME_BYTES:
                raise HTTPException(400, f"Frame '{filename}' exceeds 12 MB")
            total_size += info.file_size
            if total_size > PET_ZIP_MAX_UNCOMPRESSED_BYTES:
                raise HTTPException(400, "Uncompressed animation frames must not exceed 200 MB")
            entries.append((int(filename[:3]), suffix, info))
        if len(entries) > PET_ZIP_MAX_FRAMES:
            raise HTTPException(400, "A ZIP file can contain at most 999 animation frames")

        if not entries:
            raise HTTPException(400, "ZIP file does not contain supported animation frames")
        entries.sort(key=lambda item: item[0])
        sequences = [item[0] for item in entries]
        if len(sequences) != len(set(sequences)):
            raise HTTPException(400, "Animation frame sequence numbers must be unique")
        expected = list(range(1, len(entries) + 1))
        if sequences != expected:
            missing = next((number for number in expected if number not in sequences), 1)
            raise HTTPException(400, f"Animation frame sequence must be continuous from 001; missing {missing:03d}")

        try:
            return [
                (f"pet-{action}-{sequence:03d}{suffix}", archive.read(info))
                for sequence, suffix, info in entries
            ]
        except (OSError, RuntimeError, zipfile.BadZipFile) as error:
            raise HTTPException(400, f"Unable to read ZIP animation frames: {error}")

class PackCreate(BaseModel):
    id: str
    name: str
    persona_ref: str = ""
    theme_ref: str = ""

class PackUpdate(BaseModel):
    name: Optional[str] = None
    character: Optional[dict] = None
    theme: Optional[dict] = None


class PetConfigUpdate(BaseModel):
    scale: Optional[float] = None
    animations: Optional[dict] = None
    placements: Optional[dict] = None

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


@router.get("/api/themepacks/{pack_id}/pet-assets")
async def list_pack_pet_assets(pack_id: str):
    pack_dir = pack_manager.get_pack_dir(pack_id)
    if not pack_dir.exists():
        raise HTTPException(404, f"Pack '{pack_id}' not found")
    assets_dir = pack_dir / "assets"
    result = {action: [] for action in PET_ACTIONS}
    if assets_dir.exists():
        for action in PET_ACTIONS:
            result[action] = sorted(
                file.name for file in assets_dir.glob(f"pet-{action}-*") if file.is_file()
            )
    return result


@router.get("/api/themepacks/{pack_id}/pet-config")
async def get_pack_pet_config(pack_id: str):
    pack_dir = pack_manager.get_pack_dir(pack_id)
    if not pack_dir.exists():
        raise HTTPException(404, f"Pack '{pack_id}' not found")
    theme_id = _pack_theme_id(pack_dir, pack_id)
    theme_json = pack_dir / "theme.json"
    return {"theme_id": theme_id, **read_pet_config(theme_json)}


@router.put("/api/themepacks/{pack_id}/pet-config")
async def update_pack_pet_config(pack_id: str, req: PetConfigUpdate):
    if req.scale is not None and not 0.6 <= req.scale <= 1.8:
        raise HTTPException(400, "Pet scale must be between 0.6 and 1.8")
    try:
        animations = validate_pet_animations(req.animations) if req.animations is not None else None
        placements = validate_pet_placements(req.placements) if req.placements is not None else None
    except ValueError as error:
        raise HTTPException(400, str(error))
    pack_dir = pack_manager.get_pack_dir(pack_id)
    if not pack_dir.exists():
        raise HTTPException(404, f"Pack '{pack_id}' not found")

    theme_id = _pack_theme_id(pack_dir, pack_id)
    targets = [pack_dir / "theme.json"]
    targets.extend(
        settings.CONTENT_DIR / "themes" / target_id / "theme.json"
        for target_id in {theme_id, pack_id}
    )
    for target in targets:
        target.parent.mkdir(parents=True, exist_ok=True)
        data = {}
        if target.exists():
            try:
                data = json.loads(target.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                data = {}
        if req.scale is not None:
            data["pet_scale"] = req.scale
        if animations is not None:
            data["pet_animations"] = animations
        if placements is not None:
            data["pet_placements"] = placements
            data.pop("pet_layout", None)
        target.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"status": "ok", "theme_id": theme_id, **read_pet_config(pack_dir / "theme.json")}


@router.post("/api/themepacks/{pack_id}/pet-assets/{action}")
async def upload_pack_pet_asset(pack_id: str, action: str, file: UploadFile = File(...)):
    if action not in PET_ACTIONS:
        raise HTTPException(400, "Unsupported pet action")
    pack_dir = pack_manager.get_pack_dir(pack_id)
    if not pack_dir.exists():
        raise HTTPException(404, f"Pack '{pack_id}' not found")

    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in PET_IMAGE_EXTENSIONS:
        raise HTTPException(400, "Pet frames must be PNG, WebP, JPG, or GIF images")

    assets_dir = pack_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    indexes = []
    for existing in assets_dir.glob(f"pet-{action}-*"):
        try:
            indexes.append(int(existing.stem.rsplit("-", 1)[-1]))
        except ValueError:
            continue
    filename = f"pet-{action}-{max(indexes, default=0) + 1:03d}{suffix}"
    content = await file.read()
    (assets_dir / filename).write_bytes(content)
    _sync_pet_asset(pack_dir, pack_id, filename, content)
    return {"status": "ok", "filename": filename, "size": len(content)}


@router.post("/api/themepacks/{pack_id}/pet-assets/{action}/zip")
async def replace_pack_pet_assets_from_zip(pack_id: str, action: str, file: UploadFile = File(...)):
    if action not in PET_ACTIONS:
        raise HTTPException(400, "Unsupported pet action")
    if Path(file.filename or "").suffix.lower() != ".zip":
        raise HTTPException(400, "Animation archive must be a ZIP file")
    pack_dir = pack_manager.get_pack_dir(pack_id)
    if not pack_dir.exists():
        raise HTTPException(404, f"Pack '{pack_id}' not found")

    frames = _read_pet_zip_frames(await file.read(), action)
    _replace_pet_action_frames(pack_dir, pack_id, action, frames)
    return {
        "status": "ok",
        "action": action,
        "count": len(frames),
        "filenames": [filename for filename, _content in frames],
    }


@router.delete("/api/themepacks/{pack_id}/pet-assets/{action}/all")
async def delete_pack_pet_action_frames(pack_id: str, action: str):
    if action not in PET_ACTIONS:
        raise HTTPException(400, "Unsupported pet action")
    pack_dir = pack_manager.get_pack_dir(pack_id)
    if not pack_dir.exists():
        raise HTTPException(404, f"Pack '{pack_id}' not found")

    assets_dir = pack_dir / "assets"
    deleted = sum(1 for path in assets_dir.glob(f"pet-{action}-*") if path.is_file()) if assets_dir.exists() else 0
    _replace_pet_action_frames(pack_dir, pack_id, action, [])
    return {"status": "ok", "action": action, "deleted": deleted}


@router.delete("/api/themepacks/{pack_id}/pet-assets/{filename}")
async def delete_pack_pet_asset(pack_id: str, filename: str):
    if Path(filename).name != filename or not filename.startswith("pet-"):
        raise HTTPException(400, "Invalid pet frame filename")
    pack_dir = pack_manager.get_pack_dir(pack_id)
    target = pack_dir / "assets" / filename
    if not target.exists():
        raise HTTPException(404, f"Pet frame '{filename}' not found")
    target.unlink()
    _sync_pet_asset(pack_dir, pack_id, filename, None)
    return {"status": "ok"}

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
