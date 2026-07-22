# Sprint 007 — Goodreads import

**Status:** completed
**Depends on:** 003, 006
**Roadmap revision:** 2

## Objective

Deliver a size-bounded, preview-first Goodreads CSV import that persists the exact normalized plan,
requires explicit ambiguity choices, commits idempotently without overwriting existing library data,
and exposes actionable keyboard-accessible UI feedback.

## Required context

Read in order:

1. `AGENTS.md`
2. `docs/specs/product-spec.md` sections 2, 3, 5.1, 5.3, 6, and 7
3. `docs/specs/technical-spec.md` sections 5, 6.1, 6.5, 7, 8, 9, and 10
4. `docs/decisions.md` DEC-002, DEC-006, DEC-007, DEC-008, DEC-009, DEC-010, DEC-013,
   and DEC-015
5. `docs/sprints/ROADMAP.md` Sprint 007 and downstream Sprints 009, 010, and 011
6. `docs/agent/WORKFLOW.md`
7. `backend/src/book_tracker/infrastructure/models.py`, migrations, repositories, library/add APIs,
   `frontend/openapi.json`, `frontend/src/api/`, `frontend/src/pages/`, and their focused tests

## Current implementation baseline

The relational item/entry/source/identifier model, cached add boundary, shelves, typed OpenAPI,
keyboard-aware application shell, add flow, and cached detail/edit UI are complete. There are no
import batch/record/effect tables, CSV parser, preview/commit services or routes, import page, or
Goodreads fixtures. Sprint 009 owns durable enrichment and undo; Sprint 010 owns bulk triage.

## Deliverables

- Add migrations and repositories for durable import batches, normalized records, validation
  evidence, preview decisions, and the planned ordered effects required later by safe undo.
- Add a streaming, size-limited Goodreads CSV adapter with canonical column validation, armored ISBN,
  UTF-8, status/shelf/date/score normalization, row provenance, and stable file fingerprinting.
- Add typed preview and commit application/API contracts that persist the exact plan, expose errors
  and ambiguities, and commit idempotently without rereading client payloads.
- Add the Goodreads import tab with upload, preview summary, row-level errors/ambiguities, explicit
  choices, and commit results using generated OpenAPI-aligned clients.

## Acceptance criteria (ordered, TDD)

1. Preview rejects oversized/malformed/missing-column files safely and handles Excel-armored or
   empty ISBNs, malformed dates, UTF-8 text, zero ratings, repeated rows, and Goodreads Book Id
   provenance through deterministic fixtures.
2. Preview creates only staging/audit rows, persists the normalized plan and source fingerprint, and
   exposes parse errors plus exact-identity conflicts and title/author ambiguities without creating
   or mutating items, entries, shelves, or identifiers.
3. Personal mappings are explicit: imported rows create `unsorted` entries, Goodreads status becomes
   `suggested_status`, nonzero ratings convert to provisional 1–10 scores, shelves remain filterable,
   and invalid personal fields stay visible as row errors.
4. Commit accepts a preview batch ID and recorded ambiguity choices, never a second upload or host
   path; it applies the persisted plan atomically, is idempotent on retry, and records ordered effects.
5. Existing items/entries and manual values are never overwritten; imports fill only empty shared
   metadata, attach no contradictory exact identity, and retain alternatives in import audit data.
6. The import UI is keyboard complete, announces validation/commit states, keeps focus predictable,
   works at mobile and desktop widths, and never implies enrichment or undo completed in this sprint.

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

Also run focused migration/parser/preview/commit tests against real temporary SQLite files and
Playwright flows for valid preview/commit, malformed and oversized input, ambiguity choice, retry
idempotency, existing-manual-value preservation, keyboard focus, and mobile layout.

## Explicit non-scope

- No Calibre import, provider enrichment worker, undo execution, bulk triage, plugin registry, or auth.
- No second upload at commit, automatic fuzzy merge, overwrite of existing personal data, or public
  provider dependency while rendering previewed local records.

## Commit checkpoints

1. `feat: add durable Goodreads import planning model`
2. `feat: add Goodreads preview and commit contracts`
3. `feat: add Goodreads import preview UI`
4. `test: verify safe idempotent Goodreads import flows`
5. final `docs(sprint-007): close sprint and hand off`

## Risks and decisions to surface

- Preview must remain exact even if the source file or library changes before commit.
- Contradictory identifiers require quarantine, not a preferred winner.
- Ordered effect evidence must be sufficient for Sprint 009 without implementing undo early.
- Repeated uploads and commit retries must not duplicate staging rows or library entities.

## Outcome

Delivered a 5 MiB-bounded streaming Goodreads adapter with UTF-8/BOM-safe CSV parsing, canonical
column and ISBN validation, Goodreads provenance, normalized dates/status suggestions/shelves, and
provisional 1–10 scores. Preview fingerprints and stages the normalized plan without library writes;
commit consumes only the batch ID and explicit ambiguity choices, revalidates identity inside one
`BEGIN IMMEDIATE` transaction, preserves existing personal/shared values, fills empty shared
metadata, deduplicates repeated rows, and records ordered effects. The responsive `/import` UI
announces preview/error/commit states, enforces explicit choices, and never claims enrichment or undo.

Commits: `9216f27` (migration/parser/preview/commit), `4110481` (typed UI and Chromium flows), and
`0682b79` (data-safety regression coverage).

Verification: 82 backend tests and 15 frontend component tests pass; focused tests use migrated
temporary file-backed SQLite databases and cover migration round trips, malformed/oversized input,
normalization, preview isolation, ambiguity, retry idempotency, ordered effects, fill-empty behavior,
and manual-value preservation. Eight Chromium flows pass, including valid import, malformed and
oversized recovery, ambiguity choice, keyboard focus, and mobile layout. `make format`, `make check`,
`make test`, `make build`, project validation, and `git diff --check` pass.

Deviations: no product or scope deviation. The complete import audit tables were already introduced
by Sprint 002's full-domain migration; this sprint added query/replay indexes rather than duplicating
those tables. Sprint 008 can reuse the persisted plan/commit boundary, while Sprint 009 retains job
enrichment and undo execution.
