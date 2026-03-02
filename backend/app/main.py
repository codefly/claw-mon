"""FastAPI application entrypoint."""

from __future__ import annotations

from fastapi import FastAPI

from app.config import Settings
from app.db import check_sqlite_connectivity
from app.logging_config import configure_logging


def create_app(settings: Settings | None = None) -> FastAPI:
    configure_logging()
    app = FastAPI(title="OpenClaw Monitor API", version="0.1.0")

    resolved_settings = settings or Settings.from_env()
    app.state.settings = resolved_settings

    @app.get("/api/health")
    def health() -> dict[str, object]:
        db_ok, db_error = check_sqlite_connectivity(app.state.settings.db_path)
        return {
            "status": "ok" if db_ok else "degraded",
            "service": "openclaw-monitor-backend",
            "db": {
                "status": "ok" if db_ok else "error",
                "path": str(app.state.settings.db_path),
                "error": db_error,
            },
            "config": {
                "data_root": str(app.state.settings.data_root),
                "enrichment_enabled": app.state.settings.enrichment_enabled,
            },
        }

    return app


app = create_app()
