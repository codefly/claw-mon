import json
from pathlib import Path

from app.db import get_sqlite_connection
from app.ingestion import ingest_data_root


def _write_jsonl(path: Path, events: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join(json.dumps(event) for event in events) + "\n"
    path.write_text(text, encoding="utf-8")


def _append_jsonl(path: Path, events: list[dict]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        for event in events:
            handle.write(json.dumps(event) + "\n")


def _message_event(*, timestamp: str, role: str, with_usage: bool = False) -> dict:
    message = {
        "role": role,
        "model": "claude-sonnet-4-6",
        "provider": "anthropic",
    }
    if with_usage:
        message["usage"] = {
            "input": 10,
            "output": 5,
            "cacheRead": 2,
            "cacheWrite": 1,
            "totalTokens": 18,
            "cost": {"total": 0.00123},
        }

    return {
        "type": "message",
        "timestamp": timestamp,
        "message": message,
    }


def test_ingest_appends_without_reprocessing_existing_lines(tmp_path: Path) -> None:
    db_path = tmp_path / "db" / "clawmon.db"
    data_root = tmp_path / "agents"
    session_file = data_root / "agent-a" / "sessions" / "session-1.jsonl"

    _write_jsonl(
        session_file,
        [
            _message_event(timestamp="2026-03-02T22:00:00Z", role="user"),
            _message_event(
                timestamp="2026-03-02T22:00:01Z", role="assistant", with_usage=True
            ),
        ],
    )

    first_stats = ingest_data_root(db_path=db_path, data_root=data_root)

    assert first_stats.files_scanned == 1
    assert first_stats.lines_read == 2
    assert first_stats.lines_skipped == 0
    assert first_stats.raw_events_inserted == 2
    assert first_stats.usage_events_inserted == 1

    _append_jsonl(
        session_file,
        [
            _message_event(
                timestamp="2026-03-02T22:00:02Z", role="assistant", with_usage=True
            )
        ],
    )

    second_stats = ingest_data_root(db_path=db_path, data_root=data_root)

    assert second_stats.files_scanned == 1
    assert second_stats.lines_read == 1
    assert second_stats.raw_events_inserted == 1
    assert second_stats.usage_events_inserted == 1

    with get_sqlite_connection(db_path) as conn:
        raw_count = conn.execute("SELECT COUNT(*) AS count FROM raw_events").fetchone()[
            "count"
        ]
        usage_count = conn.execute(
            "SELECT COUNT(*) AS count FROM usage_events"
        ).fetchone()["count"]

    assert raw_count == 3
    assert usage_count == 2


def test_ingest_resets_offset_when_file_is_truncated(tmp_path: Path) -> None:
    db_path = tmp_path / "db" / "clawmon.db"
    data_root = tmp_path / "agents"
    session_file = data_root / "agent-b" / "sessions" / "session-2.jsonl"

    _write_jsonl(
        session_file,
        [
            _message_event(
                timestamp="2026-03-02T22:10:00Z", role="assistant", with_usage=True
            ),
            _message_event(
                timestamp="2026-03-02T22:10:01Z", role="assistant", with_usage=True
            ),
        ],
    )
    ingest_data_root(db_path=db_path, data_root=data_root)

    _write_jsonl(
        session_file,
        [
            _message_event(
                timestamp="2026-03-02T22:11:00Z", role="assistant", with_usage=True
            )
        ],
    )

    stats = ingest_data_root(db_path=db_path, data_root=data_root)

    assert stats.offsets_reset == 1
    assert stats.lines_read == 1
    assert stats.raw_events_inserted == 1
    assert stats.usage_events_inserted == 1

    with get_sqlite_connection(db_path) as conn:
        raw_count = conn.execute("SELECT COUNT(*) AS count FROM raw_events").fetchone()[
            "count"
        ]

    assert raw_count == 3


def test_ingest_resets_offset_when_inode_changes(tmp_path: Path) -> None:
    db_path = tmp_path / "db" / "clawmon.db"
    data_root = tmp_path / "agents"
    session_file = data_root / "agent-r" / "sessions" / "session-4.jsonl"

    _write_jsonl(
        session_file,
        [
            _message_event(
                timestamp="2026-03-02T22:12:00Z", role="assistant", with_usage=True
            )
        ],
    )
    ingest_data_root(db_path=db_path, data_root=data_root)

    with get_sqlite_connection(db_path) as conn:
        conn.execute(
            """
            UPDATE file_offsets
            SET inode = ?, offset_bytes = ?
            WHERE file_path = ?
            """,
            ("fake-inode", session_file.stat().st_size, str(session_file)),
        )

    stats = ingest_data_root(db_path=db_path, data_root=data_root)

    assert stats.offsets_reset == 1
    assert stats.lines_read == 1
    assert stats.raw_events_inserted == 0
    assert stats.usage_events_inserted == 0


def test_ingest_skips_and_counts_malformed_lines(tmp_path: Path) -> None:
    db_path = tmp_path / "db" / "clawmon.db"
    data_root = tmp_path / "agents"
    session_file = data_root / "agent-c" / "sessions" / "session-3.jsonl"

    session_file.parent.mkdir(parents=True, exist_ok=True)
    session_file.write_text(
        "\n".join(
            [
                json.dumps(
                    _message_event(
                        timestamp="2026-03-02T22:20:00Z",
                        role="assistant",
                        with_usage=True,
                    )
                ),
                "{not-json",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    stats = ingest_data_root(db_path=db_path, data_root=data_root)

    assert stats.lines_read == 3
    assert stats.lines_skipped == 2
    assert stats.raw_events_inserted == 1
    assert stats.usage_events_inserted == 1

    with get_sqlite_connection(db_path) as conn:
        raw_count = conn.execute("SELECT COUNT(*) AS count FROM raw_events").fetchone()[
            "count"
        ]

    assert raw_count == 1


def test_ingest_recursively_discovers_multiple_agents(tmp_path: Path) -> None:
    db_path = tmp_path / "db" / "clawmon.db"
    data_root = tmp_path / "agents"

    _write_jsonl(
        data_root / "agent-x" / "sessions" / "s1.jsonl",
        [_message_event(timestamp="2026-03-02T22:30:00Z", role="user")],
    )
    _write_jsonl(
        data_root / "agent-y" / "sessions" / "s2.jsonl",
        [_message_event(timestamp="2026-03-02T22:31:00Z", role="assistant", with_usage=True)],
    )

    stats = ingest_data_root(db_path=db_path, data_root=data_root)

    assert stats.files_scanned == 2
    assert stats.raw_events_inserted == 2

    with get_sqlite_connection(db_path) as conn:
        agents = {
            row["id"]
            for row in conn.execute("SELECT id FROM agents ORDER BY id")
        }

    assert agents == {"agent-x", "agent-y"}


def test_ingest_ignores_trailing_partial_line_until_completed(tmp_path: Path) -> None:
    db_path = tmp_path / "db" / "clawmon.db"
    data_root = tmp_path / "agents"
    session_file = data_root / "agent-p" / "sessions" / "session-partial.jsonl"

    session_file.parent.mkdir(parents=True, exist_ok=True)
    session_file.write_text(
        json.dumps(_message_event(timestamp="2026-03-02T23:00:00Z", role="user"))
        + "\n"
        + '{"type":"message"',
        encoding="utf-8",
    )

    first_stats = ingest_data_root(db_path=db_path, data_root=data_root)
    assert first_stats.lines_read == 1
    assert first_stats.raw_events_inserted == 1

    with session_file.open("a", encoding="utf-8") as handle:
        handle.write(
            ',"timestamp":"2026-03-02T23:00:01Z","message":{"role":"assistant","model":"claude-sonnet-4-6","provider":"anthropic","usage":{"input":1,"output":1,"cacheRead":0,"cacheWrite":0,"totalTokens":2,"cost":{"total":0.0001}}}}\n'
        )

    second_stats = ingest_data_root(db_path=db_path, data_root=data_root)
    assert second_stats.lines_read == 1
    assert second_stats.raw_events_inserted == 1
    assert second_stats.usage_events_inserted == 1

    with get_sqlite_connection(db_path) as conn:
        raw_count = conn.execute("SELECT COUNT(*) AS count FROM raw_events").fetchone()[
            "count"
        ]

    assert raw_count == 2
