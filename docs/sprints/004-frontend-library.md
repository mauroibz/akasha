# Sprint 004 — Frontend shell and virtualized library

**Status:** completed
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

Delivered the Akasha application shell and checked OpenAPI library boundary (`2c38bec`), server-side
filter/sort/search controls, persisted grid/table preference, opaque-cursor infinite queries,
deduplication, fixed-size virtualization, optimistic score/status edits, shared editable-target
shortcut guards, focus restoration/navigation, reduced motion, and deterministic browser fixtures
(`01d0cdf`, `fc44dff`, `01e031e`, `22eb2ec`, `3cb636b`). Score edits immediately clear provisional
presentation; failures restore the snapshot and announce the rollback, without stealing focus from
the user's next control.

Verification: 49 backend tests and 9 frontend component tests pass. Two Chromium Playwright checks
pass for the seeded 5,000-entry flow (fewer than 20 mounted entries after deep scrolling), keyboard
guards/navigation, routing, and reduced motion. `python scripts/validate_project.py`, `make format`,
`make check`, `make test`, `make build`, OpenAPI type-surface checking, and `git diff --check` pass.
The isolated Python build initially could not resolve hatchling inside the network-restricted
sandbox; the required `make build` rerun outside that restriction passed.

Deviations: no product or sprint-scope deviation. Grid mode uses fixed-height virtual cover rows
rather than a masonry layout so both modes retain the specified stable fixed-size behavior. The
future add route intentionally renders only a scope boundary notice until Sprint 006. Review found
no required changes to Sprints 005–012; Sprint 005 was expanded from the roadmap against current
paths.
