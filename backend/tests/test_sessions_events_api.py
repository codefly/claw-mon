import json
import time
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def _event(
    *,
    event_type: str,
    timestamp: str,
    role: str | None = None,
    model: str | None = None,
    provider: str | None = None,
    with_usage: bool = False,
) -> dict:
    event: dict = {
        "type": event_type,
        "timestamp": timestamp,
    }

    if event_type == "message":
        message = {
            "role": role,
            "model": model or "unknown-model",
            "provider": provider or "unknown-provider",
        }
        if with_usage:
            message["usage"] = {
                "input": 7,
                "output": 3,
                "cacheRead": 1,
                "cacheWrite": 1,
                "totalTokens": 12,
                "cost": {"total": 0.42},
            }
        event["message"] = message
    else:
        event["payload"] = {"kind": event_type}

    return event


def _setup_fixture_app(tmp_path: Path) -> TestClient:
    data_root = tmp_path / "agents"
    db_path = tmp_path / "db" / "clawmon.db"

    session1 = data_root / "agent-a" / "sessions" / "session-1.jsonl"
    session2 = data_root / "agent-b" / "sessions" / "session-2.jsonl"

    session1.parent.mkdir(parents=True, exist_ok=True)
    session2.parent.mkdir(parents=True, exist_ok=True)

    session1_events = [
        _event(
            event_type="message",
            timestamp="2026-03-01T09:00:00Z",
            role="user",
            model="model-alpha",
            provider="anthropic",
        ),
        _event(
            event_type="message",
            timestamp="2026-03-01T09:01:00Z",
            role="assistant",
            model="model-alpha",
            provider="anthropic",
            with_usage=True,
        ),
        _event(
            event_type="tool",
            timestamp="2026-03-01T09:02:00Z",
        ),
    ]
    session2_events = [
        _event(
            event_type="message",
            timestamp="2026-03-02T10:00:00Z",
            role="system",
            model="model-beta",
            provider="openai",
        ),
        _event(
            event_type="message",
            timestamp="2026-03-02T10:01:00Z",
            role="assistant",
            model="model-beta",
            provider="openai",
            with_usage=True,
        ),
        _event(
            event_type="message",
            timestamp="2026-03-02T10:02:00Z",
            role="assistant",
            model="model-beta",
            provider="openai",
            with_usage=False,
        ),
    ]

    session1.write_text("\n".join(json.dumps(e) for e in session1_events) + "\n", encoding="utf-8")
    session2.write_text("\n".join(json.dumps(e) for e in session2_events) + "\n", encoding="utf-8")

    app = create_app(
        settings=Settings(
            data_root=data_root,
            db_path=db_path,
            enrichment_enabled=False,
        )
    )
    client = TestClient(app)

    start = client.post("/api/refresh")
    assert start.status_code == 202
    job_id = start.json()["job_id"]

    deadline = time.time() + 5
    while time.time() < deadline:
        status_response = client.get(f"/api/jobs/{job_id}")
        payload = status_response.json()
        if payload["status"] == "completed":
            break
        if payload["status"] == "failed":
            raise AssertionError(payload)
        time.sleep(0.05)

    return client


def test_sessions_endpoint_is_paginated_and_sorted(tmp_path: Path) -> None:
    client = _setup_fixture_app(tmp_path)

    page1 = client.get("/api/sessions", params={"page": 1, "page_size": 1})
    page2 = client.get("/api/sessions", params={"page": 2, "page_size": 1})

    assert page1.status_code == 200
    assert page2.status_code == 200

    payload1 = page1.json()
    payload2 = page2.json()

    assert payload1["total_items"] == 2
    assert payload1["items"][0]["session_id"] == "session-2"
    assert payload2["items"][0]["session_id"] == "session-1"


def test_sessions_endpoint_filters_by_agent_and_model(tmp_path: Path) -> None:
    client = _setup_fixture_app(tmp_path)

    response = client.get(
        "/api/sessions",
        params={"agent": "agent-a", "model": "model-alpha"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_items"] == 1
    item = payload["items"][0]
    assert item["session_id"] == "session-1"
    assert item["agent_id"] == "agent-a"
    assert item["total_tokens"] == 12


def test_session_detail_returns_mixed_timeline_and_usage_summary(tmp_path: Path) -> None:
    client = _setup_fixture_app(tmp_path)

    response = client.get("/api/sessions/session-1", params={"page": 1, "page_size": 10})

    assert response.status_code == 200
    payload = response.json()

    assert payload["session"]["session_id"] == "session-1"
    assert payload["session"]["total_events"] == 3

    usage_summary = payload["usage_summary"]
    assert usage_summary["usage_events"] == 1
    assert usage_summary["total_tokens"] == 12
    assert usage_summary["total_cost_usd"] == 0.42

    events = payload["events"]
    assert events["total_items"] == 3
    assert events["items"][0]["event_type"] == "message"
    assert events["items"][1]["has_usage"] is True


def test_events_endpoint_supports_filters_and_usage_bearing_toggle(tmp_path: Path) -> None:
    client = _setup_fixture_app(tmp_path)

    response = client.get(
        "/api/events",
        params={
            "type": "message",
            "role": "assistant",
            "usage_bearing_only": "true",
            "page": 1,
            "page_size": 10,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_items"] == 2
    assert all(item["has_usage"] for item in payload["items"])

    timestamps = [item["timestamp"] for item in payload["items"]]
    assert timestamps == sorted(timestamps, reverse=True)


def test_session_detail_returns_404_for_missing_session(tmp_path: Path) -> None:
    client = _setup_fixture_app(tmp_path)

    response = client.get("/api/sessions/missing-session")

    assert response.status_code == 404
