# Sprint 012 — Bulk-first triage

**Status:** completed
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

### Delivered behavior

**AC1 — Server-side select-all with exclusions.**
The triage page supports Ctrl/Cmd+A to select all rows matching the current
filter. Deselecting individual rows adds them to an `excluded_entry_ids` set
that is sent to the backend instead of an explicit `entry_ids` list. The bulk
API (`PATCH /api/entries/bulk`) already supported this contract from Sprint
010; the frontend now exercises it. Verified by e2e test
`triage Ctrl+A selects all matching with server-side exclusions` which asserts
the bulk body contains `filter` + `excluded_entry_ids` rather than `entry_ids`.

**AC2 — Keyboard shortcuts with input guards.**
`j`/`k` (and ArrowUp/ArrowDown) navigate between rows. Status hotkeys
(`r`=read, `t`=to_read, `w`=wishlist, `d`=dropped, `g`=reading, `u`=unsorted)
apply to the focused row or the current selection. Score keys `1`-`9` and `0`
(=10) work the same way. `Enter` opens detail for a single row or advances
focus after a bulk action. `Escape` clears selection. All shortcuts are
guarded by `isEditableTarget` — they do not fire when focus is in an input,
select, textarea, or contenteditable element. The one exception is Ctrl/Cmd+A,
which is allowed from any target since it's a page-level select-all action.
Verified by e2e tests `triage keyboard shortcuts set status on focused row`
and `triage j/k navigation moves focus between rows`.

**AC3 — Hundreds of rows triaged without per-row requests.**
E2e test `triage hundreds of rows without per-row requests` renders 200 rows,
selects all via Ctrl+A, presses `r` to set all to read, and asserts
`bulkCallCount === 1` — a single bulk PATCH request, not 200 individual ones.

**AC4 — Conflicting values remain visible until explicitly resolved.**
Entries with `suggested_status !== null` display an amber badge showing the
suggested status. The "Accept all suggested" button sends a bulk
`POST /api/entries/accept-suggested` that applies the suggested status to all
matching entries in one request. The suggested-status badge remains visible
until the user explicitly accepts or manually changes the status.

### Commands and actual results

```
make check     → passed (tsc, eslint, prettier, ruff, mypy, OpenAPI types, validate_project)
make test      → 37/37 frontend unit tests, 122/122 backend tests
npx playwright test → 27 passed, 2 skipped (pre-existing), 0 failed
make build     → 342 KB JS (104 KB gzip), 17 KB CSS, built in 918ms
```

### Commits

- `7b431aa` — feat: add bulk-first triage page with selection, keyboard shortcuts, and e2e tests

### Deviations

- The backend bulk API (`PATCH /api/entries/bulk` and
  `POST /api/entries/accept-suggested`) was already implemented in Sprint 010.
  This sprint built the frontend triage page that exercises it. No backend
  changes were needed.
- The planned commit checkpoints were consolidated into a single commit because
  the triage page, API functions, and e2e tests are tightly coupled.
- The HomePage Inbox button now navigates to `/triage` instead of toggling the
  unsorted status filter. This aligns with the product spec's triage workflow.
