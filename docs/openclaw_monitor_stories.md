# OpenClaw Monitor - Implementation Stories

## 1. Purpose
This document breaks the design into implementation-ready stories for a coding agent.
Stories are intentionally medium-sized (not too granular), and each includes a concrete Definition of Done (DoD).

## 2. Execution Rules
- Build order follows story IDs unless dependencies require minor reordering.
- Each story must be merged with tests and updated docs.
- A story is only done when all DoD items pass locally.

## 3. Stories

## Story 1: Backend Project Skeleton and Local Runtime
**Status**: Complete (merged)

**Goal**
Set up a FastAPI backend with configuration, logging, and local run commands. 

**Definition of Done**
- python venv created and requirements.txt available
- Backend project exists under `backend/` with FastAPI app entrypoint.
- Config supports at least: data root path, DB path, enrichment enabled flag.
- `GET /api/health` returns service status and DB connectivity status.
- Local run command is documented in `backend/README.md`.
- Basic test framework is configured and one health endpoint test passes.

## Story 2: SQLite Schema and Migration Baseline
**Status**: Complete (merged)

**Goal**
Create SQLite schema for raw events, usage events, offsets, sessions, agents, enrichment, and jobs.

**Definition of Done**
- Migration creates tables from design doc: `agents`, `sessions`, `raw_events`, `usage_events`, `file_offsets`, `session_enrichment`, `jobs`.
- Required indexes are present for `raw_events` and `usage_events` time/filter queries.
- Foreign keys and uniqueness constraints are enforced.
- Migration is idempotent (safe rerun behavior defined and tested).
- Schema is documented in `docs/` with table/column notes.

## Story 3: Incremental Ingestion Engine (Library Layer)
**Status**: Complete (merged)

**Goal**
Implement reusable ingestion logic that scans OpenClaw session files and persists all events + derived usage rows.

**Definition of Done**
- Ingestion recursively scans `~/.openclaw/agents/**/sessions/*.jsonl` (configurable root).
- Parser stores all JSONL lines as `raw_events` (with dedupe guard).
- Parser derives `usage_events` only for assistant message events with usage payload.
- File offset tracking handles append, truncate, and replacement safely.
- Malformed lines are skipped and counted, without stopping entire run.
- Unit tests cover append/truncate/malformed-line behavior.

## Story 4: Refresh API and Job Tracking
**Status**: Complete (merged)

**Goal**
Expose manual refresh flow through API and persist job state/progress.

**Definition of Done**
- `POST /api/refresh` starts a refresh job and returns `job_id`.
- `GET /api/jobs/{job_id}` returns status (`queued|running|completed|failed`) and counters.
- Refresh job writes: files scanned, lines read, lines skipped, raw events inserted, usage events inserted.
- Concurrent refresh requests are serialized or rejected with clear error.
- Integration test verifies data appears after refresh on fixture files.

## Story 5: Query APIs for Overview and Breakdowns
**Status**: Complete (merged)

**Goal**
Provide backend endpoints for dashboard metrics and charts.

**Definition of Done**
- Endpoints implemented:
  - `GET /api/overview`
  - `GET /api/trends`
  - `GET /api/breakdown`
- Filters supported: date range, agent, model, provider.
- Metrics use `usage_events` as source of truth for cost/tokens.
- Responses are stable JSON contracts with pagination where applicable.
- API tests validate totals against fixture-derived expected values.

## Story 6: Query APIs for Sessions and Events Explorer
**Status**: Complete (merged)

**Goal**
Provide backend endpoints for session drill-down and full raw event exploration.

**Definition of Done**
- Endpoints implemented:
  - `GET /api/sessions`
  - `GET /api/sessions/{id}`
  - `GET /api/events`
- `GET /api/events` supports filters: type, role, agent, session, date range, usage-bearing only.
- Session detail returns mixed event timeline plus usage summary.
- Large results are paginated with deterministic sort order.
- API tests verify filters, pagination, and contract shape.

## Story 7: Enrichment Engine and Enrich API
**Status**: Complete (merged)

**Goal**
Implement manual enrichment pipeline and API-triggered job execution.

