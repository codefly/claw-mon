# OpenClaw Monitor - UI and Architecture Design

## 1. Purpose
Build a local web application that helps you understand OpenClaw usage cost and full conversation telemetry, with drill-down by:
- agent
- model
- day
- session/conversation
- inferred task/topic (enriched context)
- event type/role

Primary outcome: quickly identify what types of work are driving token burn and cost.

## 2. Inputs and Constraints
From `docs/requirements_context.md`:
- Source files: `~/.openclaw/agents/<agent_id>/sessions/<session_id>.jsonl`
- Cost computation fields come from assistant message usage records:
  - `type == "message"`
  - `message.role == "assistant"`
- For this monitor, ingest all JSONL events, then derive usage/cost facts from eligible assistant records
- Files are append-only and must be processed incrementally via file offsets

Additional assumptions:
- Single-user, local-first deployment
- Near-real-time updates (every few seconds is sufficient)
- Data volume can grow large across many sessions

## 3. Product Goals
1. Show where tokens and USD are spent over time.
2. Make drill-down fast and intuitive from aggregate -> source conversation.
3. Add context labels so high-cost work categories are obvious.
4. Preserve full-fidelity event history for broader analysis beyond cost.
5. Keep ingestion resilient to malformed lines and file rotations.

## 4. Non-Goals (MVP)
- Multi-user auth and team dashboards
- Cloud-hosted centralized data service
- Perfect semantic classification on day 1 (start with good-enough tags)

## 5. User Interface Design

## 5.1 Core UX Structure
Top-level nav:
1. Overview
2. Sessions
3. Events Explorer
4. Task Insights
5. Settings

Global filter bar (persistent across pages):
- Date range
- Agent (multi-select)
- Model (multi-select)
- Provider
- Event type / role
- Min cost / min tokens
- Search (session ID or topic label)

## 5.2 Overview Page
Purpose: answer "Where did my tokens/cost go?"

Components:
- KPI cards:
  - Total tokens
  - Total cost (USD)
  - Avg cost/day
  - Top model by spend
- Time-series chart (day):
  - tokens/day
  - cost/day
  - stacked by model or agent
- Breakdowns:
  - Cost by agent (bar)
  - Cost by model (bar)
  - Token mix (input/output/cache read/cache write)
- "Top burn sessions" table:
  - session ID, agent, model, tokens, cost, last active
  - click row -> Session detail

## 5.3 Sessions Page
Purpose: inspect conversation-level usage.

Layout:
- Left panel: sortable/filterable session list
- Right panel: selected session detail

Session detail includes:
- Header: agent, session ID, date span, total tokens, total USD
- Full event timeline (system/user/assistant/tool) with filters
- Per-message usage overlay for assistant turns
- Model/provider switches within session (if any)
- Enrichment chips: inferred task types/topics
- "High burn moments" list (largest token/cost assistant turns)

## 5.4 Events Explorer Page
Purpose: inspect all captured OpenClaw event data, not only usage records.

Components:
- Event table with virtualized rows
- Facets: type, role, agent, session, date range
- Raw JSON panel for selected event
- "Usage-bearing only" toggle for quick cost-focused mode
- Export current filtered result set (JSONL/CSV)

## 5.5 Task Insights Page
Purpose: answer "What work categories consume the most?"

Components:
- Treemap or bar chart: cost by inferred task category
- Trend chart: category cost over time
- Category table:
  - category
  - sessions count
  - total tokens
  - total cost
  - avg cost/session
- Drill-down drawer:
  - representative sessions and excerpts for selected category
  - links back to full event timeline in Events Explorer

## 5.6 Settings Page
- Data source root (default `~/.openclaw/agents`)
- Manual actions: Refresh data, Run enrichment, Reindex
- Enrichment settings:
  - provider/model
  - max enrichment budget per day
  - enable/disable enrichment
- Privacy controls:
  - redact snippets before enrichment
  - local-only mode (no external LLM calls)
- Retention controls for raw events vs derived aggregates

## 5.7 Interaction Design Notes
- Every chart element is clickable and applies filters.
- Breadcrumb drill-down (e.g. Overview > Agent A > Model B > Session X).
- Keep query state in URL params for shareable local links.
- Show job status/progress for manual Refresh and Enrich actions.

## 6. System Architecture

## 6.1 High-Level Components
1. Frontend Web App
   - React + TypeScript
   - Charting + data grid + filter state in URL
2. Backend API Service
   - Serves aggregated and detailed usage queries
   - Exposes on-demand endpoints for refresh and enrichment
3. Ingestion Module (in-process)
   - Recursive discovery of JSONL files
   - Incremental parser with per-file offsets
   - Full-event normalization + derived usage extraction
4. Enrichment Module (in-process)
   - Classifies sessions/segments into task categories/topics
   - Triggered via API endpoint, with progress tracking
5. Local Database
   - SQLite (primary) for normalized events + aggregates + offsets

## 6.2 Data Flow
1. User clicks Refresh (or calls `POST /api/refresh`).
2. File discovery scans `~/.openclaw/agents/**/sessions/*.jsonl`.
3. For each file, read from saved offset.
4. Parse all new JSONL lines and normalize/store raw events.
5. Derive usage/cost records from assistant message events with usage payload.
6. Update file offset checkpoint only after successful batch commit.
7. Aggregation queries power UI.
8. User clicks Enrich (or calls `POST /api/enrich`) to process new/changed sessions.
9. Enrichment results are stored and reflected in Task Insights.

## 6.3 Incremental Ingestion Design
Offset key should include:
- absolute file path
- inode (or file fingerprint)
- file size/mtime

Behavior:
- New file: start offset 0
- Existing file with larger size: read appended bytes
- Truncated/replaced file: detect inode/size mismatch, reset offset safely
- Malformed line: log error, skip line, continue

