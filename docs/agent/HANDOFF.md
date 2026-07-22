# Agent handoff

**State:** Sprint 001 completed; Sprint 002 is ready and unclaimed.
**Active sprint:** [`002-domain-persistence.md`](../sprints/002-domain-persistence.md)
**Worktree expectation:** clean after the Sprint 001 closure commit.

## Current reality

- FastAPI construction has no filesystem side effects; lifespan startup creates data directories, applies Alembic, and configures the SQLite engine.
- Health, readiness failure modes, SQLite pragmas, and API-safe SPA fallback have backend acceptance tests.
- The React/Vite page has accessible loading, ready, and unavailable component tests.
- `make bootstrap`, `make check`, `make test`, `make build`, deterministic OpenAPI export, CI, Compose, and the persistent non-root/no-Node container smoke are operational.
- The only schema table is the Sprint 001 `schema_probe`; no book-domain rows or contracts were invented.

## First action

Follow `AGENTS.md`, claim Sprint 002, inspect the actual foundation migration/tests, and add the domain migration tests before implementing the complete schema.

## Known blockers

None. Docker and the required Python 3.12 managed runtime were available during Sprint 001.
