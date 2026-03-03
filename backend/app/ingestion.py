"""Incremental ingestion for OpenClaw JSONL session files."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.db import apply_migrations, get_sqlite_connection


@dataclass
class IngestionStats:
    files_scanned: int = 0
    files_with_updates: int = 0
    lines_read: int = 0
    lines_skipped: int = 0
    raw_events_inserted: int = 0
    usage_events_inserted: int = 0
    offsets_reset: int = 0


def ingest_data_root(db_path: Path, data_root: Path) -> IngestionStats:
    """Ingest all session files under the OpenClaw agents data root."""
    apply_migrations(db_path)
    stats = IngestionStats()

    with get_sqlite_connection(db_path) as conn:
        for session_file in _discover_session_files(data_root):
            stats.files_scanned += 1
            _ingest_session_file(conn, data_root, session_file, stats)

    return stats


def _discover_session_files(data_root: Path) -> list[Path]:
    if not data_root.exists():
        return []

    files: list[Path] = []
    for path in data_root.rglob("*.jsonl"):
        if path.parent.name == "sessions" and path.is_file():
            files.append(path)

    return sorted(files)


def _ingest_session_file(conn, data_root: Path, session_file: Path, stats: IngestionStats) -> None:
    agent_id, session_id = _derive_agent_and_session_ids(data_root, session_file)

    file_stat = session_file.stat()
    inode = str(file_stat.st_ino)
    file_size = int(file_stat.st_size)
    last_mtime = float(file_stat.st_mtime)

    stored = conn.execute(
        """
        SELECT inode, offset_bytes
        FROM file_offsets
        WHERE file_path = ?
        """,
        (str(session_file),),
    ).fetchone()

    offset = 0
    if stored is not None:
        stored_inode = str(stored["inode"])
        stored_offset = int(stored["offset_bytes"])
        if stored_inode != inode or file_size < stored_offset:
            stats.offsets_reset += 1
            offset = 0
        else:
            offset = stored_offset

    with session_file.open("rb") as handle:
        handle.seek(offset)
        chunk = handle.read()

    if not chunk:
        _upsert_file_offset(
            conn=conn,
            file_path=session_file,
            inode=inode,
            offset_bytes=offset,
            last_size=file_size,
            last_mtime=last_mtime,
        )
        return

    complete_chunk, complete_len = _split_complete_chunk(chunk)
    if complete_len == 0:
        _upsert_file_offset(
            conn=conn,
            file_path=session_file,
            inode=inode,
            offset_bytes=offset,
            last_size=file_size,
            last_mtime=last_mtime,
        )
        return

    stats.files_with_updates += 1
    _upsert_agent_and_session(
        conn=conn,
        agent_id=agent_id,
        session_id=session_id,
        file_path=session_file,
    )

    cursor = offset
    for raw_line in complete_chunk.splitlines(keepends=True):
        stats.lines_read += 1
        line_start = cursor
        cursor += len(raw_line)

        payload = raw_line.rstrip(b"\r\n")
        if not payload:
            stats.lines_skipped += 1
            continue

        try:
            line_text = payload.decode("utf-8")
            event = json.loads(line_text)
        except (UnicodeDecodeError, json.JSONDecodeError):
            stats.lines_skipped += 1
            continue

        if not isinstance(event, dict):
            stats.lines_skipped += 1
            continue

        event_id, raw_line_hash = _make_event_id(
            file_path=session_file,
            line_start=line_start,
            payload=payload,
        )

        event_inserted = _insert_raw_event(
            conn=conn,
            event_id=event_id,
            raw_line_hash=raw_line_hash,
            agent_id=agent_id,
            session_id=session_id,
            event=event,
            raw_json=line_text,
        )
        if event_inserted:
            stats.raw_events_inserted += 1

        usage_inserted = _insert_usage_event_if_present(
            conn=conn,
            event_id=event_id,
            agent_id=agent_id,
            session_id=session_id,
            event=event,
        )
        if usage_inserted:
            stats.usage_events_inserted += 1

    _upsert_file_offset(
        conn=conn,
        file_path=session_file,
        inode=inode,
        offset_bytes=offset + complete_len,
        last_size=file_size,
        last_mtime=last_mtime,
    )


def _split_complete_chunk(chunk: bytes) -> tuple[bytes, int]:
    if not chunk:
        return b"", 0

    if chunk.endswith(b"\n"):
        return chunk, len(chunk)

    last_newline = chunk.rfind(b"\n")
    if last_newline == -1:
        return b"", 0

    complete_len = last_newline + 1
    return chunk[:complete_len], complete_len


def _derive_agent_and_session_ids(data_root: Path, session_file: Path) -> tuple[str, str]:
    try:
        relative = session_file.relative_to(data_root)
        agent_id = relative.parts[0]
    except ValueError:
        agent_id = session_file.parent.parent.name

    session_id = session_file.stem
    return agent_id, session_id


def _make_event_id(file_path: Path, line_start: int, payload: bytes) -> tuple[str, str]:
    hash_source = f"{file_path}:{line_start}:".encode("utf-8") + payload
    digest = hashlib.sha256(hash_source).hexdigest()
    return digest, digest


def _coerce_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _coerce_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _event_timestamp(event: dict[str, Any]) -> str:
    raw_timestamp = event.get("timestamp")
    if isinstance(raw_timestamp, str) and raw_timestamp:
        return raw_timestamp
    return datetime.now(tz=UTC).isoformat()


def _insert_raw_event(
    conn,
    event_id: str,
    raw_line_hash: str,
    agent_id: str,
    session_id: str,
    event: dict[str, Any],
    raw_json: str,
) -> bool:
    message = event.get("message") if isinstance(event.get("message"), dict) else {}
    role = message.get("role") if isinstance(message.get("role"), str) else None

    cursor = conn.execute(
        """
        INSERT OR IGNORE INTO raw_events(
            event_id,
            session_id,
            agent_id,
            timestamp,
            event_type,
            role,
            raw_json,
            raw_line_hash
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            event_id,
            session_id,
            agent_id,
            _event_timestamp(event),
            str(event.get("type", "unknown")),
            role,
            raw_json,
            raw_line_hash,
        ),
    )
    return cursor.rowcount > 0