Batching:
- Read in chunks (e.g., 1-4 MB)
- Keep partial trailing line buffer between reads
- Transactional writes per batch for consistency/performance

## 6.4 Storage Schema (Proposed)
`agents`
- `id` (pk, text)
- `first_seen_at`, `last_seen_at`

`sessions`
- `id` (pk, text)
- `agent_id` (fk)
- `file_path`
- `started_at`, `ended_at`
- `last_ingested_at`

`raw_events`
- `event_id` (pk)
- `session_id` (fk, indexed)
- `agent_id` (indexed)
- `timestamp` (indexed)
- `event_type` (indexed)
- `role` (indexed, nullable)
- `raw_json` (json/text)
- `raw_line_hash` (unique, dedupe guard)

`usage_events`
- `event_id` (pk, fk -> raw_events.event_id)
- `session_id` (fk)
- `agent_id` (indexed)
- `timestamp` (indexed)
- `model`
- `provider`
- `input_tokens`
- `output_tokens`
- `cache_read_tokens`
- `cache_write_tokens`
- `total_tokens`
- `usd_cost`
- Derived only when `event_type=message` and `role=assistant` with usage payload

`file_offsets`
- `file_path` (pk)
- `inode`
- `offset_bytes`
- `last_size`
- `last_mtime`
- `updated_at`

`session_enrichment`
- `session_id` (pk/fk)
- `primary_category`
- `secondary_categories` (json)
- `summary`
- `confidence`
- `model_used`
- `updated_at`

`event_tags` (optional, phase 2)
- `event_id` (fk)
- `tag`
- `score`

## 6.5 API Surface (Example)
- `GET /api/overview?from=&to=&agent=&model=`
- `GET /api/trends?bucket=day&metric=cost|tokens`
- `GET /api/breakdown?by=agent|model|provider|category`
- `GET /api/sessions?filters...&page=`
- `GET /api/sessions/:id`
- `GET /api/events?type=&role=&agent=&session=&from=&to=&page=`
- `POST /api/refresh`
- `POST /api/enrich`
- `GET /api/jobs/:id`
- `POST /api/reindex`
- `GET /api/health`

## 7. Enrichment Strategy

## 7.1 Why Enrichment
Raw token metrics answer "how much," but not "for what." Enrichment adds categories like:
- coding
- debugging
- planning/design
- research
- documentation
- operations/devops

## 7.2 Pipeline
1. Build session text payload from selected turns (or sampled windows).
2. Apply privacy scrubber (optional): redact secrets/paths/emails.
3. Send to configured LLM classifier with strict JSON schema output.
4. Store category labels + confidence + short summary.
5. Re-run only when new session data significantly changes context.

## 7.3 Guardrails
- Budget cap: stop enrichment after daily spend threshold.
- Backoff and retry for provider failures.
- Deterministic cache key on session content hash.
- Allow fully local/offline mode (no enrichment requests).

## 8. Technology Recommendations

MVP stack:
- Frontend: React + TypeScript + Vite
- Backend/API: FastAPI (Python)
- DB: SQLite (WAL mode)
- Job orchestration: in-process background jobs triggered by API endpoints

Rationale:
- Python is strong for ingestion/parsing/enrichment logic and data-centric iteration speed.
- Fast local setup with low operational complexity.
- SQLite is strong for incremental writes, offsets, and app-style local persistence.
- Easy packaging into one local app later

DuckDB note:
- DuckDB is excellent for heavy OLAP and large analytical scans.
- For MVP, SQLite is preferred because ingestion is write-heavy/incremental.
- Re-evaluate DuckDB later if analytical query complexity or data volume outgrows SQLite performance.

## 9. Performance and Reliability
- Indexes:
- `raw_events(timestamp)`
- `raw_events(session_id, timestamp)`
- `raw_events(event_type, role, timestamp)`
- `usage_events(timestamp)`
- `usage_events(agent_id, timestamp)`
- `usage_events(model, timestamp)`
- `usage_events(session_id)`
- Pre-aggregated daily table/materialized view if query latency rises.
- Keep ingestion idempotent via `raw_line_hash` or unique event key.
- Emit ingest metrics: files scanned, lines parsed, lines skipped, lag seconds.

## 10. Security and Privacy
- Default bind backend to `localhost` only.
- Encrypt secrets (API keys) at rest or use OS keychain.
- Log only metadata by default, not full prompt content.
- Document exactly what data is sent to enrichment provider.

## 11. MVP Delivery Plan

Phase 1: Usage Core
1. File discovery + incremental parser
2. SQLite schema + full-event ingestion + derived usage extraction
3. Overview page with core filters and charts
4. Sessions page with drill-down and mixed event timeline
5. Events Explorer page (basic table + filters)
6. Manual `POST /api/refresh` endpoint + frontend Refresh button
7. Manual `POST /api/enrich` endpoint + frontend Enrich button + job status endpoint

Phase 2: Insight Layer
1. Improved enrichment quality and category taxonomy
2. Task Insights page
3. Budget/privacy controls

Phase 3: Hardening
1. Reindex tools and corruption recovery
2. Performance optimizations/materialized aggregates
3. Packaging and startup UX improvements

## 12. Acceptance Criteria
- After running Refresh, all session JSONL lines are available in Events Explorer.
- After running Refresh, new assistant usage-bearing messages appear in cost dashboards.
- After running Enrich, Task Insights reflects updated categories for changed sessions.
- Aggregations by day/agent/model/session match raw source totals.
- Session drill-down shows per-message token/cost distribution.
- Task Insights shows enriched categories with traceable sessions.
- Reindex can rebuild state from raw JSONL files without manual cleanup.
