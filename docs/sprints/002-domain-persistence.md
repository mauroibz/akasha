# Sprint 002 — Domain model and durable persistence

**Status:** completed
**Depends on:** 001
**Roadmap revision:** 2

## Objective

Implement the complete v1 relational domain schema, normalization and identity rules, and SQLAlchemy repositories so database constraints and transaction behavior preserve edition identity and personal data.

## Required context

Read in order:

1. `AGENTS.md`
2. `docs/specs/product-spec.md` sections 2 and 3
3. `docs/specs/technical-spec.md` sections 2–6 and 10
4. `docs/decisions.md` DEC-003, DEC-008, DEC-009, DEC-010, DEC-011, and DEC-013
5. `docs/sprints/ROADMAP.md` Sprint 002 and downstream Sprints 003, 005, 007–009
6. `docs/agent/WORKFLOW.md`
7. `backend/alembic/versions/0001_foundation.py`, `backend/src/book_tracker/database.py`, `backend/src/book_tracker/migrations.py`, and `backend/tests/test_foundation.py`

## Current implementation baseline

Sprint 001 provides a locked Python 3.12 package, Alembic foundation migration containing only `schema_probe`, a file-backed SQLite engine with foreign keys/WAL/busy timeout, lifespan migration, and pytest/Ruff/mypy gates. There are no domain models or repositories.

## Deliverables

- Add a migration after `0001_foundation` for items, authoritative identifiers, provider sources, entries, shelves/joins, import batches/records/effects, and jobs with the canonical constraints and indexes.
- Add framework-independent status, score, identifier, source, normalization, match decision, and fill-empty domain behavior under `backend/src/book_tracker/domain/`.
- Add SQLAlchemy mappings and repositories under `backend/src/book_tracker/infrastructure/` with explicit short transaction boundaries.
- Add migrated file-backed fixtures and migration round-trip, constraint, repository dedupe/conflict, ambiguity, fill-empty, and shelf tests.

## Acceptance criteria (ordered, TDD)

1. Alembic upgrades an empty database through the complete schema and safely downgrades/upgrades from the Sprint 001 head.
2. Database constraints reject invalid status, score, reread, boolean, source-primary, and shelf relationships while foreign keys remain enabled on every connection.
3. Valid ISBN-10 and equivalent ISBN-13 normalize to one authoritative identity; duplicate identifiers and provider sources cannot race into separate items.
4. Exact item and entry identities deduplicate; contradictory exact identities return a typed `identity_conflict` without mutation.
5. Normalized title/first-author matches are ambiguity suggestions only and never auto-merge editions.
6. Fill-empty updates preserve every existing non-empty metadata or personal value; relational identifier unions occur only when exact identities agree.
7. Shelf create/attach/rename/delete behavior enforces per-user normalized slugs and cascades only join rows.

## Verification

Run and record:

```bash
python scripts/validate_project.py
make format
make check
make test
make build
git diff --check
```

Also migrate real temporary SQLite files empty-to-head and `0001_foundation`-to-head, exercise downgrade/upgrade, and run focused repository concurrency tests.

## Explicit non-scope

- No entry, shelf, search, bulk, or pagination HTTP routes.
- No metadata providers, cover handling, imports, job runner, or frontend domain UI.
- No auth, plugin runtime, or changes to permanent `book_tracker`/`items`/`entries` internal names.

## Commit checkpoints

1. `feat: add complete domain migration and invariants`
2. `feat: add identity normalization and matching decisions`
3. `feat: add transactional domain repositories`
4. final `docs(sprint-002): close sprint and hand off`

## Risks and decisions to surface

- Use relational uniqueness, not JSON queries or check-then-insert, for authoritative identity.
- Keep title/author matches advisory because rows represent editions.
- Never weaken import/personal-value precedence while creating shared repository helpers.
- Keep migration/schema work aligned with the future import ledger and durable jobs without implementing their workflows.

## Outcome

Delivered the complete v1 relational schema and its SQLAlchemy mappings, framework-independent
normalization/matching/fill-empty contracts, and short `BEGIN IMMEDIATE` repository transactions.
The repositories deduplicate authoritative item and per-user entry identities, reject split exact
identity without mutation, keep title/author matches advisory, and implement shelf lifecycle rules.

- `d45f365` adds the domain migration, canonical constraints/indexes, and real file-backed migration
  round-trip/negative tests.
- `19ea28d` adds ISBN-10/13 canonicalization, Unicode text and shelf normalization, typed match
  decisions/status/source contracts, and fill-empty behavior.
- `ca21ca6` adds mappings and repositories with concurrency, conflict, ambiguity, fill-empty,
  identifier-union, and shelf tests.
- Verification: `python scripts/validate_project.py`, `make format`, `make check`, `make test`
  (25 backend and 2 frontend tests), `make build`, and `git diff --check` passed. The focused
  two-thread equivalent-ISBN test passed against a migrated file-backed SQLite database; migration
  tests exercised empty-to-head, `0001_foundation`-to-head, downgrade, and re-upgrade.
- Deviations: none. All downstream sprints were reviewed; Sprint 003 was expanded using the actual
  repository and migration paths, and no later acceptance contract required adjustment.
