import json
import time
from pathlib import Path

import app.enrichment as enrichment_module
from fastapi.testclient import TestClient

from app.config import Settings
from app.db import get_sqlite_connection
from app.main import create_app


def _assistant_usage_event(timestamp: str, text: str) -> dict:
    return {
        "type": "message",
        "timestamp": timestamp,
        "message": {
            "role": "assistant",
            "model": "model-enrich",
            "provider": "anthropic",
            "content": [{"type": "text", "text": text}],
            "usage": {
                "input": 20,
                "output": 10,
                "cacheRead": 2,
                "cacheWrite": 1,
                "totalTokens": 33,
                "cost": {"total": 0.0042},
            },
        },
    }


def _create_client(
    tmp_path: Path,
    budget_usd: float = 0.25,
    enrichment_provider: str = "local",
    enrichment_model: str = "local-heuristic-v1",
    openai_api_key: str | None = None,
    input_cost_per_1m_usd: float = 0.0,
    output_cost_per_1m_usd: float = 0.0,
) -> tuple[TestClient, Path, Path]:
    data_root = tmp_path / "agents"
    db_path = tmp_path / "db" / "clawmon.db"

    session1 = data_root / "agent-a" / "sessions" / "session-1.jsonl"
    session2 = data_root / "agent-b" / "sessions" / "session-2.jsonl"
    session1.parent.mkdir(parents=True, exist_ok=True)
    session2.parent.mkdir(parents=True, exist_ok=True)

    session1.write_text(
        json.dumps(_assistant_usage_event("2026-03-02T10:00:00Z", "design architecture plan"))
        + "\n",
        encoding="utf-8",
    )
    session2.write_text(
        json.dumps(_assistant_usage_event("2026-03-02T11:00:00Z", "debug error traceback fix"))
        + "\n",
        encoding="utf-8",
    )

    app = create_app(
        settings=Settings(
            data_root=data_root,
            db_path=db_path,
            enrichment_enabled=True,
            enrichment_budget_usd=budget_usd,
            enrichment_provider=enrichment_provider,
            enrichment_model=enrichment_model,
            enrichment_openai_api_key=openai_api_key,
            enrichment_input_cost_per_1m_usd=input_cost_per_1m_usd,
            enrichment_output_cost_per_1m_usd=output_cost_per_1m_usd,
        )
    )
    client = TestClient(app)

    refresh = client.post("/api/refresh")
    assert refresh.status_code == 202
    _wait_for_job(client, refresh.json()["job_id"])

    return client, db_path, data_root


def _wait_for_job(client: TestClient, job_id: str, timeout_seconds: float = 5.0) -> dict:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        response = client.get(f"/api/jobs/{job_id}")
        assert response.status_code == 200
        payload = response.json()
        if payload["status"] in {"completed", "failed"}:
            return payload
        time.sleep(0.05)
    raise AssertionError(f"Job did not complete in time: {job_id}")


def test_enrich_endpoint_writes_session_enrichment(tmp_path: Path) -> None:
    client, db_path, _ = _create_client(tmp_path)

    response = client.post("/api/enrich")
    assert response.status_code == 202

    final_job = _wait_for_job(client, response.json()["job_id"])
    assert final_job["status"] == "completed"
    assert final_job["progress"]["sessions_considered"] == 2
    assert final_job["progress"]["sessions_enriched"] == 2
    assert final_job["progress"]["sessions_skipped_unchanged"] == 0
    assert final_job["progress"]["sessions_failed"] == 0
    assert final_job["progress"]["sessions_fallback_local"] == 0

    with get_sqlite_connection(db_path) as conn:
        rows = conn.execute(
            """
            SELECT session_id, primary_category, summary, confidence, model_used, content_hash
            FROM session_enrichment
            ORDER BY session_id
            """
        ).fetchall()

    assert len(rows) == 2
    assert rows[0]["model_used"] == "local-heuristic-v1"
    assert rows[0]["content_hash"]


def test_enrich_with_openai_provider_success(tmp_path: Path, monkeypatch) -> None:
    client, db_path, _ = _create_client(
        tmp_path,
        enrichment_provider="openai",
        enrichment_model="gpt-4.1-mini",
        openai_api_key="test-key",
        input_cost_per_1m_usd=0.4,
        output_cost_per_1m_usd=1.2,
    )

    def mock_openai_call(**kwargs) -> dict:
        return {
            "model": kwargs["model_name"],
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "primary_category": "architecture",
                                "secondary_categories": ["planning", "debugging"],
                                "summary": "Session focused on planning architecture changes.",
                                "confidence": 0.86,
                            }
                        )
                    }
                }
            ],
            "usage": {"prompt_tokens": 1000, "completion_tokens": 200},
        }

    monkeypatch.setattr(enrichment_module, "_call_openai_chat_completion", mock_openai_call)

    response = client.post("/api/enrich")
    assert response.status_code == 202
    final_job = _wait_for_job(client, response.json()["job_id"])

    assert final_job["status"] == "completed"
    assert final_job["progress"]["sessions_enriched"] == 2
    assert final_job["progress"]["sessions_fallback_local"] == 0
    assert final_job["progress"]["budget_spent_actual_usd"] > 0

    with get_sqlite_connection(db_path) as conn:
        row = conn.execute(
            "SELECT model_used, summary, primary_category FROM session_enrichment WHERE session_id = ?",
            ("session-1",),
        ).fetchone()

    assert row["model_used"] == "gpt-4.1-mini"
    assert row["primary_category"] == "architecture"
    assert "[fallback:" not in row["summary"]


