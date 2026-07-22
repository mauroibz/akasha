# Sprint 004 — Frontend shell and virtualized library

**Status:** in_progress
**Depends on:** 003
**Roadmap revision:** 2

## Objective

Deliver a polished, keyboard-accessible library screen that consumes the stable entries API and
remains responsive with a seeded 5,000-entry collection.

## Required context

Read in order:

1. `AGENTS.md`
2. `docs/specs/product-spec.md` sections 2, 6, and 7
3. `docs/specs/technical-spec.md` sections 2, 7, 8, 9, and 10
4. `docs/decisions.md` DEC-005, DEC-006, and DEC-015
5. `docs/sprints/ROADMAP.md` Sprint 004 and downstream Sprints 006, 010, and 011
6. `docs/agent/WORKFLOW.md`
7. `frontend/openapi.json`, `frontend/src/`, `backend/src/book_tracker/api/library.py`, and
   `backend/tests/test_library_api.py`, `test_pagination.py`, and `test_bulk_api.py`

## Current implementation baseline

Sprint 003 provides typed OpenAPI schemas for entries, items, shelves, facets, cursor pagination,
and mutations. The frontend still contains only the Sprint 001 health view; it has no router, Query
client, library feature, virtualization, filters, design tokens beyond the baseline, or mutation UI.

## Deliverables

- Add the application shell, restrained Akasha design tokens, routing, Query client, and typed API
  boundary generated or checked against `frontend/openapi.json`.
- Build grid/table library views with server filters, facets, sort/order controls, infinite keyset
  loading, fixed-size virtualization, and persisted view preference.
- Add optimistic inline status/score editing with rollback, accessible announcements, and page-one
  invalidation when an active sort key changes.
- Add keyboard navigation/shortcuts with input-focus guards and reduced-motion behavior.
- Add a deterministic 5,000-entry seeded/browser test fixture without committing runtime data.

## Acceptance criteria (ordered, TDD)

1. `/` renders loading, empty, error, and populated library states from the typed API; default
   filters exclude inbox entries while facets expose its count.
2. Grid/table preference persists, filters and sort reset pagination, and infinite loading consumes
   opaque cursors without duplicating rows.
3. A seeded 5,000-entry fixture remains responsive and the DOM mounts only the visible overscanned
   rows/cards under the specified browser check.
4. Inline score/status edits are optimistic, clear provisional styling after score edits, invalidate
   an active sort from page one, and roll back with an accessible announcement on failure.
5. `/`, `a`, navigation, and score shortcuts work outside editable controls, never steal keystrokes
   from inputs, and maintain visible focus.
6. Motion respects `prefers-reduced-motion`; core loading/error/empty/list controls have accessible
   names, roles, contrast, and keyboard operation.

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

Also run the focused frontend component tests and Playwright/browser checks for keyboard guards,
optimistic rollback, reduced motion, virtualization DOM bounds, and the seeded 5,000-entry flow.

## Explicit non-scope

- No add/detail/import/triage screens, provider integration, cover upload, or job UI.
- No auth, global client store, offset pagination, or one-request-per-row bulk behavior.
- No backend contract changes unless a verified prerequisite defect blocks the frontend contract.

## Commit checkpoints

1. `feat: add frontend shell and typed library client`
2. `feat: add virtualized library views and filters`
3. `feat: add optimistic edits and keyboard behavior`
4. final `docs(sprint-004): close sprint and hand off`

## Risks and decisions to surface

- Virtualization must be verified by mounted DOM count, not visual impression alone.
- Cursor pages must be reset after filter/sort-key mutation and focus restored by entry ID.
- Keyboard shortcuts must share one editable-target guard across grid and table modes.

## Outcome

_Not started. The implementing agent replaces this section with delivered behavior, tests/commands
and results, commit IDs, deviations, and downstream changes before marking the sprint complete._
