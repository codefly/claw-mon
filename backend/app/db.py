"""SQLite helper functions."""

from __future__ import annotations

import sqlite3
from pathlib import Path


def check_sqlite_connectivity(db_path: Path) -> tuple[bool, str | None]:
    """Attempt a lightweight SQLite query and report status."""
    try:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(db_path) as conn:
            conn.execute("SELECT 1")
        return True, None
    except sqlite3.Error as exc:
        return False, str(exc)
