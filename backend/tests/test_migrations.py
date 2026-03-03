import sqlite3
from pathlib import Path

import pytest

from app.db import apply_migrations, get_sqlite_connection


EXPECTED_TABLES = {
    "agents",
    "sessions",
    "raw_events",
    "usage_events",
    "file_offsets",
    "session_enrichment",
    "jobs",
    "schema_migrations",
}

EXPECTED_INDEXES = {
    "idx_sessions_agent_id",
    "idx_raw_events_timestamp",
    "idx_raw_events_session_timestamp",
    "idx_raw_events_type_role_timestamp",
    "idx_usage_events_timestamp",
    "idx_usage_events_agent_timestamp",
    "idx_usage_events_model_timestamp",
    "idx_usage_events_session_id",
    "idx_jobs_status_requested_at",
    "idx_session_enrichment_content_hash",
}


def test_apply_migrations_creates_expected_tables_and_indexes(tmp_path: Path) -> None:
    db_path = tmp_path / "clawmon.db"

    applied = apply_migrations(db_path)

    assert "0001_initial" in applied
    assert "0002_session_enrichment_hash" in applied

    with get_sqlite_connection(db_path) as conn:
        tables = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        indexes = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'index'"
            )
        }
        session_enrichment_columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(session_enrichment)")
        }

    assert EXPECTED_TABLES.issubset(tables)
    assert EXPECTED_INDEXES.issubset(indexes)
    assert "content_hash" in session_enrichment_columns
    assert "estimated_cost_usd" in session_enrichment_columns


def test_apply_migrations_is_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / "clawmon.db"

    first_apply = apply_migrations(db_path)
    second_apply = apply_migrations(db_path)

    assert first_apply == ["0001_initial", "0002_session_enrichment_hash"]
    assert second_apply == []

    with get_sqlite_connection(db_path) as conn:
        migration_count = conn.execute(
            "SELECT COUNT(*) AS count FROM schema_migrations"
        ).fetchone()["count"]

    assert migration_count == 2


def test_foreign_keys_are_enforced(tmp_path: Path) -> None:
    db_path = tmp_path / "clawmon.db"
    apply_migrations(db_path)

    with get_sqlite_connection(db_path) as conn:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO sessions(id, agent_id, file_path) VALUES (?, ?, ?)",
                ("session-1", "missing-agent", "/tmp/session-1.jsonl"),
            )


def test_unique_constraints_are_enforced(tmp_path: Path) -> None:
    db_path = tmp_path / "clawmon.db"
    apply_migrations(db_path)

    with get_sqlite_connection(db_path) as conn:
        conn.execute("INSERT INTO agents(id) VALUES (?)", ("agent-1",))
        conn.execute(
            "INSERT INTO sessions(id, agent_id, file_path) VALUES (?, ?, ?)",
            ("session-1", "agent-1", "/tmp/session-1.jsonl"),
        )
        conn.execute(
            """
            INSERT INTO raw_events(
                event_id, session_id, agent_id, timestamp, event_type, role, raw_json, raw_line_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "event-1",
                "session-1",
                "agent-1",
                "2026-03-02T22:23:08.995Z",
                "message",
                "assistant",
                '{"type":"message"}',
                "hash-1",
            ),
        )

        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """
                INSERT INTO raw_events(
                    event_id, session_id, agent_id, timestamp, event_type, role, raw_json, raw_line_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "event-2",
                    "session-1",
                    "agent-1",
                    "2026-03-02T22:23:09.000Z",
                    "message",
                    "assistant",
                    '{"type":"message"}',
                    "hash-1",
                ),
            )
