# Sprint 009 — Calibre import and re-sync

**Status:** completed
**Depends on:** 008
**Roadmap revision:** 4

## Objective

Deliver a confined, read-only Calibre preview and re-sync path that stages a stable normalized plan,
reuses the safe shared import commit boundary, and never overwrites library or source data.

## Required context

Read in order:

1. `AGENTS.md`
2. `docs/specs/product-spec.md` sections 2, 3, 5.2, 5.3, 6, and 7
3. `docs/specs/technical-spec.md` sections 5, 6.1, 6.4, 6.5, 7, 8, 9, and 10
4. `docs/decisions.md` DEC-002, DEC-007, DEC-008, DEC-009, DEC-010, and DEC-013
5. `docs/sprints/008-book-metadata-covers.md` Outcome and `docs/sprints/ROADMAP.md` Sprints 009–015
6. `docs/agent/WORKFLOW.md`, the last worklog entry, and `docs/agent/HANDOFF.md`
7. `backend/src/book_tracker/domain/goodreads.py`, `application/imports.py`, import API/repository,
   migrations/models, `frontend/src/api/imports.ts`, `frontend/src/pages/ImportPage.tsx`, and tests

## Current implementation baseline

Goodreads import now provides bounded staging, exact-plan persistence, explicit ambiguity choices,
atomic idempotent commit, ordered effects, OpenAPI contracts, and a keyboard/mobile import page.
Calibre configuration exists, but there is no path-confined adapter, read-only database reader,
Calibre normalization, cover staging, Calibre routes, or second UI tab. Sprint 011 still owns jobs,
enrichment, progress, and undo execution.

## Deliverables

- Add a Calibre adapter that resolves only configured-mount-relative paths, rejects traversal and
  symlink escape, opens `metadata.db` with `mode=ro` plus `PRAGMA query_only=ON`, and never changes it.
- Normalize supported Calibre book/author/identifier/tag/comment/series/rating schemas and stage all
  rows plus cover-copy evidence during preview so commit never rereads the source.
- Generalize the persisted import preview/commit service where needed without weakening Goodreads
  behavior, preserving exact identity, fill-empty, effect ordering, and retry idempotency.
- Add typed Calibre preview/commit contracts and a keyboard-accessible Calibre tab that clearly
  communicates path confinement, re-sync semantics, row errors, ambiguity choices, and results.

## Acceptance criteria (ordered, TDD)

1. Preview accepts supported synthetic Calibre schemas, preserves UUID provenance, joins authors,
   identifiers, tags, comments, series, ratings, and tolerates absent optional data.
2. Absolute paths, `..`, missing databases, symlink escapes, and non-database inputs fail safely
   without exposing host paths; every source connection proves `mode=ro` and `query_only=ON`.
3. Preview stages the exact normalized rows and prepared cover evidence, changes no library entity,
   and commit performs no Calibre database or source-cover read.
4. Calibre tags become shelves, status remains `unsorted` without a suggestion, and valid native
   1–10 ratings are not provisional; invalid personal fields remain visible row errors.
5. First import and re-sync are atomic/idempotent: new books/entries are created once, existing
   entries and populated shared metadata remain unchanged, and only empty shared fields are filled.
6. The Calibre UI tab is keyboard complete, announces validation/commit states, works at mobile and
   desktop widths, and does not imply enrichment, progress, or undo is available yet.

## Required tests (TDD)

- Synthetic temporary Calibre libraries covering full and minimal supported schemas, malformed
  optional rows, UUID/ISBN identity, tags, comments, series, direct ratings, and cover presence.
- Before/after SHA-256 proof that preview and commit never modify `metadata.db`; assertions for URI
  read-only mode and `PRAGMA query_only` on the actual adapter connection.
- File-backed migrated application database tests for preview isolation, staged-source stability,
  ambiguity/conflict handling, atomic rollback, re-sync idempotency, fill-empty, and manual values.
- ASGI/OpenAPI tests for safe path/domain errors and batch-ID-only commit.
- Component and Playwright flows for valid preview/commit, invalid/escaping path, ambiguity,
  re-sync retry, keyboard focus, mobile layout, and Goodreads regression.

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

Also run focused migration/adapter/preview/commit tests against real temporary SQLite files, verify
source DB hashes before and after, and run the specified Chromium flows.

## Explicit non-scope

- No durable job runner, provider enrichment, progress polling, undo execution, triage, auth, or
  Calibre write/sync-back behavior.
- No arbitrary host path, source reread during commit, live provider dependency, or cover reference
  that remains inside the Calibre mount.

## Commit checkpoints

1. `feat: add confined read-only Calibre adapter`
2. `feat: share durable Calibre import planning and commit`
3. `feat: add Calibre import and re-sync UI`
4. `test: verify read-only idempotent Calibre flows`
5. final `docs(sprint-009): close sprint and hand off`

## Risks and decisions to surface

- Calibre schema variants must be detected explicitly rather than guessed from a single fixture.
- Cover preparation must remain stable after preview without retaining unsafe source paths.
- Shared-pipeline refactors must preserve the already verified Goodreads request/response contract.
- Evidence must distinguish SQLite read-only/query-only enforcement from a hash-only observation.

## Outcome

Completed 2026-07-22.

- `0b7896b` added the mount-confined adapter, `mode=ro`/`query_only` enforcement, supported full and
  minimal schema normalization, durable exact-plan preview/commit, staged local covers, safe typed
  errors, UUID/ISBN matching, fill-empty re-sync, and Goodreads regression coverage.
- `73ee89d` added typed Calibre client calls and a keyboard/mobile import tab explaining relative
  paths, read-only access, cover staging, ratings, row errors, ambiguity, and re-sync semantics.
- `4c88c91` synchronized OpenAPI and quality contracts; `b3c89a4` ensured an ISBN-matched existing
  item also retains its non-conflicting Calibre UUID provenance.
- Synthetic file-backed tests prove absolute/traversal/missing/symlink/non-database rejection,
  unchanged source SHA-256, source-independent commit/retry, optional-schema tolerance, native
  nonprovisional score, shelves, cover installation, idempotency, and manual-value preservation.
- Verification passed: project validation; format/check; 91 backend and 16 component tests; Python
  wheel and production SPA build; nine normal Chromium flows (two live-provider flows gated/skipped),
  including the Calibre mobile keyboard flow; and `git diff --check`. The isolated build initially
  lacked DNS for Hatchling; the approved network rerun passed.
- No product or scope deviation. The implementation consolidated the first two planned backend
  checkpoints into one coherent commit. Sprint 010 now redesigns the real two-source import UI and
  implements the already-specified navigation/detail/delete/shelf completion work.
