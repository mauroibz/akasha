# Sprint 142 — Arrange

**Sprint:** 142
**Status:** in_progress
**Roadmap revision:** 56
**Depends on:** 141
**Owner:** Mauro

## Objective

The Library is arranged where it stands: showcases are dragged, resized, removed and added on the screen itself, and a number from the Journal can be one.

## Required context

- DEC-193; [`../library-first-proposal.md`](../library-first-proposal.md) section 2.5 and 3.3 and the mockup.
- DEC-185 (layout storage and its write contract), DEC-192 (families), DEC-132 (Insights sections).
- Frontend: `features/home/EditHome.tsx`, `features/home/layout.ts`, the showcase components, `features/insights/sections.tsx`, `features/library/useInsights.ts`.
- Backend: `application/home.py` (layout), `api/home.py`, `tests/test_home_layout.py`; `application/insights.py`.

## Current implementation baseline

Observed 2026-11-23 while writing the proposal (section 2); re-observe at activation. *Edit home* is a dialog listing every module with S/M/L and a switch; it covers the screen it edits.

## Deliverables

1. **Arrange mode.** *Arrange* in the greeting line puts handles on each showcase: drag (and arrow keys) to reorder, S/M/L, remove. Changes save as they are made, through the existing layout endpoint. *Done* leaves the mode. The dialog is deleted.
2. **The tray.** In the mode, a tray lists what can be added: each shelf, each medium's year, *Up next*, *More like this*, *One question*, and numbers.
3. **A number from the Journal.** A new family `insight:<item type>:<section>` for the sections that fit a card (how you rate, the leading subject, decades): the section's sentence and its one figure or small chart, linking to the full section.

## Acceptance criteria

1. A showcase moved by keyboard or pointer keeps its place after a reload; removing one returns it to the tray.
2. Adding *How you rate* for a medium shows its sentence and distribution; a medium with no scores is not offered.
3. The layout endpoint refuses an unknown insight section and an unknown medium (pytest).
4. Arrange mode is operable by keyboard alone; no serious axe violation in the mode at 390 and 1440 px.

## Required tests (TDD)

Arrange mode and the tray (Vitest); `test_home_layout.py` (the insight family); `e2e/home.spec.ts` (arrange).

## Verification

Per DEC-167: the tests covering the changed code, `make check`, the Playwright specs for the changed screens, and a look at them in the running app at 1440 and 390 px in *Ink* and *Paper*.

## Explicit non-scope

Media order and themes in the same panel (143, 148).

## Commit checkpoints

`[ADD]` arrange in place; `[ADD]` the tray; `[ADD]` the insight family; `[DEL]` the dialog; `[DOCS]` close.

## Risks and decisions to surface

- Drag and drop on a touch screen; the existing dialog's keyboard reordering is the fallback pattern.

## Outcome

Completed 2026-11-23 (DEC-193). Commits: `e6a0000` placeholder.

- **Arrange in place.** *Arrange* in the greeting line (pressed while on) gives every placed
  showcase a strip: a handle (drag, or arrow keys: left and up earlier, right and down later),
  S/M/L and remove. A showcase with nothing to show stands in its place while arranging. Each
  change is stored at once through the existing layout endpoint. `EditHome` and its tests are
  deleted.
- **The tray.** Below the showcases while arranging: what is not placed, by kind (showcases, a
  year, a shelf, a number from Insights), then *Reset* and *Done*. Adding puts a showcase after
  those shown and moves the focus to its handle. Moves, additions and removals are announced.
- **A number from Insights.** `insight:<item type>:<section>` in `application/home_layout.py`,
  offered per medium held: `scores`, `decade` and each groupable field. `InsightShowcase` draws
  it from the existing insights endpoints: the rating sentence with a ten-bar distribution, or
  "You return most to …" with the first three rows linking into the library.

Acceptance: 1 by `Arrange.test.tsx`, `LibraryFront.test.tsx` and `e2e/home.spec.ts` (keyboard,
drag, reload); 2 by `InsightShowcase.test.tsx` and `test_home_layout.py`; 3 by
`test_home_layout.py` (five refused keys, isolation); 4 by the keyboard e2e test and the axe
test in arrange mode at 390 and 1440 px.

Verification: backend `test_home_layout`, `test_home_api`, `test_app_shape` 40 passed; Vitest
636 passed; Playwright `home`, `library`, `accessibility`, `insights` in chromium and
heavy-library 97 passed; `make check`. Walked through on a copy of the development library at
1440 and 390 px: the tray listed two showcases, four shelves and fourteen numbers (books and
albums, the media held); *How you rate books*, *Books by subjects* and the shelf *Work* were
added and drew beside each other after *Done*. No overflow, no console errors.

Deviations:

- A number is offered for a medium the person **holds an entry of**, not for one that has
  scores: the layout endpoint would need a count per section to know. A number with nothing to
  count says so in its box.
- The sections are every groupable field plus `scores` and `decade`, not three chosen ones:
  the registry already says which exist, and choosing three would be a branch on the medium.
  `decade` is drawn as a ranking (its three largest decades), not as the Journal's chart.
- The frontend tests for arranging were written after the code, not before; the backend's
  were written first.
- The owner's word for the source is "Journal"; until Sprint 146 the screen is still called
  Insights, so the tray and the link say Insights.

Observed, left: with five media held the tray's numbers run to about thirty-five buttons.

Impact on later sprints: 143 adds *Your media* beside the tray, and can filter the tray's
numbers to *Front* and *Kept* media. 146 renames "Insights" in `Arrange.tsx` and
`InsightShowcase.tsx`. 148 adds the theme swatches beside the tray.
