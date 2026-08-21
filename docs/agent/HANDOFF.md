# Handoff — numbered plan complete through Sprint 036

Plan revision 18. **Sprint 036 closed on 2026-08-21 and project state is `complete`.** Sprints
001–036 are completed; active sprint fields are null; `FINAL_SPRINT` is 36. Nothing was tagged,
pushed, released or deployed.

## What now ships

The existing `/import` route reads as two independent steps: **1. Import** contains the registered
source tabs, and **2. Triage** contains review. Connector URLs, remembered source, staged previews,
undo and the old `/triage` redirect retain their behavior.

In Triage, status and score are editable directly on every row. Each control writes only that entry
with optimistic rollback. Clicking the row body opens detail; only the checkbox enters pointer bulk
selection. Shift ranges, Ctrl/Cmd+A, bulk actions, keyboard shortcuts and bounded virtualization
remain. The controls fit a 390 px viewport, and a short inbox uses only the height its rows need.

## Closure evidence

- `make check` passed Ruff, Prettier, ESLint, mypy, TypeScript, OpenAPI and project validation.
- `make test` passed 559 backend and 179 frontend tests; the affected frontend gate passed all 179
  again after the final accessibility-only JSX correction.
- Full Playwright at one worker passed 101 with 2 intentional skips. Focused Triage (16), Triage axe
  (2) and production-bundle (2) checks passed.
- Realistic-data mobile walkthrough exercised both steps, two row-local edits, row navigation and
  checkbox-only bulk selection. It found and drove the short-inbox height repair; the repeat had no
  overflow, console error or page error. Live owner data was never mutated.

## Testing next time

Follow `docs/agent/TESTING.md` and DEC-084: stabilize focused checks, freeze implementation, run each
affected exhaustive gate once, then classify closure-only diffs. Do not automatically repeat backend
tests after frontend- or documentation-only changes.

Reusable owner-data flows live locally under ignored `frontend/e2e/scratchpad/` and are excluded from
ordinary Playwright discovery. Opt into one explicitly from `frontend/` with
`BOOK_TRACKER_INCLUDE_SCRATCHPAD=1 npm run test:e2e -- --project=chromium --workers=1
e2e/scratchpad/<file>.spec.ts`. Adapt the closest runner rather than recreating and deleting it.

## Known and left

- `_bundle` still refuses a missing root `metadata.db` with Calibre-specific wording even though
  allowed members are connector-declared. Generalizing required root files needs a scoped follow-up.
- Playwright still emits proxy errors for optional endpoints that some isolated specs do not stub,
  and Vitest still emits JSDOM/reduced-motion warnings. They are noisy but green; DEC-084 records
  fixture centralization and warning cleanup as optimization work.
- The two heavy library browser cases remain load-sensitive with parallel workers. One worker is the
  established exhaustive gate; do not weaken their DOM or keyboard invariants.

## Next

No numbered sprint is active. A future session must first plan a new remediation sprint or select an
unnumbered roadmap epic, update `FINAL_SPRINT`, and move state from `complete` through the normal
planning protocol. Do not push, tag, deploy or release unless the owner asks.
