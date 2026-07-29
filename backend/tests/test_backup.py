import sqlite3
import sys
import zipfile
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from backup_user_data import create_backup


def test_backup_contains_consistent_database_and_user_assets(tmp_path):
    project_root = tmp_path / "project"
    data_dir = project_root / "backend/data"
    persona_dir = project_root / "personas/default"
    data_dir.mkdir(parents=True)
    persona_dir.mkdir(parents=True)

    database_path = data_dir / "ciyuan.db"
    connection = sqlite3.connect(database_path)
    connection.execute("CREATE TABLE messages (content TEXT NOT NULL)")
    connection.execute("INSERT INTO messages VALUES ('hello')")
    connection.commit()
    persona_dir.joinpath("prompt.md").write_text("persona", encoding="utf-8")

    backup_path = create_backup(project_root, tmp_path / "backups", keep=1)
    connection.close()

    with zipfile.ZipFile(backup_path) as archive:
        names = set(archive.namelist())
        assert "backup-manifest.json" in names
        assert "backend/data/ciyuan.db" in names
        assert "personas/default/prompt.md" in names
        archive.extract("backend/data/ciyuan.db", tmp_path / "restored")

    restored = sqlite3.connect(tmp_path / "restored/backend/data/ciyuan.db")
    try:
        assert restored.execute("SELECT content FROM messages").fetchone()[0] == "hello"
    finally:
        restored.close()
