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

_Not started. On completion record delivered behavior, commands and actual results, commit IDs, deviations/decisions, and impact on every future sprint._
