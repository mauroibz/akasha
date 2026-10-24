# Sprint 126 — Five minutes

**Sprint:** 126
**Status:** in_progress
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

Not started.
