import json
import time
from pathlib import Path

import app.main as main_module
from fastapi.testclient import TestClient

from app.config import Settings
from app.db import get_sqlite_connection
from app.ingestion import IngestionStats
from app.main import create_app


def _assistant_message(timestamp: str) -> dict:
    return {
        "type": "message",
        "timestamp": timestamp,
        "message": {
            "role": "assistant",
            "model": "claude-sonnet-4-6",
            "provider": "anthropic",
            "usage": {
                "input": 100,
                "output": 25,
                "cacheRead": 10,
                "cacheWrite": 5,
                "totalTokens": 140,
                "cost": {"total": 0.0123},
            },
        },
    }


def _build_app_with_data(tmp_path: Path) -> tuple[TestClient, Path]:
    data_root = tmp_path / "agents"
    db_path = tmp_path / "db" / "clawmon.db"

    session_file = data_root / "agent-a" / "sessions" / "session-1.jsonl"
    session_file.parent.mkdir(parents=True, exist_ok=True)
    session_file.write_text(
        json.dumps(_assistant_message("2026-03-02T22:00:01Z")) + "\n",
        encoding="utf-8",
    )

    settings = Settings(
        data_root=data_root,
        db_path=db_path,
        enrichment_enabled=False,
    )
    app = create_app(settings=settings)
    client = TestClient(app)
    return client, db_path


def _wait_for_job_completion(client: TestClient, job_id: str, timeout_seconds: float = 5.0) -> dict:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        response = client.get(f"/api/jobs/{job_id}")
        assert response.status_code == 200
        payload = response.json()
        if payload["status"] in {"completed", "failed"}:
            return payload
        time.sleep(0.05)
    raise AssertionError(f"Job did not complete before timeout: {job_id}")


def test_refresh_endpoint_runs_ingestion_and_persists_job_progress(tmp_path: Path) -> None:
    client, db_path = _build_app_with_data(tmp_path)

    start_response = client.post("/api/refresh")

    assert start_response.status_code == 202
    job_id = start_response.json()["job_id"]

    final_job = _wait_for_job_completion(client, job_id)

    assert final_job["status"] == "completed"
    assert final_job["job_type"] == "refresh"
    assert final_job["progress"]["files_scanned"] == 1
    assert final_job["progress"]["lines_read"] == 1
    assert final_job["progress"]["lines_skipped"] == 0
    assert final_job["progress"]["raw_events_inserted"] == 1
    assert final_job["progress"]["usage_events_inserted"] == 1

    with get_sqlite_connection(db_path) as conn:
        raw_count = conn.execute("SELECT COUNT(*) AS count FROM raw_events").fetchone()[
            "count"
        ]
        usage_count = conn.execute(
            "SELECT COUNT(*) AS count FROM usage_events"
        ).fetchone()["count"]

    assert raw_count == 1
    assert usage_count == 1


def test_refresh_endpoint_rejects_concurrent_refresh_jobs(tmp_path: Path, monkeypatch) -> None:
    client, _ = _build_app_with_data(tmp_path)

    def slow_ingestion(**_kwargs) -> IngestionStats:
        time.sleep(0.35)
        return IngestionStats(files_scanned=1)

    monkeypatch.setattr(main_module, "ingest_data_root", slow_ingestion)

    first = client.post("/api/refresh")
    assert first.status_code == 202

    second = client.post("/api/refresh")
    assert second.status_code == 409
    assert "already running" in second.json()["detail"].lower()

    _wait_for_job_completion(client, first.json()["job_id"])


def test_get_job_returns_404_for_unknown_id(tmp_path: Path) -> None:
    client, _ = _build_app_with_data(tmp_path)

    response = client.get("/api/jobs/missing-job")

    assert response.status_code == 404
