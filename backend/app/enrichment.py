"""Session enrichment pipeline with content-hash caching and budget controls."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from app.db import apply_migrations
from app.db import get_sqlite_connection


@dataclass
class EnrichmentStats:
    sessions_considered: int = 0
    sessions_enriched: int = 0
    sessions_skipped_unchanged: int = 0
    sessions_failed: int = 0
    budget_spent_usd: float = 0.0
    budget_capped: bool = False


def enrich_sessions(
    db_path: Path,
    budget_usd: float,
    model_name: str,
) -> EnrichmentStats:
    apply_migrations(db_path)
    stats = EnrichmentStats()

    with get_sqlite_connection(db_path) as conn:
        sessions = conn.execute(
            "SELECT id AS session_id FROM sessions ORDER BY id"
        ).fetchall()

    for session in sessions:
        session_id = session["session_id"]
        stats.sessions_considered += 1

        try:
            session_payload = _load_session_payload(db_path, session_id)
            if session_payload is None:
                continue

            content_hash, content_text, event_count = session_payload
            previous = _get_existing_enrichment(db_path, session_id)
            if previous and previous.get("content_hash") == content_hash:
                stats.sessions_skipped_unchanged += 1
                continue

            estimated_cost = _estimate_enrichment_cost(content_text)
            if stats.budget_spent_usd + estimated_cost > budget_usd:
                stats.budget_capped = True
                break

            classification = _classify_session(session_id=session_id, content=content_text)

            _upsert_session_enrichment(
                db_path=db_path,
                session_id=session_id,
                content_hash=content_hash,
                estimated_cost_usd=estimated_cost,
                primary_category=classification["primary_category"],
                secondary_categories=classification["secondary_categories"],
                summary=f"{classification['summary']} (events={event_count})",
                confidence=classification["confidence"],
                model_used=model_name,
            )

            stats.sessions_enriched += 1
            stats.budget_spent_usd += estimated_cost
        except Exception:
            stats.sessions_failed += 1
            continue

    return stats


def _load_session_payload(db_path: Path, session_id: str) -> tuple[str, str, int] | None:
    with get_sqlite_connection(db_path) as conn:
        rows = conn.execute(
            """
            SELECT raw_json
            FROM raw_events
            WHERE session_id = ?
            ORDER BY timestamp ASC, event_id ASC
            """,
            (session_id,),
        ).fetchall()

    if not rows:
        return None

    raw_chunks = [row["raw_json"] for row in rows]
    content_text = "\n".join(raw_chunks)
    content_hash = hashlib.sha256(content_text.encode("utf-8")).hexdigest()
    return content_hash, content_text, len(rows)


def _get_existing_enrichment(db_path: Path, session_id: str) -> dict[str, object] | None:
    with get_sqlite_connection(db_path) as conn:
        row = conn.execute(
            """
            SELECT content_hash
            FROM session_enrichment
            WHERE session_id = ?
            """,
            (session_id,),
        ).fetchone()

    if row is None:
        return None
    return {"content_hash": row["content_hash"]}


def _estimate_enrichment_cost(content: str) -> float:
    approx_tokens = max(len(content) / 4.0, 1.0)
    return approx_tokens * 0.0000005


def _classify_session(session_id: str, content: str) -> dict[str, object]:
    lowered = content.lower()

    keyword_map: list[tuple[str, str, list[str]]] = [
        ("debugging", "Debug-oriented activity detected", ["error", "exception", "traceback", "bug", "fix"]),
        ("planning/design", "Planning and architecture activity detected", ["plan", "design", "architecture", "tradeoff"]),
        ("operations/devops", "Operational and infrastructure activity detected", ["deploy", "docker", "kubernetes", "infra", "prod"]),
        ("documentation", "Documentation work detected", ["readme", "docs", "documentation", "guide"]),
        ("research", "Research-oriented activity detected", ["research", "investigate", "compare", "evaluate"]),
    ]

    secondary: list[str] = []
    for category, _summary, keywords in keyword_map:
        if any(keyword in lowered for keyword in keywords):
            secondary.append(category)

    if secondary:
        primary = secondary[0]
        confidence = 0.78
        summary = f"{primary} classification inferred for {session_id}"
    else:
        primary = "coding"
        confidence = 0.56
        summary = f"coding classification inferred for {session_id}"

    return {
        "primary_category": primary,
        "secondary_categories": secondary[1:] if len(secondary) > 1 else [],
        "summary": summary,
        "confidence": confidence,
    }


def _upsert_session_enrichment(
    db_path: Path,
    session_id: str,
    content_hash: str,
    estimated_cost_usd: float,
    primary_category: str,
    secondary_categories: list[str],
    summary: str,
    confidence: float,
    model_used: str,
) -> None:
    with get_sqlite_connection(db_path) as conn:
        conn.execute(
            """
            INSERT INTO session_enrichment(
                session_id,
                primary_category,
                secondary_categories,
                summary,
                confidence,
                model_used,
                content_hash,
                estimated_cost_usd,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(session_id) DO UPDATE SET
                primary_category = excluded.primary_category,
                secondary_categories = excluded.secondary_categories,
                summary = excluded.summary,
                confidence = excluded.confidence,
                model_used = excluded.model_used,
                content_hash = excluded.content_hash,
                estimated_cost_usd = excluded.estimated_cost_usd,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                session_id,
                primary_category,
                json.dumps(secondary_categories),
                summary,
                confidence,
                model_used,
                content_hash,
                estimated_cost_usd,
            ),
        )
