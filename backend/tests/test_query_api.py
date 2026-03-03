import json
import time
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def _assistant_message(
    *,
    timestamp: str,
    model: str,
    provider: str,
    input_tokens: int,
    output_tokens: int,
    cache_read: int,
    cache_write: int,
    total_tokens: int,
    cost: float,
) -> dict:
    return {
        "type": "message",
        "timestamp": timestamp,
        "message": {
            "role": "assistant",
            "model": model,
            "provider": provider,
            "usage": {
                "input": input_tokens,
                "output": output_tokens,
                "cacheRead": cache_read,
                "cacheWrite": cache_write,
                "totalTokens": total_tokens,
                "cost": {"total": cost},
            },
        },
    }


def _non_usage_message(timestamp: str) -> dict:
    return {
        "type": "message",
        "timestamp": timestamp,
        "message": {
            "role": "user",
            "model": "n/a",
            "provider": "n/a",
        },
    }


def _write_fixture_data(data_root: Path) -> None:
    session_a = data_root / "agent-a" / "sessions" / "session-a.jsonl"
    session_b = data_root / "agent-b" / "sessions" / "session-b.jsonl"

    session_a.parent.mkdir(parents=True, exist_ok=True)
    session_b.parent.mkdir(parents=True, exist_ok=True)

    session_a.write_text(
        "\n".join(
            [
                json.dumps(
                    _assistant_message(
                        timestamp="2026-03-01T10:00:00Z",
                        model="model-alpha",
                        provider="anthropic",
                        input_tokens=5,
                        output_tokens=3,
                        cache_read=1,
                        cache_write=1,
                        total_tokens=10,
                        cost=1.0,
                    )
                ),
                json.dumps(_non_usage_message("2026-03-01T10:01:00Z")),
                json.dumps(
                    _assistant_message(
                        timestamp="2026-03-01T11:00:00Z",
                        model="model-alpha",
                        provider="anthropic",
                        input_tokens=10,
                        output_tokens=8,
                        cache_read=1,
                        cache_write=1,
                        total_tokens=20,
                        cost=2.0,
                    )
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    session_b.write_text(
        json.dumps(
            _assistant_message(
                timestamp="2026-03-02T09:00:00Z",
                model="model-beta",
                provider="openai",
                input_tokens=20,
                output_tokens=15,
                cache_read=3,
                cache_write=2,
                total_tokens=40,
                cost=4.0,
            )
        )
        + "\n",
        encoding="utf-8",
    )


def _build_client_with_fixtures(tmp_path: Path) -> TestClient:
    data_root = tmp_path / "agents"
    db_path = tmp_path / "db" / "clawmon.db"
    _write_fixture_data(data_root)

    settings = Settings(
        data_root=data_root,
        db_path=db_path,
        enrichment_enabled=False,
    )
    app = create_app(settings=settings)
    return TestClient(app)


def _refresh_and_wait(client: TestClient, timeout_seconds: float = 5.0) -> str:
    response = client.post("/api/refresh")
    assert response.status_code == 202

    job_id = response.json()["job_id"]
    deadline = time.time() + timeout_seconds

    while time.time() < deadline:
        status_response = client.get(f"/api/jobs/{job_id}")
        assert status_response.status_code == 200
        payload = status_response.json()
        if payload["status"] in {"completed", "failed"}:
            assert payload["status"] == "completed"
            return job_id
        time.sleep(0.05)

    raise AssertionError("Refresh did not complete in time")


def test_overview_returns_expected_totals_and_top_model(tmp_path: Path) -> None:
    client = _build_client_with_fixtures(tmp_path)
    _refresh_and_wait(client)

    response = client.get("/api/overview")

    assert response.status_code == 200
    payload = response.json()
    summary = payload["summary"]

    assert summary["events"] == 3
    assert summary["input_tokens"] == 35
    assert summary["output_tokens"] == 26
    assert summary["cache_read_tokens"] == 5
    assert summary["cache_write_tokens"] == 4
    assert summary["total_tokens"] == 70
    assert summary["total_cost_usd"] == 7.0

    assert payload["top_model_by_spend"]["model"] == "model-beta"
    assert payload["top_model_by_spend"]["total_cost_usd"] == 4.0


def test_overview_supports_filters(tmp_path: Path) -> None:
    client = _build_client_with_fixtures(tmp_path)
    _refresh_and_wait(client)

    response = client.get(
        "/api/overview",
        params={
            "agent": "agent-a",
            "provider": "anthropic",
            "from": "2026-03-01T00:00:00Z",
            "to": "2026-03-01T23:59:59Z",
        },
    )

    assert response.status_code == 200
    summary = response.json()["summary"]
    assert summary["events"] == 2
    assert summary["total_tokens"] == 30
    assert summary["total_cost_usd"] == 3.0


def test_trends_returns_day_buckets_for_cost_and_tokens(tmp_path: Path) -> None:
    client = _build_client_with_fixtures(tmp_path)
    _refresh_and_wait(client)

    cost_response = client.get("/api/trends", params={"bucket": "day", "metric": "cost"})
    tokens_response = client.get(
        "/api/trends",
        params={"bucket": "day", "metric": "tokens", "provider": "anthropic"},
    )

    assert cost_response.status_code == 200
    assert tokens_response.status_code == 200

    assert cost_response.json()["points"] == [
        {"bucket": "2026-03-01", "value": 3.0},
        {"bucket": "2026-03-02", "value": 4.0},
    ]

    assert tokens_response.json()["points"] == [
        {"bucket": "2026-03-01", "value": 30}
    ]


def test_breakdown_returns_paginated_grouped_results(tmp_path: Path) -> None:
    client = _build_client_with_fixtures(tmp_path)
    _refresh_and_wait(client)

    page1 = client.get(
        "/api/breakdown",
        params={"by": "model", "page": 1, "page_size": 1},
    )
    page2 = client.get(
        "/api/breakdown",
        params={"by": "model", "page": 2, "page_size": 1},
    )

    assert page1.status_code == 200
    assert page2.status_code == 200

    payload1 = page1.json()
    payload2 = page2.json()

    assert payload1["by"] == "model"
    assert payload1["page"] == 1
    assert payload1["page_size"] == 1
    assert payload1["total_items"] == 2
    assert payload1["items"] == [
        {
            "key": "model-beta",
            "events": 1,
            "total_tokens": 40,
            "total_cost_usd": 4.0,
        }
    ]

    assert payload2["items"] == [
        {
            "key": "model-alpha",
            "events": 2,
            "total_tokens": 30,
            "total_cost_usd": 3.0,
        }
    ]
