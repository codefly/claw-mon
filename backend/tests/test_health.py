from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def test_health_endpoint_returns_service_and_db_status(tmp_path: Path) -> None:
    settings = Settings(
        data_root=tmp_path / "agents",
        db_path=tmp_path / "db" / "clawmon.db",
        enrichment_enabled=False,
    )
    app = create_app(settings=settings)
    client = TestClient(app)

    response = client.get("/api/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["service"] == "openclaw-monitor-backend"
    assert payload["db"]["status"] == "ok"
    assert payload["db"]["path"].endswith("clawmon.db")
    assert payload["config"]["enrichment_enabled"] is False
