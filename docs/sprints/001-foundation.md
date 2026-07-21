# Sprint 001 — Reproducible foundation

**Status:** ready
**Depends on:** none
**Roadmap revision:** 1

## Objective

Create a reproducible FastAPI + React monorepo skeleton with migrations, quality gates, a minimal backend-to-frontend vertical slice, local development commands, and CI. This sprint proves the architecture and toolchain; it does not implement book-domain behavior.

## Required context

Read in order:

1. `AGENTS.md`
2. `docs/specs/product-spec.md` sections 1, 2, 7, and 8
3. `docs/specs/technical-spec.md` sections 1–4, 10, and 11
4. `docs/sprints/ROADMAP.md`
5. `docs/agent/WORKFLOW.md`
6. `docs/decisions.md`

## Deliverables

### 1. Backend package

Create `backend/pyproject.toml`, `backend/src/book_tracker/`, and `backend/tests/`.

- Package targets Python 3.12.
- `create_app(settings=None)` application factory; no import-time filesystem or DB side effects.
- Typed settings and structured logging baseline.
- `/api/health/live` and `/api/health/ready` endpoints.
- SQLAlchemy engine factory applies foreign keys, WAL, and busy timeout.
- Alembic is configured with an initial foundation migration. It may create only a `schema_probe` or equivalent minimal table; Sprint 002 owns the complete domain schema.
- Readiness verifies DB query success and current Alembic head.
- pytest, Ruff, mypy, and coverage configuration.

### 2. Frontend package

Create `frontend/package.json` with an npm lockfile and strict TypeScript Vite application.

- React 18, React Router, TanStack Query, Tailwind, shadcn-compatible aliases, and Motion dependencies/config are installed.
- The initial page displays product name and live readiness state from the backend.
- Accessible loading, ready, and unavailable states are component-tested.
- Vitest, Testing Library, ESLint, and Prettier checks are configured.
- Do not build the final design system or library page.

### 3. Developer workflow and contract

- Root `Makefile`: `bootstrap`, `dev`, `format`, `lint`, `typecheck`, `test`, `check`, `migrate`, and `build` targets.
- `.env.example` documents all technical-spec environment variables with safe local defaults.
- OpenAPI export command produces a deterministic `frontend/openapi.json` or generated typed client artifact; CI detects drift.
- `scripts/seed_dev.py` may exist only as an empty/foundation-safe seed command; do not invent domain rows before Sprint 002.
- `README.md` setup instructions become executable rather than aspirational.

### 4. CI and container build proof

- GitHub Actions runs project-state validation, backend lint/type/tests, frontend lint/type/tests, and production builds with dependency caches.
- Add an initial multi-stage `Dockerfile` and `compose.yaml` sufficient to build and serve the hello SPA through FastAPI.
- Final stage runs as non-root, contains no Node executable, and exposes a healthcheck.
- Compose visibly warns that v1 is LAN-only and mounts `/data`; Calibre mount may be documented/disabled until Sprint 008.

## Required tests (TDD)

1. App factory construction has no filesystem side effects before startup.
2. Live health succeeds without consulting DB/providers.
3. Ready health succeeds on migrated DB and fails usefully on unavailable/unmigrated DB.
4. Every SQLAlchemy connection has foreign keys enabled; configured WAL/busy timeout are observed.
5. Frontend renders loading, ready, and unavailable health states with accessible text.
6. SPA fallback serves a frontend route while `/api/missing` remains a JSON 404, not `index.html`.
7. Production container starts, passes readiness, serves the SPA, persists a probe across recreation, runs non-root, and does not contain `node`.

## Verification

Run and record actual outputs:

```bash
python scripts/validate_project.py
make bootstrap
make format
make check
make test
make build
docker compose config
# Run the scripted container smoke test introduced by this sprint.
```

Also inspect `git diff --check`. If Docker is unavailable, this sprint is blocked unless the user explicitly accepts deferred container verification.

## Explicit non-scope

- No item/entry/shelf domain schema.
- No book CRUD routes or UI.
- No provider calls, imports, job queue, or real cover handling.
- No auth, plugin runtime, multiuser behavior, or deployment to a host.

## Commit checkpoints

Suggested coherent commits (adapt to actual work, do not commit red tests):

1. `build: scaffold backend and migration tooling`
2. `build: scaffold frontend and health view`
3. `build: add unified quality gates and API contract`
4. `build: add CI and production image smoke test`
5. final `docs(sprint-001): close sprint and hand off`

## Risks and decisions to surface

- Select a dependency-locking approach that is reproducible in CI and Docker; record it.
- Keep the DB API sync unless evidence justifies async SQLAlchemy.
- Ensure static SPA catch-all is mounted after API routes.
- Do not let readiness call public providers.
- If tooling choices differ from the technical spec, explain why and assess downstream impact.

## Outcome

_Not started. The implementing agent replaces this section with delivered behavior, tests/commands and results, commit IDs, deviations, and downstream changes before marking the sprint complete._
