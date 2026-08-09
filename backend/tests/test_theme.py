import io
import zipfile

import pytest
from fastapi import HTTPException, UploadFile

from themes.manager import ThemeManager

def test_list_themes():
    themes = ThemeManager.list_themes()
    ids = [t["id"] for t in themes]
    assert "default" in ids

def test_get_theme():
    t = ThemeManager.get_theme("default")
    assert t["name"] == "默认暗黑"
    assert "primary" in t["colors"]

def test_get_css():
    css = ThemeManager.get_css("miku")
    assert "#39C5BB" in css


def test_pet_placement_validation_rejects_out_of_range_values():
    from pet_config import validate_pet_placements

    with pytest.raises(ValueError, match="scale"):
        validate_pet_placements({"idle": {"scale": 3.2}})


@pytest.mark.asyncio
async def test_pet_frames_are_synced_and_deleted(tmp_path, monkeypatch):
    import api.theme_asset_api as theme_asset_api
    import api.themepack_api as themepack_api

    content_dir = tmp_path / "content"
    pack_dir = content_dir / "themepacks" / "sample_pack"
    pack_dir.mkdir(parents=True)
    pack_dir.joinpath("pack.json").write_text(
        '{"id":"sample_pack","theme_ref":"sample_theme"}',
        encoding="utf-8",
    )
    monkeypatch.setattr(themepack_api.settings, "CONTENT_DIR", content_dir)
    monkeypatch.setattr(
        themepack_api.pack_manager,
        "get_pack_dir",
        lambda pack_id: pack_dir if pack_id == "sample_pack" else content_dir / "missing",
    )
    monkeypatch.setattr(theme_asset_api, "THEMES_DIR", content_dir / "themes")

    upload = UploadFile(filename="idle.png", file=io.BytesIO(b"frame-data"))
    result = await themepack_api.upload_pack_pet_asset("sample_pack", "idle", upload)
    filename = result["filename"]

    assert filename == "pet-idle-001.png"
    assert (pack_dir / "assets" / filename).read_bytes() == b"frame-data"
    assert (content_dir / "themes" / "sample_theme" / "assets" / filename).exists()
    assert (content_dir / "themes" / "sample_pack" / "assets" / filename).exists()

    pack_assets = await themepack_api.list_pack_pet_assets("sample_pack")
    theme_assets = await theme_asset_api.list_pet_assets("sample_theme")
    assert pack_assets["idle"] == [filename]
    assert theme_assets["idle"] == [filename]

    await themepack_api.delete_pack_pet_asset("sample_pack", filename)
    assert not (pack_dir / "assets" / filename).exists()
    assert not (content_dir / "themes" / "sample_theme" / "assets" / filename).exists()
    assert not (content_dir / "themes" / "sample_pack" / "assets" / filename).exists()


@pytest.mark.asyncio
async def test_pet_animation_config_is_synced(tmp_path, monkeypatch):
    import api.themepack_api as themepack_api

    content_dir = tmp_path / "content"
    pack_dir = content_dir / "themepacks" / "sample_pack"
    pack_dir.mkdir(parents=True)
    pack_dir.joinpath("pack.json").write_text(
        '{"id":"sample_pack","theme_ref":"sample_theme"}',
        encoding="utf-8",
    )
    pack_dir.joinpath("theme.json").write_text(
        '{"pet_layout":{"enabled":true,"target_height":0.8}}',
        encoding="utf-8",
    )
    monkeypatch.setattr(themepack_api.settings, "CONTENT_DIR", content_dir)
    monkeypatch.setattr(
        themepack_api.pack_manager,
        "get_pack_dir",
        lambda pack_id: pack_dir if pack_id == "sample_pack" else content_dir / "missing",
    )

    initial = await themepack_api.get_pack_pet_config("sample_pack")
    assert initial["animations"]["idle"]["mode"] == "loop"
    assert initial["animations"]["thinking"]["mode"] == "loop"
    assert initial["animations"]["tool"]["fps"] == 20
    assert initial["animations"]["working"]["mode"] == "loop"

    result = await themepack_api.update_pack_pet_config(
        "sample_pack",
        themepack_api.PetConfigUpdate(
            scale=1.2,
            animations={"jump": {"fps": 24, "mode": "once", "after": "hold"}},
            placements={
                "idle": {"x": 0.1, "y": -0.12, "scale": 1.25},
                "tool": {"x": -0.05, "y": 0.08, "scale": 0.9},
            },
        ),
    )
    assert result["scale"] == 1.2
    assert result["animations"]["jump"]["fps"] == 24
    assert result["animations"]["jump"]["after"] == "hold"
    assert result["placements"]["idle"] == {"x": 0.1, "y": -0.12, "scale": 1.25}
    assert result["placements"]["tool"] == {"x": -0.05, "y": 0.08, "scale": 0.9}
    for path in (
        pack_dir / "theme.json",
        content_dir / "themes" / "sample_theme" / "theme.json",
        content_dir / "themes" / "sample_pack" / "theme.json",
    ):
        assert '"pet_animations"' in path.read_text(encoding="utf-8")
        assert '"pet_placements"' in path.read_text(encoding="utf-8")
        assert '"pet_layout"' not in path.read_text(encoding="utf-8")


def _animation_zip(entries):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries:
            archive.writestr(name, content)
    return buffer.getvalue()


