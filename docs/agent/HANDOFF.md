# Agent handoff

**State:** Sprint 002 completed; Sprint 003 is ready and unclaimed.
**Active sprint:** [`003-entries-shelves-api.md`](../sprints/003-entries-shelves-api.md)
**Worktree expectation:** clean after the Sprint 002 closure commit.

## Current reality

- Alembic head `0002_domain_schema` contains the complete v1 tables, constraints, and indexes;
  downgrade to the foundation and re-upgrade are tested on real files.
- Framework-independent ISBN/text/shelf normalization, matching decisions, enums, and fill-empty
  behavior live under `backend/src/book_tracker/domain/`.
- All schema tables are mapped under `infrastructure/models.py`; `DomainRepository` uses short
  `BEGIN IMMEDIATE` writes for identity/entry creation, fill-empty union, and shelf lifecycle.
- Exact ISBN/provider identities and per-user entries deduplicate; split exact identities raise a
  typed conflict without mutation, and title/author similarities remain advisory.
- Only health HTTP routes exist; Sprint 003 owns application services, list/cursor queries, and API.

## First action

Follow `AGENTS.md`, claim Sprint 003, inspect the actual domain repositories/tests, and begin with
failing entry and shelf application-service tests.

## Known blockers

None. Docker and the required Python 3.12 managed runtime were available during Sprint 001.
