# Akasha Book Tracker

A self-hosted, keyboard-first personal book rating and triage application. It is an opinion tracker, not an ebook server or social network.

## Repository status

The repository is prepared for sprint-by-sprint autonomous implementation. Application code has not started yet. Sprint 001 is the active unit of work.

## For coding agents

Start with [`AGENTS.md`](AGENTS.md). If your instruction is only `work`, follow that file exactly. Do not choose a different sprint or implement future scope.

## Canonical documents

1. [`docs/specs/product-spec.md`](docs/specs/product-spec.md) — user-visible behavior and scope
2. [`docs/specs/technical-spec.md`](docs/specs/technical-spec.md) — architecture, contracts, data model, quality constraints
3. [`docs/sprints/ROADMAP.md`](docs/sprints/ROADMAP.md) — ordered delivery plan
4. [`docs/agent/WORKFLOW.md`](docs/agent/WORKFLOW.md) — execution and handoff protocol
5. [`docs/agent/state.json`](docs/agent/state.json) — machine-readable active sprint pointer
6. [`docs/agent/worklog.md`](docs/agent/worklog.md) — append-only per-session work log
7. [`docs/decisions.md`](docs/decisions.md) — decisions and implementation deviations

The precedence and conflict rules are defined in `AGENTS.md`.

## Intended development commands

These commands become operational in Sprint 001:

```bash
make bootstrap
make check
make test
make dev
```

Until Sprint 001 creates the application scaffold, validate the planning repository with:

```bash
python scripts/validate_project.py
```

## Target stack

- Python 3.12, FastAPI, SQLAlchemy 2, Alembic, SQLite
- React 18, Vite, TypeScript, Tailwind, shadcn/ui, Motion
- pytest for backend tests; Vitest + Testing Library for frontend tests; Playwright for critical flows
- One multi-stage Docker image; `/data` is writable and `/calibre` is read-only

## Product safety boundary

v1 has no authentication. It is LAN-only and must not be exposed to the public internet. Reverse-proxy configuration must preserve that boundary.
