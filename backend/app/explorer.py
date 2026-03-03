"""Session and raw-event explorer queries."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.db import get_sqlite_connection


@dataclass(frozen=True)
class SessionFilters:
    from_ts: str | None = None
    to_ts: str | None = None
    agents: list[str] | None = None
    models: list[str] | None = None
    providers: list[str] | None = None


@dataclass(frozen=True)
class EventFilters:
    from_ts: str | None = None
    to_ts: str | None = None
    event_types: list[str] | None = None
    roles: list[str] | None = None
    agents: list[str] | None = None
    sessions: list[str] | None = None
    usage_bearing_only: bool = False


def _in_clause(values: list[str]) -> str:
    return ",".join("?" for _ in values)


def _build_session_where(filters: SessionFilters) -> tuple[str, list[object]]:
    clauses: list[str] = []
    params: list[object] = []

    if filters.agents:
        clauses.append(f"s.agent_id IN ({_in_clause(filters.agents)})")
        params.extend(filters.agents)

    if filters.from_ts or filters.to_ts:
        parts = ["re.session_id = s.id"]
        if filters.from_ts:
            parts.append("re.timestamp >= ?")
            params.append(filters.from_ts)
        if filters.to_ts:
            parts.append("re.timestamp <= ?")
            params.append(filters.to_ts)
        clauses.append(f"EXISTS (SELECT 1 FROM raw_events re WHERE {' AND '.join(parts)})")

    if filters.models or filters.providers:
        parts = ["ue.session_id = s.id"]
        if filters.models:
            parts.append(f"ue.model IN ({_in_clause(filters.models)})")
            params.extend(filters.models)
        if filters.providers:
            parts.append(f"ue.provider IN ({_in_clause(filters.providers)})")
            params.extend(filters.providers)
        clauses.append(f"EXISTS (SELECT 1 FROM usage_events ue WHERE {' AND '.join(parts)})")

    where_sql = ""
    if clauses:
        where_sql = "WHERE " + " AND ".join(clauses)

    return where_sql, params


def query_sessions(
    db_path: Path,
    filters: SessionFilters,
    page: int,
    page_size: int,
) -> dict[str, object]:
    where_sql, params = _build_session_where(filters)

    with get_sqlite_connection(db_path) as conn:
        total_items_row = conn.execute(
            f"SELECT COUNT(*) AS count FROM sessions s {where_sql}",
            params,
        ).fetchone()

        offset = (page - 1) * page_size
        rows = conn.execute(
            f"""
            WITH raw_agg AS (
                SELECT
                    session_id,
                    MIN(timestamp) AS started_at,
                    MAX(timestamp) AS ended_at,
                    COUNT(*) AS total_events
                FROM raw_events
                GROUP BY session_id
            ),
            usage_agg AS (
                SELECT
                    session_id,
                    COUNT(*) AS usage_events,
                    COALESCE(SUM(total_tokens), 0) AS total_tokens,
                    COALESCE(SUM(usd_cost), 0.0) AS total_cost_usd
                FROM usage_events
                GROUP BY session_id
            )
            SELECT
                s.id AS session_id,
                s.agent_id,
                s.file_path,
                ra.started_at,
                ra.ended_at,
                COALESCE(ra.total_events, 0) AS total_events,
                COALESCE(ua.usage_events, 0) AS usage_events,
                COALESCE(ua.total_tokens, 0) AS total_tokens,
                COALESCE(ua.total_cost_usd, 0.0) AS total_cost_usd
            FROM sessions s
            LEFT JOIN raw_agg ra ON ra.session_id = s.id
            LEFT JOIN usage_agg ua ON ua.session_id = s.id
            {where_sql}
            ORDER BY COALESCE(ra.ended_at, '') DESC, s.id ASC
            LIMIT ? OFFSET ?
            """,
            [*params, page_size, offset],
        ).fetchall()

    return {
        "page": page,
        "page_size": page_size,
        "total_items": total_items_row["count"],
        "items": [
            {
                "session_id": row["session_id"],
                "agent_id": row["agent_id"],
                "file_path": row["file_path"],
                "started_at": row["started_at"],
                "ended_at": row["ended_at"],
                "total_events": row["total_events"],
                "usage_events": row["usage_events"],
                "total_tokens": row["total_tokens"],
                "total_cost_usd": row["total_cost_usd"],
            }
            for row in rows
        ],
    }


def query_session_detail(
    db_path: Path,
    session_id: str,
    page: int,
    page_size: int,
) -> dict[str, object] | None:
    with get_sqlite_connection(db_path) as conn:
        session_row = conn.execute(
            """
            WITH raw_agg AS (
                SELECT
                    session_id,
                    MIN(timestamp) AS started_at,
                    MAX(timestamp) AS ended_at,
                    COUNT(*) AS total_events
                FROM raw_events
                GROUP BY session_id
            )
            SELECT
                s.id AS session_id,
                s.agent_id,
                s.file_path,
                ra.started_at,
                ra.ended_at,
                COALESCE(ra.total_events, 0) AS total_events
            FROM sessions s
            LEFT JOIN raw_agg ra ON ra.session_id = s.id
            WHERE s.id = ?
            """,
            (session_id,),
        ).fetchone()

        if session_row is None:
            return None

        usage_summary = conn.execute(
            """
            SELECT
                COUNT(*) AS usage_events,
                COALESCE(SUM(input_tokens), 0) AS input_tokens,
                COALESCE(SUM(output_tokens), 0) AS output_tokens,
                COALESCE(SUM(cache_read_tokens), 0) AS cache_read_tokens,
                COALESCE(SUM(cache_write_tokens), 0) AS cache_write_tokens,
                COALESCE(SUM(total_tokens), 0) AS total_tokens,
                COALESCE(SUM(usd_cost), 0.0) AS total_cost_usd
            FROM usage_events
            WHERE session_id = ?
            """,
            (session_id,),
        ).fetchone()

        models = [
            row["model"]
            for row in conn.execute(
                "SELECT DISTINCT model FROM usage_events WHERE session_id = ? ORDER BY model",
                (session_id,),
            ).fetchall()
        ]
        providers = [
            row["provider"]
            for row in conn.execute(
                "SELECT DISTINCT provider FROM usage_events WHERE session_id = ? ORDER BY provider",
                (session_id,),
            ).fetchall()
        ]

        total_items_row = conn.execute(
            "SELECT COUNT(*) AS count FROM raw_events WHERE session_id = ?",
            (session_id,),
        ).fetchone()

        offset = (page - 1) * page_size
        event_rows = conn.execute(
            """
            SELECT
                re.event_id,
                re.session_id,
                re.agent_id,
                re.timestamp,
                re.event_type,
                re.role,
                re.raw_json,
                ue.model,
                ue.provider,
                ue.input_tokens,
                ue.output_tokens,
                ue.cache_read_tokens,
                ue.cache_write_tokens,
                ue.total_tokens,
                ue.usd_cost
            FROM raw_events re
            LEFT JOIN usage_events ue ON ue.event_id = re.event_id
            WHERE re.session_id = ?
            ORDER BY re.timestamp ASC, re.event_id ASC
            LIMIT ? OFFSET ?
            """,
            (session_id, page_size, offset),
        ).fetchall()

    return {
        "session": {
            "session_id": session_row["session_id"],
            "agent_id": session_row["agent_id"],
            "file_path": session_row["file_path"],
            "started_at": session_row["started_at"],
            "ended_at": session_row["ended_at"],
            "total_events": session_row["total_events"],
        },
        "usage_summary": {
            "usage_events": usage_summary["usage_events"],
            "input_tokens": usage_summary["input_tokens"],
            "output_tokens": usage_summary["output_tokens"],
            "cache_read_tokens": usage_summary["cache_read_tokens"],
            "cache_write_tokens": usage_summary["cache_write_tokens"],
            "total_tokens": usage_summary["total_tokens"],
            "total_cost_usd": usage_summary["total_cost_usd"],
            "models": models,
            "providers": providers,
        },
        "events": {
            "page": page,
            "page_size": page_size,
            "total_items": total_items_row["count"],
            "items": [_serialize_event_row(row) for row in event_rows],
        },
    }


def _build_event_where(filters: EventFilters) -> tuple[str, list[object]]:
    clauses: list[str] = []
    params: list[object] = []

    if filters.from_ts:
        clauses.append("re.timestamp >= ?")
        params.append(filters.from_ts)
    if filters.to_ts:
        clauses.append("re.timestamp <= ?")
        params.append(filters.to_ts)
    if filters.event_types:
        clauses.append(f"re.event_type IN ({_in_clause(filters.event_types)})")
        params.extend(filters.event_types)
    if filters.roles:
        clauses.append(f"re.role IN ({_in_clause(filters.roles)})")
        params.extend(filters.roles)
    if filters.agents:
        clauses.append(f"re.agent_id IN ({_in_clause(filters.agents)})")
        params.extend(filters.agents)
    if filters.sessions:
        clauses.append(f"re.session_id IN ({_in_clause(filters.sessions)})")
        params.extend(filters.sessions)
    if filters.usage_bearing_only:
        clauses.append("ue.event_id IS NOT NULL")

    where_sql = ""
    if clauses:
        where_sql = "WHERE " + " AND ".join(clauses)

    return where_sql, params


def query_events(
    db_path: Path,
    filters: EventFilters,
    page: int,
    page_size: int,
) -> dict[str, object]:
    where_sql, params = _build_event_where(filters)

    with get_sqlite_connection(db_path) as conn:
        total_items_row = conn.execute(
            f"""
            SELECT COUNT(*) AS count
            FROM raw_events re
            LEFT JOIN usage_events ue ON ue.event_id = re.event_id
            {where_sql}
            """,
            params,
        ).fetchone()

        offset = (page - 1) * page_size
        rows = conn.execute(
            f"""
            SELECT
                re.event_id,
                re.session_id,
                re.agent_id,
                re.timestamp,
                re.event_type,
                re.role,
                re.raw_json,
                ue.model,
                ue.provider,
                ue.input_tokens,
                ue.output_tokens,
                ue.cache_read_tokens,
                ue.cache_write_tokens,
                ue.total_tokens,
                ue.usd_cost
            FROM raw_events re
            LEFT JOIN usage_events ue ON ue.event_id = re.event_id
            {where_sql}
            ORDER BY re.timestamp DESC, re.event_id DESC
            LIMIT ? OFFSET ?
            """,
            [*params, page_size, offset],
        ).fetchall()

    return {
        "page": page,
        "page_size": page_size,
        "total_items": total_items_row["count"],
        "items": [_serialize_event_row(row) for row in rows],
    }


def _serialize_event_row(row: Any) -> dict[str, object]:
    usage = None
    has_usage = row["model"] is not None
    if has_usage:
        usage = {
            "model": row["model"],
            "provider": row["provider"],
            "input_tokens": row["input_tokens"],
            "output_tokens": row["output_tokens"],
            "cache_read_tokens": row["cache_read_tokens"],
            "cache_write_tokens": row["cache_write_tokens"],
            "total_tokens": row["total_tokens"],
            "usd_cost": row["usd_cost"],
        }

    raw_obj = None
    raw_json = row["raw_json"]
    try:
        raw_obj = json.loads(raw_json)
    except json.JSONDecodeError:
        raw_obj = None

    return {
        "event_id": row["event_id"],
        "session_id": row["session_id"],
        "agent_id": row["agent_id"],
        "timestamp": row["timestamp"],
        "event_type": row["event_type"],
        "role": row["role"],
        "has_usage": has_usage,
        "usage": usage,
        "raw_json": raw_json,
        "raw": raw_obj,
    }
