# Sprint 127 — The goal in the Diary

**Sprint:** 127
**Status:** completed
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

Delivered 2026-10-24 in `d67642a`. Verified per DEC-167: `goals.test.ts` (the paces, the slots,
the year's mark; red first) and `DiaryPage.test.tsx` (the slots in order, the bar above 24,
the one-tap invitation, the dialog behind *Another number*; red first); `vitest related`
(17); `make check`; Playwright `diary-goal` (new, at 390: one tap sets a goal; the slots fill
in order), `diary-timeline`, `year-review` and the Diary accessibility checks (the band with
slots, the invitation) in both schemes.
Walkthrough on a fresh backend: two books finished in 2026 and no goal gave "You've finished
2 books in 2026 · Want something to aim at this year?" with 6, 12 and 24; *Aim for 12* set it
and the band read "2 of 12" with two filled slots, the next one marked, ten dashed; a goal of
30 drew the bar, "2 of 30 books in 2026", with today's mark late in the year. No sideways
scroll at 390 or 1440.

1. One tap sets a goal for the shown library (Vitest, Playwright, walkthrough).
2. Slots fill with the year's finished covers in order, and switch to a bar above 24
   (Vitest, walkthrough).
3. Still gentle: no streaks, no red when behind (an empty slot is a dashed outline).

Deviations and notes:

- **The slots replace the calendar of lights** (Sprint 104) rather than sitting beside it;
  `calendarPlaces` and its tests went with it.
- **The invitation offers a yearly goal for the library finished most this year**, and only
  for the current year; the dialog still sets a monthly one or another library's.
- **The three numbers move up with the year:** past 6 finished they become 12, 24, 36.
