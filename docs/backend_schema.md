# Backend SQLite Schema (Story 2)

This schema is created by migration `backend/app/migrations/0001_initial.sql`.

## Tables

### `schema_migrations`
Tracks applied migration versions.
- `version` (TEXT, PK)
- `applied_at` (TEXT)

### `agents`
Known OpenClaw agent IDs.
- `id` (TEXT, PK)
- `first_seen_at` (TEXT)
- `last_seen_at` (TEXT)

### `sessions`
Session metadata per JSONL session file.
- `id` (TEXT, PK)
- `agent_id` (TEXT, FK -> `agents.id`)
- `file_path` (TEXT, UNIQUE)
- `started_at` (TEXT)
- `ended_at` (TEXT)
- `last_ingested_at` (TEXT)

### `raw_events`
All JSONL events captured from session files.
- `event_id` (TEXT, PK)
- `session_id` (TEXT, FK -> `sessions.id`)
- `agent_id` (TEXT, FK -> `agents.id`)
- `timestamp` (TEXT)
- `event_type` (TEXT)
- `role` (TEXT, nullable)
- `raw_json` (TEXT)
- `raw_line_hash` (TEXT, UNIQUE)

### `usage_events`
Derived usage rows for assistant message events with usage payload.
- `event_id` (TEXT, PK, FK -> `raw_events.event_id`)
- `session_id` (TEXT, FK -> `sessions.id`)
- `agent_id` (TEXT, FK -> `agents.id`)
- `timestamp` (TEXT)
- `model` (TEXT)
- `provider` (TEXT)
- `input_tokens` (INTEGER, >=0)
- `output_tokens` (INTEGER, >=0)
- `cache_read_tokens` (INTEGER, >=0)
- `cache_write_tokens` (INTEGER, >=0)
- `total_tokens` (INTEGER, >=0)
- `usd_cost` (REAL, >=0)

### `file_offsets`
Incremental ingest checkpoints.
- `file_path` (TEXT, PK)
- `inode` (TEXT)
- `offset_bytes` (INTEGER, >=0)
- `last_size` (INTEGER, >=0)
- `last_mtime` (REAL)
- `updated_at` (TEXT)

### `session_enrichment`
Session-level enrichment output.
- `session_id` (TEXT, PK, FK -> `sessions.id`)
- `primary_category` (TEXT)
- `secondary_categories` (TEXT)
- `summary` (TEXT)
- `confidence` (REAL, 0..1)
- `model_used` (TEXT)
- `content_hash` (TEXT)
- `estimated_cost_usd` (REAL)
- `updated_at` (TEXT)

### `jobs`
Job tracking for refresh/enrich/reindex operations.
- `id` (TEXT, PK)
- `job_type` (TEXT)
- `status` (TEXT, queued|running|completed|failed)
- `requested_at` (TEXT)
- `started_at` (TEXT)
- `finished_at` (TEXT)
- `progress_json` (TEXT)
- `error` (TEXT)

## Indexes
Created in baseline migration:
- `idx_sessions_agent_id`
- `idx_raw_events_timestamp`
- `idx_raw_events_session_timestamp`
- `idx_raw_events_type_role_timestamp`
- `idx_usage_events_timestamp`
- `idx_usage_events_agent_timestamp`
- `idx_usage_events_model_timestamp`
- `idx_usage_events_session_id`
- `idx_jobs_status_requested_at`
- `idx_session_enrichment_content_hash`

## Notes
- SQLite foreign keys are enforced via `PRAGMA foreign_keys = ON` in app connections.
- Migration runs are idempotent through `schema_migrations` version tracking.
