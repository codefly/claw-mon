"""Session enrichment pipeline with provider-backed LLM support and fallback."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from app.db import apply_migrations
from app.db import get_sqlite_connection

_LOCAL_MODEL = "local-heuristic-v1"
_MAX_PROMPT_CHARS = 14000


@dataclass
class EnrichmentStats:
    sessions_considered: int = 0
    sessions_enriched: int = 0
    sessions_skipped_unchanged: int = 0
    sessions_failed: int = 0
    sessions_fallback_local: int = 0
    budget_spent_usd: float = 0.0
    budget_spent_estimated_usd: float = 0.0
    budget_spent_actual_usd: float = 0.0
    budget_capped: bool = False


@dataclass(frozen=True)
class ClassificationResult:
    primary_category: str
    secondary_categories: list[str]
    summary: str
    confidence: float
    model_used: str
    actual_cost_usd: float | None = None
    fallback_reason: str | None = None


def enrich_sessions(
    db_path: Path,
    budget_usd: float,
    model_name: str,
    provider: str = "local",
    openai_api_key: str | None = None,
    openai_base_url: str = "https://api.openai.com/v1",
    timeout_seconds: float = 30.0,
    input_cost_per_1m_usd: float = 0.0,
    output_cost_per_1m_usd: float = 0.0,
) -> EnrichmentStats:
    apply_migrations(db_path)
    stats = EnrichmentStats()

    with get_sqlite_connection(db_path) as conn:
        sessions = conn.execute(
            "SELECT id AS session_id FROM sessions ORDER BY id"
        ).fetchall()

    normalized_provider = provider.strip().lower() if provider else "local"
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

            estimated_cost = _estimate_enrichment_cost(
                content=content_text,
                provider=normalized_provider,
                input_cost_per_1m_usd=input_cost_per_1m_usd,
                output_cost_per_1m_usd=output_cost_per_1m_usd,
            )
            if stats.budget_spent_actual_usd + estimated_cost > budget_usd:
                stats.budget_capped = True
                break

            classification = _classify_session_with_fallback(
                session_id=session_id,
                content=content_text,
                provider=normalized_provider,
                model_name=model_name,
                openai_api_key=openai_api_key,
                openai_base_url=openai_base_url,
                timeout_seconds=timeout_seconds,
                input_cost_per_1m_usd=input_cost_per_1m_usd,
                output_cost_per_1m_usd=output_cost_per_1m_usd,
            )

            if classification.actual_cost_usd is None:
                actual_cost = estimated_cost
            else:
                actual_cost = classification.actual_cost_usd

            summary = f"{classification.summary} (events={event_count})"
            if classification.fallback_reason:
                summary = f"{summary} [fallback: {classification.fallback_reason}]"
                stats.sessions_fallback_local += 1

            _upsert_session_enrichment(
                db_path=db_path,
                session_id=session_id,
                content_hash=content_hash,
                estimated_cost_usd=actual_cost,
                primary_category=classification.primary_category,
                secondary_categories=classification.secondary_categories,
                summary=summary,
                confidence=classification.confidence,
                model_used=classification.model_used,
            )

            stats.sessions_enriched += 1
            stats.budget_spent_estimated_usd += estimated_cost
            stats.budget_spent_actual_usd += actual_cost
            stats.budget_spent_usd = stats.budget_spent_actual_usd
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


def _estimate_enrichment_cost(
    content: str,
    provider: str,
    input_cost_per_1m_usd: float,
    output_cost_per_1m_usd: float,
) -> float:
    if provider == "openai" and (input_cost_per_1m_usd > 0 or output_cost_per_1m_usd > 0):
        clipped = content[:_MAX_PROMPT_CHARS]
        prompt_tokens = max((len(clipped) / 4.0) + 250.0, 1.0)
        completion_tokens = 180.0
        return (
            (prompt_tokens * max(input_cost_per_1m_usd, 0.0))
            + (completion_tokens * max(output_cost_per_1m_usd, 0.0))
        ) / 1_000_000.0

    approx_tokens = max(len(content) / 4.0, 1.0)
    return approx_tokens * 0.0000005


def _classify_session_with_fallback(
    session_id: str,
    content: str,
    provider: str,
    model_name: str,
    openai_api_key: str | None,
    openai_base_url: str,
    timeout_seconds: float,
    input_cost_per_1m_usd: float,
    output_cost_per_1m_usd: float,
) -> ClassificationResult:
    if provider in {"", "local", "heuristic"}:
        local = _classify_session(session_id=session_id, content=content)
        return ClassificationResult(
            primary_category=str(local["primary_category"]),
            secondary_categories=list(local["secondary_categories"]),
            summary=str(local["summary"]),
            confidence=float(local["confidence"]),
            model_used=_LOCAL_MODEL,
            actual_cost_usd=None,
        )

    if provider == "openai":
        try:
            return _classify_with_openai(
                session_id=session_id,
                content=content,
                model_name=model_name,
                openai_api_key=openai_api_key,
                openai_base_url=openai_base_url,
                timeout_seconds=timeout_seconds,
                input_cost_per_1m_usd=input_cost_per_1m_usd,
                output_cost_per_1m_usd=output_cost_per_1m_usd,
            )
        except Exception as exc:
            local = _classify_session(session_id=session_id, content=content)
            return ClassificationResult(
                primary_category=str(local["primary_category"]),
                secondary_categories=list(local["secondary_categories"]),
                summary=str(local["summary"]),
                confidence=float(local["confidence"]),
                model_used=_LOCAL_MODEL,
                actual_cost_usd=None,
                fallback_reason=f"openai_error:{exc.__class__.__name__}",
            )

    local = _classify_session(session_id=session_id, content=content)
    return ClassificationResult(
        primary_category=str(local["primary_category"]),
        secondary_categories=list(local["secondary_categories"]),
        summary=str(local["summary"]),
        confidence=float(local["confidence"]),
        model_used=_LOCAL_MODEL,
        actual_cost_usd=None,
        fallback_reason=f"unsupported_provider:{provider}",
    )


def _classify_with_openai(
    session_id: str,
    content: str,
    model_name: str,
    openai_api_key: str | None,
    openai_base_url: str,
    timeout_seconds: float,
    input_cost_per_1m_usd: float,
    output_cost_per_1m_usd: float,
) -> ClassificationResult:
    if not openai_api_key:
        raise ValueError("missing_openai_api_key")

    response_payload = _call_openai_chat_completion(
        api_key=openai_api_key,
        base_url=openai_base_url,
        model_name=model_name,
        session_id=session_id,
        content=content,
        timeout_seconds=timeout_seconds,
    )
    parsed = _extract_openai_classification(response_payload)
    actual_cost = _estimate_openai_actual_cost(
        response_payload,
        input_cost_per_1m_usd=input_cost_per_1m_usd,
        output_cost_per_1m_usd=output_cost_per_1m_usd,
    )

    model_used = response_payload.get("model")
    if not isinstance(model_used, str) or not model_used:
        model_used = model_name

    return ClassificationResult(
        primary_category=parsed["primary_category"],
        secondary_categories=parsed["secondary_categories"],
        summary=parsed["summary"],
        confidence=parsed["confidence"],
        model_used=model_used,
        actual_cost_usd=actual_cost,
    )


def _call_openai_chat_completion(
    api_key: str,
    base_url: str,
    model_name: str,
    session_id: str,
    content: str,
    timeout_seconds: float,
) -> dict[str, Any]:
    endpoint = base_url.rstrip("/") + "/chat/completions"
    clipped = content[:_MAX_PROMPT_CHARS]

    system_prompt = (
        "You classify OpenClaw coding sessions. Respond with JSON only. "
        "Schema: {"
        '"primary_category": string, '
        '"secondary_categories": string[], '
        '"summary": string, '
        '"confidence": number'
        "}."
    )
    user_prompt = (
        f"Session ID: {session_id}\n"
        "Classify the work type from this session payload. "
        "Use short category labels, confidence in [0,1], and summary <= 220 chars.\n\n"
        f"Session payload excerpt:\n{clipped}"
    )

    with httpx.Client(timeout=timeout_seconds) as client:
        response = client.post(
            endpoint,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model_name,
                "temperature": 0,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            },
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("openai_response_not_object")
        return payload


def _extract_openai_classification(payload: dict[str, Any]) -> dict[str, Any]:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError("openai_missing_choices")

    first = choices[0]
    if not isinstance(first, dict):
        raise ValueError("openai_choice_not_object")

    message = first.get("message")
    if not isinstance(message, dict):
        raise ValueError("openai_missing_message")

    content = message.get("content")
    if isinstance(content, list):
        text_parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    text_parts.append(text)
        content = "\n".join(text_parts)

    if not isinstance(content, str) or not content.strip():
        raise ValueError("openai_missing_content")

    parsed = _parse_json_content(content)
    if not isinstance(parsed, dict):
        raise ValueError("openai_content_not_json_object")

    primary = parsed.get("primary_category")
    if not isinstance(primary, str) or not primary.strip():
        raise ValueError("invalid_primary_category")

    secondary_raw = parsed.get("secondary_categories")
    secondary: list[str] = []
    if secondary_raw is None:
        secondary = []
    elif isinstance(secondary_raw, list):
        for item in secondary_raw:
            if isinstance(item, str) and item.strip():
                secondary.append(item.strip())
    else:
        raise ValueError("invalid_secondary_categories")

    summary = parsed.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        raise ValueError("invalid_summary")

    confidence_raw = parsed.get("confidence")
    confidence = _coerce_float(confidence_raw, default=-1.0)
    if confidence < 0.0 or confidence > 1.0:
        raise ValueError("invalid_confidence")

    return {
        "primary_category": primary.strip(),
        "secondary_categories": secondary[:5],
        "summary": summary.strip(),
        "confidence": confidence,
    }


def _parse_json_content(content: str) -> Any:
    raw = content.strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.lower().startswith("json"):
            raw = raw[4:].strip()
    return json.loads(raw)


def _estimate_openai_actual_cost(
    payload: dict[str, Any],
    input_cost_per_1m_usd: float,
    output_cost_per_1m_usd: float,
) -> float | None:
    usage = payload.get("usage")
    if not isinstance(usage, dict):
        return None

    if input_cost_per_1m_usd <= 0 and output_cost_per_1m_usd <= 0:
        return None

    prompt_tokens = _coerce_int(usage.get("prompt_tokens"), default=0)
    completion_tokens = _coerce_int(usage.get("completion_tokens"), default=0)
    return (
        (prompt_tokens * max(input_cost_per_1m_usd, 0.0))
        + (completion_tokens * max(output_cost_per_1m_usd, 0.0))
    ) / 1_000_000.0


def _coerce_float(value: Any, default: float) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _coerce_int(value: Any, default: int) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _classify_session(session_id: str, content: str) -> dict[str, object]:
    lowered = content.lower()

    keyword_map: list[tuple[str, str, list[str]]] = [
        (
            "debugging",
            "Debug-oriented activity detected",
            ["error", "exception", "traceback", "bug", "fix"],
        ),
        (
            "planning/design",
            "Planning and architecture activity detected",
            ["plan", "design", "architecture", "tradeoff"],
        ),
        (
            "operations/devops",
            "Operational and infrastructure activity detected",
            ["deploy", "docker", "kubernetes", "infra", "prod"],
        ),
        (
            "documentation",
            "Documentation work detected",
            ["readme", "docs", "documentation", "guide"],
        ),
        (
            "research",
            "Research-oriented activity detected",
            ["research", "investigate", "compare", "evaluate"],
        ),
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
