# Backend (Story 1)

FastAPI backend skeleton for OpenClaw Monitor.

## Prerequisites
- Python 3.11+

## Setup
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## Run Locally
```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Health endpoint:
- `GET http://127.0.0.1:8000/api/health`

## Test
```bash
cd backend
source .venv/bin/activate
pytest -q
```

## Run Migrations
```bash
cd backend
source .venv/bin/activate
python -m app.migrate
```

## Run Ingestion (Library)
```bash
cd backend
source .venv/bin/activate
python - <<'PY'
from pathlib import Path
from app.ingestion import ingest_data_root

stats = ingest_data_root(
    db_path=Path("./data/clawmon.db"),
    data_root=Path.home() / ".openclaw" / "agents",
)
print(stats)
PY
```

## Refresh API (Manual Trigger)
Start local server:

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Trigger refresh:

```bash
curl -X POST http://127.0.0.1:8000/api/refresh
```

Check job status:

```bash
curl http://127.0.0.1:8000/api/jobs/<job_id>
```

## Configuration
Environment variables are auto-loaded from `backend/.env` on startup.
Start by copying the template:

```bash
cp .env.example .env
```

Available variables:
- `CLAWMON_DATA_ROOT` (default: `~/.openclaw/agents`)
- `CLAWMON_DB_PATH` (default: `./data/clawmon.db`)
- `CLAWMON_ENRICHMENT_ENABLED` (default: `false`)
