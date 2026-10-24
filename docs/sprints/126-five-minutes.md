# Sprint 126 — Five minutes

**Sprint:** 126
**Status:** completed
**Roadmap revision:** 51
**Depends on:** 125
**Owner:** Mauro

## Objective

One mixed round of five cards drawn from every game, ending with what changed (DEC-179 point 5, mockup 2C).

## Required context

- DEC-179 and the *A second look* mockups (section named in the objective); DEC-176, DEC-178.

## Deliverables

1. `/play/five`: five cards mixed from the pair game, the gaps, old scores and the pile, as many kinds as have something to ask.
2. An end screen listing what changed.
3. The first card in Play.

## Acceptance criteria

1. The round mixes kinds and never shows more than five cards (tested).
2. Each answer writes what its own game writes (tested).
3. Fits at 390px; accessibility passes.

## Verification

Per DEC-167: the tests for the changed code, `vitest related`, `make check`, the Playwright
specs for the changed screens, and the changed flow seen in the running app.

## Outcome

Delivered 2026-10-24 in `65bc87a`. Verified per DEC-167: `five.test.ts` (the pair, the order
written, the mix; written with the code, then tightened red-first when the walkthrough showed
a pair placing books never asked about), `FivePage.test.tsx` (red first: a round of four,
each write, the end), `PlaySection.test.tsx` (the lead card, and none with one game);
`vitest related` (79); `make check`; Playwright `play` (a whole round through Insights; the
phone fit), `chores`, `rescore` and the five-minutes accessibility checks in both schemes.
Walkthrough on a fresh backend at 390: six books dealt five cards (a pair of 8s, two gaps, an
old 10, the pile); *Every day* chosen over *Harry Potter*, two finish dates filled, *Tokio
blues* kept at 10, the pile's book let go and removed after the confirmation; the end listed
four changes. The 8s then read *Every day* 1, *Harry Potter* 2, *Matadero cinco* unplaced.

1. The round mixes kinds and never shows more than five cards (Vitest).
2. Each answer writes what its own game writes (Vitest, Playwright, walkthrough).
3. Fits at 390px; accessibility passes.

Deviations and notes:

- **A route of its own, `/play/five`**, as the sprint said; *Another round* reloads it.
- **The pair game writes the placed order plus the two compared**, so one answer never
  gives a place to a book nobody asked about (found in the walkthrough, fixed and tested).
- **The pair comes from the first library's most shared score**; old scores answered here
  are recorded as *Time*.
- **The decks' way out follows where they now live:** the pile and old scores go back to
  Insights, covers and duplicates to *Tidy up*.