@pytest.mark.asyncio
async def test_pet_animation_zip_replaces_and_orders_frames(tmp_path, monkeypatch):
    import api.themepack_api as themepack_api

    content_dir = tmp_path / "content"
    pack_dir = content_dir / "themepacks" / "sample_pack"
    pack_assets = pack_dir / "assets"
    pack_assets.mkdir(parents=True)
    pack_dir.joinpath("pack.json").write_text(
        '{"id":"sample_pack","theme_ref":"sample_theme"}',
        encoding="utf-8",
    )
    old_filename = "pet-idle-009.png"
    pack_assets.joinpath(old_filename).write_bytes(b"old")
    for theme_id in ("sample_pack", "sample_theme"):
        runtime_assets = content_dir / "themes" / theme_id / "assets"
        runtime_assets.mkdir(parents=True)
        runtime_assets.joinpath(old_filename).write_bytes(b"old")

    monkeypatch.setattr(themepack_api.settings, "CONTENT_DIR", content_dir)
    monkeypatch.setattr(
        themepack_api.pack_manager,
        "get_pack_dir",
        lambda pack_id: pack_dir if pack_id == "sample_pack" else content_dir / "missing",
    )
    archive = _animation_zip([
        ("frames/002-second.webp", b"second"),
        ("frames/001 first.png", b"first"),
        ("notes.txt", b"ignored"),
    ])
    upload = UploadFile(filename="idle.zip", file=io.BytesIO(archive))
    result = await themepack_api.replace_pack_pet_assets_from_zip("sample_pack", "idle", upload)

    assert result["count"] == 2
    assert result["filenames"] == ["pet-idle-001.png", "pet-idle-002.webp"]
    assert not pack_assets.joinpath(old_filename).exists()
    assert pack_assets.joinpath("pet-idle-001.png").read_bytes() == b"first"
    assert pack_assets.joinpath("pet-idle-002.webp").read_bytes() == b"second"
    for theme_id in ("sample_pack", "sample_theme"):
        runtime_assets = content_dir / "themes" / theme_id / "assets"
        assert not runtime_assets.joinpath(old_filename).exists()
        assert runtime_assets.joinpath("pet-idle-001.png").read_bytes() == b"first"


@pytest.mark.asyncio
async def test_pet_animation_zip_rejects_missing_sequence_without_replacing(tmp_path, monkeypatch):
    import api.themepack_api as themepack_api

    content_dir = tmp_path / "content"
    pack_dir = content_dir / "themepacks" / "sample_pack"
    assets_dir = pack_dir / "assets"
    assets_dir.mkdir(parents=True)
    pack_dir.joinpath("pack.json").write_text('{"id":"sample_pack"}', encoding="utf-8")
    existing = assets_dir / "pet-wave-001.png"
    existing.write_bytes(b"keep")
    monkeypatch.setattr(themepack_api.settings, "CONTENT_DIR", content_dir)
    monkeypatch.setattr(themepack_api.pack_manager, "get_pack_dir", lambda _pack_id: pack_dir)

    archive = _animation_zip([("001-start.png", b"one"), ("003-end.png", b"three")])
    upload = UploadFile(filename="wave.zip", file=io.BytesIO(archive))
    with pytest.raises(HTTPException) as error:
        await themepack_api.replace_pack_pet_assets_from_zip("sample_pack", "wave", upload)

    assert getattr(error.value, "status_code", None) == 400
    assert "missing 002" in str(getattr(error.value, "detail", ""))
    assert existing.read_bytes() == b"keep"


@pytest.mark.asyncio
async def test_delete_pet_action_frames_clears_pack_and_runtime_themes(tmp_path, monkeypatch):
    import api.themepack_api as themepack_api

    content_dir = tmp_path / "content"
    pack_dir = content_dir / "themepacks" / "sample_pack"
    pack_assets = pack_dir / "assets"
    pack_assets.mkdir(parents=True)
    pack_dir.joinpath("pack.json").write_text(
        '{"id":"sample_pack","theme_ref":"sample_theme"}',
        encoding="utf-8",
    )
    for filename in ("pet-walk-001.png", "pet-walk-002.png"):
        pack_assets.joinpath(filename).write_bytes(b"frame")
    pack_assets.joinpath("pet-idle-001.png").write_bytes(b"keep")
    for theme_id in ("sample_pack", "sample_theme"):
        runtime_assets = content_dir / "themes" / theme_id / "assets"
        runtime_assets.mkdir(parents=True)
        runtime_assets.joinpath("pet-walk-001.png").write_bytes(b"frame")
        runtime_assets.joinpath("pet-idle-001.png").write_bytes(b"keep")

    monkeypatch.setattr(themepack_api.settings, "CONTENT_DIR", content_dir)
    monkeypatch.setattr(themepack_api.pack_manager, "get_pack_dir", lambda _pack_id: pack_dir)

    result = await themepack_api.delete_pack_pet_action_frames("sample_pack", "walk")

    assert result["deleted"] == 2
    assert not list(pack_assets.glob("pet-walk-*"))
    assert pack_assets.joinpath("pet-idle-001.png").exists()
    for theme_id in ("sample_pack", "sample_theme"):
        runtime_assets = content_dir / "themes" / theme_id / "assets"
        assert not list(runtime_assets.glob("pet-walk-*"))
        assert runtime_assets.joinpath("pet-idle-001.png").exists()
