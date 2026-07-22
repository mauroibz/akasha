# Agent handoff

**State:** Sprint 003 completed; Sprint 004 is ready and unclaimed.
**Active sprint:** [`004-frontend-library.md`](../sprints/004-frontend-library.md)
**Worktree expectation:** clean after the Sprint 003 closure commit.

## Current reality

- Alembic head is `0003_list_indexes`; real-file downgrade/upgrade and common query-plan index use
  are tested.
- `/api/entries`, `/api/items`, and `/api/shelves` expose typed CRUD, exact counts/facets, all six
  stable keyset sorts, atomic bulk mutations, and suggested-status acceptance.
- Static bulk routes precede integer detail routes; domain failures use stable error envelopes and
  validation remains FastAPI 422.
- Unicode search, text order, and cursor values share the deterministic per-connection SQLite
  `normalize_text` function recorded in DEC-015.
- `frontend/openapi.json` is the checked generated contract and is excluded from Prettier so
  `make format` and `make openapi-check` remain deterministic.
- The frontend is still the health-only Sprint 001 page; Sprint 004 owns the library UI.

## First action

Follow `AGENTS.md`, claim Sprint 004, inspect the generated OpenAPI and current frontend tests, and
begin with failing library loading/empty/error/populated component tests.

## Known blockers

None. Docker and the required Python 3.12 managed runtime were available during Sprint 001.
