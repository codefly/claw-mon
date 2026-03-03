"""SQLite helper functions."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable


MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def get_sqlite_connection(db_path: Path) -> sqlite3.Connection:
    """Create a SQLite connection with foreign key enforcement enabled."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def _get_migration_files(migrations_dir: Path) -> Iterable[Path]:
    return sorted(path for path in migrations_dir.glob("*.sql") if path.is_file())


def apply_migrations(db_path: Path, migrations_dir: Path = MIGRATIONS_DIR) -> list[str]:
    """Apply pending SQL migrations and return the versions that were applied."""
    if not migrations_dir.exists():
        raise FileNotFoundError(f"Migration directory not found: {migrations_dir}")

    applied_versions: list[str] = []
    with get_sqlite_connection(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        existing_versions = {
            row["version"] for row in conn.execute("SELECT version FROM schema_migrations")
        }

        for migration_file in _get_migration_files(migrations_dir):
            version = migration_file.stem
            if version in existing_versions:
                continue

            sql = migration_file.read_text(encoding="utf-8")
            conn.executescript(sql)
            conn.execute(
                "INSERT INTO schema_migrations(version) VALUES (?)",
                (version,),
            )
            applied_versions.append(version)

    return applied_versions


def check_sqlite_connectivity(db_path: Path) -> tuple[bool, str | None]:
    """Attempt a lightweight SQLite query and report status."""
    try:
        with get_sqlite_connection(db_path) as conn:
            conn.execute("SELECT 1")
        return True, None
    except sqlite3.Error as exc:
        return False, str(exc)
