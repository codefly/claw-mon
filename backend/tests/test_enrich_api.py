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


def _create_client(tmp_path: Path, budget_usd: float = 0.25) -> tuple[TestClient, Path, Path]:
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
            enrichment_model="local-heuristic-v1",
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
