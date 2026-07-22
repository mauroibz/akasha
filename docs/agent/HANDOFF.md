# Handoff — current reality

**Last completed:** Sprint 011 (durable-enrichment-undo), 2026-07-22.
**Next:** Sprint 012 (bulk-first triage) — status `ready`, but the sprint file
`docs/sprints/012-bulk-first-triage.md` does not yet exist. It must be expanded
from the roadmap entry before implementation can begin.

## What was built in Sprint 011

- **Job runner** (`backend/src/book_tracker/infrastructure/jobs.py`):
  `JobRepository` with enqueue/claim/complete/fail/cancel/reclaim_expired,
  `RateLimiter` with clock-injected gating, `JobRunner` cooperative poller.
- **Enrichment** (`backend/src/book_tracker/application/enrichment.py`):
  fills empty item fields from providers, records `import_effects` for undo
  coverage, skips undone batches (late-job guard).
- **Undo** (`backend/src/book_tracker/application/undo.py`): reverses effects
  in descending order, reverts fill_empty only when current value matches
  after-value, preserves edited/shared/pre-existing entities, 24-hour window.
- **API**: `GET /api/import/jobs/{id}`, `DELETE /api/import/batches/{id}`.
- **UI**: undo button with confirmation, result display with reverted/retained
  counts, back-to-library link.
- **Tests**: `backend/tests/test_jobs.py` (30 tests), e2e undo flow tests.

## State

- All commits are on `main`, pushed to `origin/main`.
- Worktree is clean.
- `docs/agent/state.json` has `active_sprint: "012"`, `active_sprint_status: "ready"`.
- `docs/sprints/012-bulk-first-triage.md` does not exist — create it first.
- New decisions: DEC-018 (job runner shares event loop), DEC-019 (undo
  field-matching semantics).

## Key files to read for Sprint 012

- `docs/sprints/ROADMAP.md` — Sprint 012 scope and acceptance criteria.
- `backend/src/book_tracker/infrastructure/jobs.py` — job queue infrastructure.
- `backend/src/book_tracker/infrastructure/repositories.py` — existing query patterns.
- `backend/src/book_tracker/api/library.py` — existing API endpoints to extend.
- `frontend/src/pages/HomePage.tsx` — current library view to replace with table.
- `frontend/src/api/imports.ts` — undo/progress API functions added in Sprint 011.
