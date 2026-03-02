# Repository Guidelines

## Project Structure & Module Organization
This repository is currently documentation-first.
- `docs/requirements_context.md`: source context and data format assumptions.
- `docs/openclaw_monitor_design.md`: architecture and UI design decisions.
- `docs/openclaw_monitor_stories.md`: implementation stories and Definition of Done.
- `README.md`: minimal project entrypoint.

As implementation starts, follow the planned layout from the stories doc:
- `backend/` for FastAPI, ingestion, DB schema/migrations, and API tests.
- `frontend/` for React UI and page-level integration tests.
- `fixtures/` (or `tests/fixtures/`) for sample OpenClaw JSONL session data.

Keep README updated as you implement new features.

## Build, Test, and Development Commands
No build pipeline is committed yet. Until code is added, use:
- `git status` to verify local changes.
- `rg "pattern" docs/` to quickly search design decisions.
- `sed -n '1,120p' docs/openclaw_monitor_design.md` to inspect key sections.

When backend/frontend are added, document canonical run/test commands in each subproject README and keep them current.

## Coding Style & Naming Conventions
- Use clear, small modules with single responsibilities.
- Python (backend): 4-space indentation, type hints on public functions, `snake_case` for functions/files, `PascalCase` for classes.
- TypeScript (frontend): `camelCase` variables/functions, `PascalCase` React components.
- Prefer explicit names like `refresh_job_service.py` over generic names like `utils.py`.
- Keep docs and API names aligned with terms in `docs/openclaw_monitor_design.md`.

## Testing Guidelines
- Place tests near implementation (`backend/tests/`, `frontend/src/**/__tests__/`).
- Name tests by behavior (example: `test_refresh_inserts_new_usage_events`).
- Cover ingestion edge cases: append, truncate/rotate, malformed JSONL lines.
- Do not mark a story complete unless all DoD checks in `docs/openclaw_monitor_stories.md` pass locally.

## Commit & Pull Request Guidelines
- Follow concise, imperative commit messages (examples from history: `initial commit`, `Add ... docs`).
- Keep commits focused; avoid mixing refactors with feature behavior changes.
- Create feature branches for each feature you work on, and create a PR to master when you are completed
- PRs should include:
  - summary of scope and impacted paths,
  - linked story ID(s),
  - test evidence (commands + results),
  - screenshots for UI changes.

## Security & Configuration Tips
- Never commit API keys or local paths from `~/.openclaw`.
- Bind local services to `localhost` by default.
- Prefer sample/anonymized fixtures in tests and docs.
