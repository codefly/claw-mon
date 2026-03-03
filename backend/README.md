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

## Configuration
Environment variables are auto-loaded from `backend/.env` on startup:
- `CLAWMON_DATA_ROOT` (default: `~/.openclaw/agents`)
- `CLAWMON_DB_PATH` (default: `./data/clawmon.db`)
- `CLAWMON_ENRICHMENT_ENABLED` (default: `false`)
