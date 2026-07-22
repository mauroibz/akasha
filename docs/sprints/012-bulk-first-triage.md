# Sprint 012 — Bulk-first triage

**Status:** in_progress
**Depends on:** 011
**Roadmap revision:** 4

## Objective

Replace the current library view with a virtualized dense table that supports filters, grouping,
selection (including server-side select-all with exclusions), and bulk status/shelf/score
assignment, so that hundreds of imported entries can be triaged efficiently in one pass.

## Required context

1. `AGENTS.md`
2. `docs/specs/product-spec.md` section 5 (enrichment and triage)
3. `docs/specs/technical-spec.md` section 9 (import effects) and section 11 (undo)
4. `docs/decisions.md` DEC-002 (import ledger), DEC-018 (job runner), DEC-019 (undo semantics)
5. Sprint 011 Outcome and `docs/agent/WORKFLOW.md`
6. Existing `backend/src/book_tracker/api/library.py`, `frontend/src/pages/HomePage.tsx`,
   `frontend/src/api/imports.ts` (undo/progress API from Sprint 011)

## Current implementation baseline

After Sprint 011, the application has a durable job runner, enrichment pipeline, and safe undo.
The library view (`HomePage.tsx`) renders entries as cards without bulk operations. The API
supports individual entry updates but no batch endpoints. Import effects are recorded for undo.

## Deliverables

- Virtualized dense table replacing card-based library view.
- Filters (status, shelf, score, source) and grouping by shelf or status.
- Selection model: single, range, select-all (server-side with exclusions).
- Bulk action bar: set status, set shelf, set score, advance/commit.
- Keyboard shortcuts: `j/k` navigation, status/score/shelf hotkeys, commit/advance.
- Playwright scenario importing and triaging hundreds of rows without per-row requests.

## Acceptance criteria

1. Server-side select-all means all rows matching the current filter and uses exclusions;
   unloaded or hidden rows are mutated only when that contract explicitly includes them.
2. `j/k`, status, score, shelf, commit/advance shortcuts work with input guards.
3. A Playwright scenario imports and triages hundreds of rows without one request per row.
4. Conflicting values remain visible until explicitly resolved.

## Required tests (TDD)

- Backend: batch update endpoint, select-all with exclusions, conflict visibility.
- Frontend: virtualized table rendering, selection model, bulk action bar, keyboard shortcuts.
- E2e: import-and-triage scenario with hundreds of rows.

## Verification

Run and record:

```bash
python scripts/validate_project.py
make format
make check
make test
cd frontend && npm run test:e2e -- --project=chromium
cd .. && make build
git diff --check
```

## Explicit non-scope

- No accessibility audit, performance budgets, or full E2E hardening (Sprint 013).
- No container, backup, or release work (Sprint 014).

## Commit checkpoints

1. `feat: add batch update API with select-all and exclusions`
2. `feat: add virtualized triage table with filters and grouping`
3. `feat: add bulk action bar and keyboard shortcuts`
4. `test: add import-and-triage e2e scenario`
5. final `docs(sprint-012): close sprint and hand off`

## Risks and decisions to surface

- Virtualization library choice: react-window vs custom.
- Server-side select-all contract: how to represent exclusions in the API.
- Keyboard shortcut conflicts with browser or screen reader shortcuts.

## Outcome

_Not started. On completion record delivered behavior, commands and actual results, commit IDs,
deviations/decisions, and impact on every future sprint._
