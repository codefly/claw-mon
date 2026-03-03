"""Job persistence helpers for refresh/enrich/reindex operations."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from app.db import get_sqlite_connection


def create_job(db_path: Path, job_type: str) -> str:
    job_id = str(uuid.uuid4())
    with get_sqlite_connection(db_path) as conn:
        conn.execute(
            """
            INSERT INTO jobs(id, job_type, status, progress_json)
            VALUES (?, ?, 'queued', '{}')
            """,
            (job_id, job_type),
        )
    return job_id


def set_job_running(db_path: Path, job_id: str) -> None:
    with get_sqlite_connection(db_path) as conn:
        conn.execute(
            """
            UPDATE jobs
            SET status = 'running', started_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (job_id,),
        )


def set_job_completed(db_path: Path, job_id: str, progress: dict[str, Any]) -> None:
    with get_sqlite_connection(db_path) as conn:
        conn.execute(
            """
            UPDATE jobs
            SET status = 'completed', finished_at = CURRENT_TIMESTAMP, progress_json = ?
            WHERE id = ?
            """,
            (json.dumps(progress), job_id),
        )


def set_job_failed(
    db_path: Path, job_id: str, error: str, progress: dict[str, Any] | None = None
) -> None:
    with get_sqlite_connection(db_path) as conn:
        conn.execute(
            """
            UPDATE jobs
            SET status = 'failed', finished_at = CURRENT_TIMESTAMP, error = ?, progress_json = ?
            WHERE id = ?
            """,
            (error, json.dumps(progress or {}), job_id),
        )


def get_job(db_path: Path, job_id: str) -> dict[str, Any] | None:
    with get_sqlite_connection(db_path) as conn:
        row = conn.execute(
            """
            SELECT id, job_type, status, requested_at, started_at, finished_at, progress_json, error
            FROM jobs
            WHERE id = ?
            """,
            (job_id,),
        ).fetchone()

    if row is None:
        return None

    progress_raw = row["progress_json"]
    try:
        progress = json.loads(progress_raw) if progress_raw else {}
    except json.JSONDecodeError:
        progress = {}

    return {
        "job_id": row["id"],
        "job_type": row["job_type"],
        "status": row["status"],
        "requested_at": row["requested_at"],
        "started_at": row["started_at"],
        "finished_at": row["finished_at"],
        "progress": progress,
        "error": row["error"],
    }
