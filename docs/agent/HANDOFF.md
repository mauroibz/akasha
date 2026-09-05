# Handoff — Sprint 072 implementation complete; exhaustive gate deferred

Branch `ui-readability-proposal`, local only, nothing pushed. Sprint 072 remains `in_progress` by
the owner's explicit request to defer the remaining tests. The only tracked worktree changes are
this handoff and the appended worklog entries; application and test changes are committed.

## Delivered commits

- `edc1fe3` — grid/container geometry and in-progress state.
- `565e6aa` — vertical cover-first card, readable cover controls and metadata.
- `060792a` — one command bar, Filters popover/chips, and correct `N` / `N of M` total.
- `3bacbc3` — genuinely dense 52px list and bounded overscan.
- `e3aeacb` — five-domain command bar stays above the measured fold.

## Evidence already captured

- `make check` passes.
- Focused Vitest passes (HomePage 50/50; broader affected set 76/76).
- Focused Playwright acceptance checks pass. Deterministic 10,000-entry measurements are grid
  6 rows / 30 cards and table 19 rows / 19 cards.
- Fresh 20-entry realistic walkthrough passes: first card y=293/144/144 at 390/1440/2560;
  columns 1/6/6; cover area 72.8%; table 15 visible rows; no body overflow or browser errors;
  score/status/filter/navigation persisted. The wide poster centre-crops strongly; the light-cover
  controls remain readable on their opaque backing. The owner's `127.0.0.1:8000` was not mutated.

## Exact remaining work

1. Rerun `make test`; the interrupted capture is not a pass.
2. Run the full `npx playwright test`. If the degraded-provider axe timing sample recurs, settle
   the crossfade before axe rather than weakening accessibility assertions.
3. Run `python scripts/validate_project.py` distinctly (it already passed inside `make check`).
4. Reconcile and close: Sprint 072 Outcome (including every changed test and the 112px text block
   deviation), any material DEC append, ROADMAP review, status/state transition to Sprint 073
   `ready`, final worklog/HANDOFF, closure validator plus `git diff --check`, and the final
   `[DOCS] Close sprint 072 and hand off` commit.

Observed outside scope: after an inline status mutation, the filter facet label stayed stale until
refresh (`To read 4`) while the filtered response and total were correctly `3 of 20`. Do not hide
this in Sprint 072's Outcome; record/schedule it as a cache invalidation defect.

After 072 closes, Sprint 073 redesigns Insights (hero, chronology, score distribution and long-tail
cards). Sprint 074 then turns Shelves into a visual board with cross-domain shelf pages and pinning;
074 is the current final planned sprint. Saved views are accepted in principle but unscheduled.