**Definition of Done**
- `POST /api/enrich` starts enrichment job for new/changed sessions and returns `job_id`.
- Enrichment writes `session_enrichment` with category, summary, confidence, model metadata.
- Content-hash cache avoids re-enriching unchanged sessions.
- Enrichment budget cap is enforced per run/day setting.
- Failures are isolated per session and reported in job counters.
- Tests cover unchanged-session skip behavior and write/update behavior.

## Story 8: Provider LLM Enrichment Integration
**Status**: Complete (implemented)

**Goal**
Integrate a real LLM provider for enrichment while keeping the existing local heuristic classifier as fallback.

**Definition of Done**
- Enrichment service supports provider-backed classification mode (configurable provider/model).
- API key/config handling is implemented without committing secrets.
- Prompt + response contract is structured (JSON schema or strict parser) and validated.
- LLM output is normalized into existing `session_enrichment` fields.
- If provider call fails, enrichment falls back to local classifier and records fallback reason.
- Budget accounting includes provider-estimated/actual spend and is reflected in job progress.
- Tests cover success path, provider failure fallback, and malformed response handling.

## Story 9: Frontend App Shell and Shared Filter State
**Status**: Complete (merged)

**Goal**
Build React app shell with routes, top nav, and global filter model.

**Definition of Done**
- Frontend exists under `frontend/` with build/run scripts.
- Routes implemented: `Overview`, `Sessions`, `Events Explorer`, `Task Insights`, `Settings`.
- Global filter state is URL-backed and reusable across pages.
- API client layer handles loading/error states consistently.
- Minimal responsive layout works on desktop and mobile widths.

## Story 10: Overview UI
**Goal**
Implement overview dashboards for token/cost analytics.

**Definition of Done**
- KPI cards render totals from `GET /api/overview`.
- Trends and breakdown charts render from API endpoints.
- Chart interactions apply/update global filters.
- Top burn sessions table links to Session detail route.
- Page handles empty states and no-data date ranges.

## Story 11: Sessions UI and Events Explorer UI
**Goal**
Implement session drill-down and full event inspection experiences.

**Definition of Done**
- Sessions page shows list + detail pane with mixed timeline.
- Usage overlay and high-burn moments are visible in session detail.
- Events Explorer table supports filter facets and pagination.
- Selected event displays raw JSON payload.
- Usage-bearing only toggle works end-to-end with API.

## Story 12: Task Insights UI
**Goal**
Expose enrichment results in category-based analytics views.

**Definition of Done**
- Task Insights page renders category breakdown and trends.
- Category table shows sessions count, tokens, cost, avg cost/session.
- Drill-down exposes representative sessions and links to events/sessions pages.
- Page gracefully handles enrichment-not-run and partial-enrichment states.

## Story 13: Settings UI and Manual Operations
**Goal**
Provide operational controls for refresh/enrich/reindex and core settings.

**Definition of Done**
- Settings page includes editable values for data root, enrichment config, budget cap.
- Buttons trigger `Refresh`, `Enrich`, and `Reindex` operations.
- UI polls `GET /api/jobs/{id}` and shows progress/status/errors.
- Operation outcomes are visible with timestamps and summary counts.
- Settings persistence is documented and tested.

## Story 14: Reindex Flow and Recovery Hardening
**Goal**
Enable full rebuild from source files and improve resilience for edge cases.

**Definition of Done**
- `POST /api/reindex` performs clear-and-rebuild workflow safely.
- Reindex preserves app operability and reports progress via jobs API.
- Recovery behavior documented for corrupted offsets and malformed files.
- End-to-end test validates rebuild equals fresh ingest totals.

## Story 15: End-to-End Quality Gate and Release Docs
**Goal**
Finalize MVP quality bar and onboarding docs.

**Definition of Done**
- Test suite includes backend API tests and frontend smoke tests.
- A seeded fixture dataset is included for repeatable local validation.
- `README.md` describes startup steps for backend + frontend and MVP workflow.
- A release checklist exists covering: refresh, enrich, overview totals, sessions drill-down, events explorer, task insights.
- Known limitations and next-phase items are documented.
