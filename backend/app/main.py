"""FastAPI application entrypoint."""

from __future__ import annotations

import threading
from dataclasses import asdict

from fastapi import FastAPI
from fastapi import HTTPException
from fastapi import status

from app.config import Settings
from app.db import apply_migrations
from app.db import check_sqlite_connectivity
from app.ingestion import ingest_data_root
from app.jobs import create_job
from app.jobs import get_job
from app.jobs import set_job_completed
from app.jobs import set_job_failed
from app.jobs import set_job_running
from app.logging_config import configure_logging


def create_app(settings: Settings | None = None) -> FastAPI:
    configure_logging()
    app = FastAPI(title="OpenClaw Monitor API", version="0.1.0")

    resolved_settings = settings or Settings.from_env()
    app.state.settings = resolved_settings
    apply_migrations(app.state.settings.db_path)
    app.state.refresh_lock = threading.Lock()

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

    def _run_refresh_job(job_id: str) -> None:
        try:
            set_job_running(app.state.settings.db_path, job_id)
            stats = ingest_data_root(
                db_path=app.state.settings.db_path,
                data_root=app.state.settings.data_root,
            )
            set_job_completed(
                app.state.settings.db_path,
                job_id,
                progress=asdict(stats),
            )
        except Exception as exc:
            set_job_failed(app.state.settings.db_path, job_id, error=str(exc))
        finally:
            app.state.refresh_lock.release()

    @app.post("/api/refresh", status_code=status.HTTP_202_ACCEPTED)
    def refresh() -> dict[str, object]:
        if not app.state.refresh_lock.acquire(blocking=False):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Refresh job already running",
            )

        try:
            job_id = create_job(app.state.settings.db_path, job_type="refresh")
        except Exception:
            app.state.refresh_lock.release()
            raise

        thread = threading.Thread(target=_run_refresh_job, args=(job_id,), daemon=True)
        thread.start()
        return {"job_id": job_id, "status": "queued"}

    @app.get("/api/jobs/{job_id}")
    def job_status(job_id: str) -> dict[str, object]:
        job = get_job(app.state.settings.db_path, job_id=job_id)
        if job is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job not found: {job_id}",
            )
        return job

    return app


app = create_app()