def _insert_usage_event_if_present(
    conn,
    event_id: str,
    agent_id: str,
    session_id: str,
    event: dict[str, Any],
) -> bool:
    if event.get("type") != "message":
        return False

    message = event.get("message")
    if not isinstance(message, dict):
        return False
    if message.get("role") != "assistant":
        return False

    usage = message.get("usage")
    if not isinstance(usage, dict):
        return False

    input_tokens = _coerce_int(usage.get("input"))
    output_tokens = _coerce_int(usage.get("output"))
    cache_read_tokens = _coerce_int(usage.get("cacheRead"))
    cache_write_tokens = _coerce_int(usage.get("cacheWrite"))
    total_tokens = _coerce_int(usage.get("totalTokens"), default=-1)
    if total_tokens < 0:
        total_tokens = input_tokens + output_tokens + cache_read_tokens + cache_write_tokens

    cost = usage.get("cost") if isinstance(usage.get("cost"), dict) else {}
    usd_cost = _coerce_float(cost.get("total"))

    cursor = conn.execute(
        """
        INSERT OR IGNORE INTO usage_events(
            event_id,
            session_id,
            agent_id,
            timestamp,
            model,
            provider,
            input_tokens,
            output_tokens,
            cache_read_tokens,
            cache_write_tokens,
            total_tokens,
            usd_cost
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            event_id,
            session_id,
            agent_id,
            _event_timestamp(event),
            str(message.get("model", "unknown")),
            str(message.get("provider", "unknown")),
            input_tokens,
            output_tokens,
            cache_read_tokens,
            cache_write_tokens,
            total_tokens,
            usd_cost,
        ),
    )
    return cursor.rowcount > 0


def _upsert_agent_and_session(conn, agent_id: str, session_id: str, file_path: Path) -> None:
    now = datetime.now(tz=UTC).isoformat()

    conn.execute(
        """
        INSERT INTO agents(id, first_seen_at, last_seen_at)
        VALUES (?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            first_seen_at = COALESCE(agents.first_seen_at, excluded.first_seen_at),
            last_seen_at = excluded.last_seen_at
        """,
        (agent_id, now, now),
    )

    conn.execute(
        """
        INSERT INTO sessions(id, agent_id, file_path, last_ingested_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            agent_id = excluded.agent_id,
            file_path = excluded.file_path,
            last_ingested_at = excluded.last_ingested_at
        """,
        (session_id, agent_id, str(file_path), now),
    )


def _upsert_file_offset(
    conn,
    file_path: Path,
    inode: str,
    offset_bytes: int,
    last_size: int,
    last_mtime: float,
) -> None:
    conn.execute(
        """
        INSERT INTO file_offsets(file_path, inode, offset_bytes, last_size, last_mtime)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(file_path) DO UPDATE SET
            inode = excluded.inode,
            offset_bytes = excluded.offset_bytes,
            last_size = excluded.last_size,
            last_mtime = excluded.last_mtime,
            updated_at = CURRENT_TIMESTAMP
        """,
        (str(file_path), inode, offset_bytes, last_size, last_mtime),
    )
