# Sprint 125 — Play, at the top of Insights

**Sprint:** 125
**Status:** completed
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

Delivered 2026-10-24 in `dd54cb0`. Verified per DEC-167: `test_gaps.py` (observed failing first)
with isolation, the documented routes and the app shape (both learn `GET /api/gaps`; shape
fixture regenerated, six lines); `PlaySection.test.tsx` and `GapsPage.test.tsx` (red first),
the Tidy up page test moved to its new contract; `vitest related` (300); `make check`;
Playwright `play` (new: the games, a game opening its deck, the gaps flow, phone fit),
`chores`, `insights` and the Play, gaps and Tidy up accessibility checks.
Walkthrough on a fresh backend at 390 and 1440: seven books gave four games ("Which 8 is
your best 8? · 3 books", "Is Tokio blues still a 10? · 2 old scores", "The pile · 2
waiting", "Fill in the gaps · 2"), no sideways scroll; the gaps page asked Rayuela's finish
date; `/deck` read *Tidy up* with the inbox, covers and duplicates and the line to the games.

1. A game with nothing to ask is not drawn (Vitest).
2. The gaps deck fills a field and respects *I don't remember* (API test, Playwright).
3. Fits at 390px and 1440px; accessibility passes.

Deviations and notes:

- **The best-score game follows the library shown on Insights** and picks its most shared
  score; the others are across every library, as their decks are.
- **The pile game's line names when the oldest was added**, so a pile added in one import
  reads "since October 2026".
- **Seen:** on a phone the four games take most of the first screen before Insights' own
  sentence. That is the placement asked for; worth the owner's look.