def test_enrich_skips_unchanged_sessions(tmp_path: Path) -> None:
    client, _, _ = _create_client(tmp_path)

    first = client.post("/api/enrich")
    assert first.status_code == 202
    _wait_for_job(client, first.json()["job_id"])

    second = client.post("/api/enrich")
    assert second.status_code == 202
    final_job = _wait_for_job(client, second.json()["job_id"])

    assert final_job["status"] == "completed"
    assert final_job["progress"]["sessions_enriched"] == 0
    assert final_job["progress"]["sessions_skipped_unchanged"] == 2


def test_enrich_updates_changed_session_content_hash(tmp_path: Path) -> None:
    client, db_path, data_root = _create_client(tmp_path)

    first = client.post("/api/enrich")
    assert first.status_code == 202
    _wait_for_job(client, first.json()["job_id"])

    with get_sqlite_connection(db_path) as conn:
        original_hash = conn.execute(
            "SELECT content_hash FROM session_enrichment WHERE session_id = ?",
            ("session-1",),
        ).fetchone()["content_hash"]

    session1_file = data_root / "agent-a" / "sessions" / "session-1.jsonl"
    with session1_file.open("a", encoding="utf-8") as handle:
        handle.write(
            json.dumps(_assistant_usage_event("2026-03-02T12:00:00Z", "docs update guide")) + "\n"
        )

    refresh = client.post("/api/refresh")
    assert refresh.status_code == 202
    _wait_for_job(client, refresh.json()["job_id"])

    enrich = client.post("/api/enrich")
    assert enrich.status_code == 202
    final_job = _wait_for_job(client, enrich.json()["job_id"])

    assert final_job["progress"]["sessions_enriched"] >= 1

    with get_sqlite_connection(db_path) as conn:
        updated_hash = conn.execute(
            "SELECT content_hash FROM session_enrichment WHERE session_id = ?",
            ("session-1",),
        ).fetchone()["content_hash"]

    assert updated_hash != original_hash


def test_enrich_respects_budget_cap(tmp_path: Path) -> None:
    client, _, _ = _create_client(tmp_path, budget_usd=0.0)

    response = client.post("/api/enrich")
    assert response.status_code == 202
    final_job = _wait_for_job(client, response.json()["job_id"])

    assert final_job["status"] == "completed"
    assert final_job["progress"]["sessions_enriched"] == 0
    assert final_job["progress"]["budget_capped"] is True


def test_enrich_isolates_session_failures(tmp_path: Path, monkeypatch) -> None:
    client, _, _ = _create_client(tmp_path)

    original_classifier = enrichment_module._classify_session

    def flaky_classifier(session_id: str, content: str) -> dict[str, object]:
        if session_id == "session-1":
            raise RuntimeError("synthetic failure")
        return original_classifier(session_id, content)

    monkeypatch.setattr(enrichment_module, "_classify_session", flaky_classifier)

    response = client.post("/api/enrich")
    assert response.status_code == 202
    final_job = _wait_for_job(client, response.json()["job_id"])

    assert final_job["status"] == "completed"
    assert final_job["progress"]["sessions_failed"] == 1
    assert final_job["progress"]["sessions_enriched"] == 1


def test_enrich_openai_failure_falls_back_to_local(tmp_path: Path, monkeypatch) -> None:
    client, db_path, _ = _create_client(
        tmp_path,
        enrichment_provider="openai",
        enrichment_model="gpt-4.1-mini",
        openai_api_key="test-key",
    )

    def fail_openai_call(**_kwargs) -> dict:
        raise RuntimeError("synthetic provider failure")

    monkeypatch.setattr(enrichment_module, "_call_openai_chat_completion", fail_openai_call)

    response = client.post("/api/enrich")
    assert response.status_code == 202
    final_job = _wait_for_job(client, response.json()["job_id"])

    assert final_job["status"] == "completed"
    assert final_job["progress"]["sessions_failed"] == 0
    assert final_job["progress"]["sessions_fallback_local"] == 2

    with get_sqlite_connection(db_path) as conn:
        rows = conn.execute(
            "SELECT model_used, summary FROM session_enrichment ORDER BY session_id"
        ).fetchall()

    assert all(row["model_used"] == "local-heuristic-v1" for row in rows)
    assert all("[fallback: openai_error:RuntimeError]" in row["summary"] for row in rows)


def test_enrich_openai_malformed_response_falls_back_to_local(
    tmp_path: Path, monkeypatch
) -> None:
    client, db_path, _ = _create_client(
        tmp_path,
        enrichment_provider="openai",
        enrichment_model="gpt-4.1-mini",
        openai_api_key="test-key",
    )

    def malformed_openai_call(**_kwargs) -> dict:
        return {
            "model": "gpt-4.1-mini",
            "choices": [{"message": {"content": "not-a-json-object"}}],
            "usage": {"prompt_tokens": 120, "completion_tokens": 20},
        }

    monkeypatch.setattr(enrichment_module, "_call_openai_chat_completion", malformed_openai_call)

    response = client.post("/api/enrich")
    assert response.status_code == 202
    final_job = _wait_for_job(client, response.json()["job_id"])

    assert final_job["status"] == "completed"
    assert final_job["progress"]["sessions_failed"] == 0
    assert final_job["progress"]["sessions_fallback_local"] == 2

    with get_sqlite_connection(db_path) as conn:
        row = conn.execute(
            "SELECT summary FROM session_enrichment WHERE session_id = ?",
            ("session-1",),
        ).fetchone()

    assert "[fallback: openai_error:JSONDecodeError]" in row["summary"]
