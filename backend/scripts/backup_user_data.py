"""Create a consistent ZIP backup of VerseNa user data."""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path


BACKUP_SOURCES = (
    Path("backend/data"),
    Path("personas"),
    Path("themes"),
    Path("themepacks"),
    Path("backend/skills/custom"),
    Path("backend/skills/installed"),
)


def _ignore_live_database_files(_directory: str, names: list[str]) -> set[str]:
    return {
        name
        for name in names
        if name.endswith((".db", ".db-wal", ".db-shm"))
    }


def _copy_sqlite_database(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.stat().st_size == 0:
        shutil.copy2(source, destination)
        return

    source_connection = sqlite3.connect(f"file:{source.as_posix()}?mode=ro", uri=True)
    destination_connection = sqlite3.connect(destination)
    try:
        source_connection.backup(destination_connection)
    finally:
        destination_connection.close()
        source_connection.close()


def create_backup(project_root: Path, output_dir: Path, keep: int = 10) -> Path:
    project_root = project_root.resolve()
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = output_dir / f"versena-backup-{timestamp}.zip"
    if backup_path.exists():
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        backup_path = output_dir / f"versena-backup-{timestamp}.zip"

    included_sources: list[str] = []
    with tempfile.TemporaryDirectory(prefix="versena-backup-") as temp_dir:
        staging_root = Path(temp_dir)

        for relative_source in BACKUP_SOURCES:
            source = project_root / relative_source
            if not source.exists():
                continue
            destination = staging_root / relative_source
            shutil.copytree(
                source,
                destination,
                dirs_exist_ok=True,
                ignore=_ignore_live_database_files,
            )
            included_sources.append(relative_source.as_posix())

        data_dir = project_root / "backend/data"
        if data_dir.exists():
            for database_path in data_dir.glob("*.db"):
                relative_database = database_path.relative_to(project_root)
                _copy_sqlite_database(database_path, staging_root / relative_database)

        manifest = {
            "format_version": 1,
            "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "sources": included_sources,
        }
        (staging_root / "backup-manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        with zipfile.ZipFile(backup_path, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(staging_root.rglob("*")):
                if path.is_file():
                    archive.write(path, path.relative_to(staging_root).as_posix())

    if keep > 0:
        backups = sorted(output_dir.glob("versena-backup-*.zip"), reverse=True)
        for expired_backup in backups[keep:]:
            expired_backup.unlink()

    return backup_path


def main() -> None:
    project_root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description="Backup VerseNa user data")
    parser.add_argument(
        "--output",
        type=Path,
        default=project_root / "backups",
        help="Backup output directory (default: <project>/backups)",
    )
    parser.add_argument(
        "--keep",
        type=int,
        default=10,
        help="Number of recent backups to retain; 0 keeps all (default: 10)",
    )
    args = parser.parse_args()

    backup_path = create_backup(project_root, args.output, max(args.keep, 0))
    print(backup_path)


if __name__ == "__main__":
    main()
