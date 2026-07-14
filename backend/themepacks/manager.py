import json
import shutil
from pathlib import Path

PACKS_DIR = Path(__file__).parent.parent.parent / "themepacks"

class ThemePackManager:
    def __init__(self):
        PACKS_DIR.mkdir(exist_ok=True)

    def list_packs(self):
        packs = []
        for d in PACKS_DIR.iterdir():
            if d.is_dir() and (d / "pack.json").exists():
                pack = json.loads((d / "pack.json").read_text(encoding="utf-8"))
                packs.append(pack)
        return packs

    def get_pack(self, pack_id):
        pack_dir = PACKS_DIR / pack_id
        if not pack_dir.exists() or not (pack_dir / "pack.json").exists():
            return None
        return json.loads((pack_dir / "pack.json").read_text(encoding="utf-8"))

    def create_pack(self, pack_id, name, persona_ref="", theme_ref=""):
        pack_dir = PACKS_DIR / pack_id
        if pack_dir.exists():
            raise ValueError(f"Pack '{pack_id}' already exists")
        pack_dir.mkdir(parents=True)
        # 创建 assets 子目录
        (pack_dir / "assets").mkdir()
        # 写 pack.json
        pack_data = {
            "id": pack_id,
            "name": name,
            "persona_ref": persona_ref,
            "theme_ref": theme_ref,
        }
        (pack_dir / "pack.json").write_text(json.dumps(pack_data, ensure_ascii=False, indent=2), encoding="utf-8")
        # 复制 persona 文件（如果指定了）
        if persona_ref:
            persona_src = Path(__file__).parent.parent.parent / "personas" / persona_ref
            if persona_src.exists():
                for f in persona_src.iterdir():
                    if f.is_file():
                        shutil.copy2(f, pack_dir / f.name)
        # 复制 theme 文件（如果指定了）
        if theme_ref:
            theme_src = Path(__file__).parent.parent.parent / "themes" / theme_ref
            if theme_src.exists():
                for f in theme_src.iterdir():
                    if f.is_file():
                        shutil.copy2(f, pack_dir / f.name)
                # 复制 assets
                theme_assets = theme_src / "assets"
                if theme_assets.exists():
                    for f in theme_assets.iterdir():
                        if f.is_file():
                            shutil.copy2(f, pack_dir / "assets" / f.name)
        return pack_data

    def update_pack(self, pack_id, **kwargs):
        pack_dir = PACKS_DIR / pack_id
        if not pack_dir.exists():
            raise ValueError(f"Pack '{pack_id}' not found")
        pack_data = json.loads((pack_dir / "pack.json").read_text(encoding="utf-8"))
        for k, v in kwargs.items():
            if k in pack_data:
                pack_data[k] = v
        (pack_dir / "pack.json").write_text(json.dumps(pack_data, ensure_ascii=False, indent=2), encoding="utf-8")
        return pack_data

    def delete_pack(self, pack_id):
        if pack_id == "default_pack":
            raise ValueError("Cannot delete default pack")
        pack_dir = PACKS_DIR / pack_id
        if not pack_dir.exists():
            raise ValueError(f"Pack '{pack_id}' not found")
        shutil.rmtree(pack_dir)

    def get_pack_dir(self, pack_id):
        return PACKS_DIR / pack_id

pack_manager = ThemePackManager()
