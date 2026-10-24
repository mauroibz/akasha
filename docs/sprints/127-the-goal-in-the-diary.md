# Sprint 127 — The goal in the Diary

**Sprint:** 127
**Status:** planned
**Roadmap revision:** 51
**Depends on:** 126
**Owner:** Mauro

## Objective

The gentle goal leads the Diary: an invitation with suggested numbers when none is set, and a row of slots the year's covers fill when one is (DEC-179 point 6, mockups 3A and 3B).

## Required context

- DEC-179 and the *A second look* mockups (section named in the objective); DEC-176, DEC-178.

## Deliverables

1. No goal: the year so far and three suggested numbers in plain words, one tap to set one; *Another number* opens the existing dialog.
2. A goal: the count, a slot per thing aimed at, filled by the year's covers in order; above 24, a bar with today's mark.
3. Still gentle: no streaks, no red when behind.

## Acceptance criteria

1. One tap sets a goal for the shown library (tested).
2. Slots fill with the year's finished covers in order, and switch to a bar above 24 (tested).
3. Fits at 390px and 1440px; accessibility passes.

## Verification

Per DEC-167: the tests for the changed code, `vitest related`, `make check`, the Playwright
specs for the changed screens, and the changed flow seen in the running app.

## Outcome

Not started.
