# Sprint 125 — Play, at the top of Insights

**Sprint:** 125
**Status:** planned
**Roadmap revision:** 51
**Depends on:** 124
**Owner:** Mauro

## Objective

The decks become games named after your own books, at the top of Insights; upkeep moves to Settings (DEC-179 point 4, mockup 2A).

## Required context

- DEC-179 and the *A second look* mockups (section named in the objective); DEC-176, DEC-178.

## Deliverables

1. A *Play with your library* section at the top of Insights: which of your Ns is best, an old score, the pile, and *Fill in the gaps*, each with its covers and shown only when it has something to ask.
2. *Fill in the gaps*: a deck of finished entries missing a finish date or format, asking the same questions as Sprint 124.
3. *Settings → Tidy up* holds covers and duplicates; `/deck` points to Play and Tidy up.

## Acceptance criteria

1. A game with nothing to ask is not drawn (tested).
2. The gaps deck fills a field and respects *I don't remember* (tested).
3. Fits at 390px and 1440px; accessibility passes.

## Verification

Per DEC-167: the tests for the changed code, `vitest related`, `make check`, the Playwright
specs for the changed screens, and the changed flow seen in the running app.

## Outcome

Not started.
