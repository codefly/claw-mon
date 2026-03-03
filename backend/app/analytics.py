"""Read models for overview/trend/breakdown analytics over usage events."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.db import get_sqlite_connection


@dataclass(frozen=True)
class UsageFilters:
    from_ts: str | None = None
    to_ts: str | None = None
    agents: list[str] | None = None
    models: list[str] | None = None
    providers: list[str] | None = None


def _in_clause(values: list[str]) -> str:
    return ",".join("?" for _ in values)


def _build_usage_where(filters: UsageFilters) -> tuple[str, list[object]]:
    clauses: list[str] = []
    params: list[object] = []

    if filters.from_ts:
        clauses.append("timestamp >= ?")
        params.append(filters.from_ts)
    if filters.to_ts:
        clauses.append("timestamp <= ?")
        params.append(filters.to_ts)

    if filters.agents:
        clauses.append(f"agent_id IN ({_in_clause(filters.agents)})")
        params.extend(filters.agents)
    if filters.models:
        clauses.append(f"model IN ({_in_clause(filters.models)})")
        params.extend(filters.models)
    if filters.providers:
        clauses.append(f"provider IN ({_in_clause(filters.providers)})")
        params.extend(filters.providers)

    where_sql = ""
    if clauses:
        where_sql = "WHERE " + " AND ".join(clauses)
    return where_sql, params


def query_overview(db_path: Path, filters: UsageFilters) -> dict[str, object]:
    where_sql, params = _build_usage_where(filters)

    with get_sqlite_connection(db_path) as conn:
        totals_row = conn.execute(
            f"""
            SELECT
                COUNT(*) AS events,
                COALESCE(SUM(input_tokens), 0) AS input_tokens,
                COALESCE(SUM(output_tokens), 0) AS output_tokens,
                COALESCE(SUM(cache_read_tokens), 0) AS cache_read_tokens,
                COALESCE(SUM(cache_write_tokens), 0) AS cache_write_tokens,
                COALESCE(SUM(total_tokens), 0) AS total_tokens,
                COALESCE(SUM(usd_cost), 0.0) AS total_cost_usd
            FROM usage_events
            {where_sql}
            """,
            params,
        ).fetchone()

        top_model_row = conn.execute(
            f"""
            SELECT model, COALESCE(SUM(usd_cost), 0.0) AS total_cost_usd
            FROM usage_events
            {where_sql}
            GROUP BY model
            ORDER BY total_cost_usd DESC, model ASC
            LIMIT 1
            """,
            params,
        ).fetchone()

    return {
        "summary": {
            "events": totals_row["events"],
            "input_tokens": totals_row["input_tokens"],
            "output_tokens": totals_row["output_tokens"],
            "cache_read_tokens": totals_row["cache_read_tokens"],
            "cache_write_tokens": totals_row["cache_write_tokens"],
            "total_tokens": totals_row["total_tokens"],
            "total_cost_usd": totals_row["total_cost_usd"],
        },
        "top_model_by_spend": (
            {
                "model": top_model_row["model"],
                "total_cost_usd": top_model_row["total_cost_usd"],
            }
            if top_model_row is not None
            else None
        ),
    }


def query_trends(
    db_path: Path,
    filters: UsageFilters,
    bucket: str,
    metric: str,
) -> dict[str, object]:
    if bucket != "day":
        raise ValueError(f"Unsupported bucket: {bucket}")
    if metric not in {"cost", "tokens"}:
        raise ValueError(f"Unsupported metric: {metric}")

    metric_sql = "SUM(usd_cost)" if metric == "cost" else "SUM(total_tokens)"
    where_sql, params = _build_usage_where(filters)

    with get_sqlite_connection(db_path) as conn:
        rows = conn.execute(
            f"""
            SELECT
                SUBSTR(timestamp, 1, 10) AS bucket,
                COALESCE({metric_sql}, 0) AS value
            FROM usage_events
            {where_sql}
            GROUP BY SUBSTR(timestamp, 1, 10)
            ORDER BY bucket ASC
            """,
            params,
        ).fetchall()

    return {
        "bucket": bucket,
        "metric": metric,
        "points": [
            {
                "bucket": row["bucket"],
                "value": row["value"],
            }
            for row in rows
        ],
    }


def query_breakdown(
    db_path: Path,
    filters: UsageFilters,
    by: str,
    page: int,
    page_size: int,
) -> dict[str, object]:
    field_map = {
        "agent": "agent_id",
        "model": "model",
        "provider": "provider",
    }
    group_field = field_map.get(by)
    if group_field is None:
        raise ValueError(f"Unsupported breakdown dimension: {by}")

    where_sql, params = _build_usage_where(filters)

    with get_sqlite_connection(db_path) as conn:
        total_items_row = conn.execute(
            f"""
            SELECT COUNT(*) AS count
            FROM (
                SELECT {group_field}
                FROM usage_events
                {where_sql}
                GROUP BY {group_field}
            )
            """,
            params,
        ).fetchone()

        offset = (page - 1) * page_size
        rows = conn.execute(
            f"""
            SELECT
                {group_field} AS key,
                COUNT(*) AS events,
                COALESCE(SUM(total_tokens), 0) AS total_tokens,
                COALESCE(SUM(usd_cost), 0.0) AS total_cost_usd
            FROM usage_events
            {where_sql}
            GROUP BY {group_field}
            ORDER BY total_cost_usd DESC, total_tokens DESC, key ASC
            LIMIT ? OFFSET ?
            """,
            [*params, page_size, offset],
        ).fetchall()

    return {
        "by": by,
        "page": page,
        "page_size": page_size,
        "total_items": total_items_row["count"],
        "items": [
            {
                "key": row["key"],
                "events": row["events"],
                "total_tokens": row["total_tokens"],
                "total_cost_usd": row["total_cost_usd"],
            }
            for row in rows
        ],
    }
