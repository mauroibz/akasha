# Sprint 006 — Add, detail, and metadata-edit UI

**Status:** ready
**Depends on:** 004, 005
**Roadmap revision:** 2

## Objective

Deliver keyboard-complete manual/provider add, entry detail, item editing, cover replacement, and
explicit metadata refresh flows on top of the cached Sprint 005 boundary.

## Required context

Read in order:

1. `AGENTS.md`
2. `docs/specs/product-spec.md` sections 2, 4, 6, and 7
3. `docs/specs/technical-spec.md` sections 4, 6, 7, 8, 9, and 10
4. `docs/decisions.md` DEC-003, DEC-005, DEC-006, DEC-007, DEC-011, DEC-012, and DEC-015
5. `docs/sprints/ROADMAP.md` Sprint 006 and downstream Sprints 007, 009, 010, and 011
6. `docs/agent/WORKFLOW.md`
7. `frontend/openapi.json`, `frontend/src/api/`, `frontend/src/features/library/`,
   `frontend/src/pages/`, `backend/src/book_tracker/api/library.py`,
   `backend/src/book_tracker/api/providers.py`, `backend/src/book_tracker/application/add.py`,
   and their focused tests

## Current implementation baseline

The library UI has typed queries, fixed-size virtual grid/table views, optimistic opinion edits,
and shared keyboard guards. `/add` remains a placeholder. The backend exposes typed provider
search/resolve and one-call cached entry creation with duplicate/near-match outcomes, plus item and
entry patching. It does not yet expose cover upload or explicit provider refresh routes, and the
frontend has no detail, metadata-edit, add, duplicate, or refresh experience.

## Deliverables

- Add typed frontend clients and accessible pages/components for provider search, URL/ISBN resolve,
  edition choice, manual fallback, status/score/shelf selection, and one-call creation.
- Add entry detail with opinion editing and item metadata editing while preserving the distinction
  between user opinion fields and shared cached item fields.
- Add bounded cover-replacement and explicit confirmed-refresh backend contracts with generated
  OpenAPI, then expose them in the detail UI.
- Add duplicate navigation/toasts, advisory near-match confirmation, loading/error/degraded-provider
  states, keyboard focus management, and reduced-motion behavior.

## Acceptance criteria (ordered, TDD)

1. `/add` supports debounced provider search plus ISBN/URL resolution, partial-provider warnings,
   explicit Open Library work-edition choice, and a manual fallback without requiring a mouse.
2. Manual and selected-provider submissions call `POST /api/entries` once; new entries navigate to
   detail, exact duplicates navigate to the existing detail with an announced toast, and near
   matches remain addable only after an explicit advisory confirmation.
3. The detail page renders entirely from cached local APIs while providers are unavailable and
   edits status, score, dates, notes, shelves, title, subtitle, year, and metadata through typed
   mutations with validation and accessible rollback errors.
4. Cover replacement enforces upload byte/type/pixel limits, normalizes to local JPEG, installs
   atomically without losing the prior valid cover on failure, and updates the detail/library cache.
5. Explicit refresh requires overwrite confirmation, fetches and validates outside the write
   transaction, overwrites only provider-managed fields present in the payload, preserves omitted
   fields and all opinion data, and leaves the item unchanged on provider failure.
6. Focus moves predictably through search, picker, duplicate/near-match messaging, detail, and edit
   dialogs; editable-target shortcut guards and reduced motion remain effective at mobile and
   desktop widths.

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

Also run focused backend cover-upload/refresh contract tests and Playwright flows for provider and
manual add, work-edition choice, exact/near duplicates, cached detail with providers down, metadata
edit persistence, refresh complete/partial/failure, cover replacement failure, keyboard focus, and
mobile layout.

## Explicit non-scope

- No Goodreads/Calibre imports, durable job runner, undo, import triage, or plugin registry.
- No automatic fuzzy merge, arbitrary work-edition selection, background refresh, or auth.
- No provider access during ordinary detail/library rendering and no overwrite without explicit
  refresh confirmation.

## Commit checkpoints

1. `feat: add provider and manual add experience`
2. `feat: add cached entry detail and metadata editing`
3. `feat: add cover replacement and explicit refresh`
4. `test: verify keyboard-complete add and detail flows`
5. final `docs(sprint-006): close sprint and hand off`

## Risks and decisions to surface

- Near matches must be presented as advisory choices, never silently merged or blocked.
- Refresh payload presence must be distinguishable from null/omitted values before overwriting.
- Failed cover replacement must retain the previous valid file/path; filesystem and DB writes need
  explicit compensation.
- Detail routing and invalidation must preserve focus without reintroducing provider reads.

## Outcome

_Not started. The implementing agent replaces this section with delivered behavior, tests/commands
and results, commit IDs, deviations, and downstream changes before marking the sprint complete._
