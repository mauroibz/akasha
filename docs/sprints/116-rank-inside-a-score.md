# Sprint 116 — A rank inside a score

**Sprint:** 116
**Status:** completed
**Roadmap revision:** 49
**Depends on:** 115
**Owner:** Mauro

## Objective

Entries that share a score can be put in order by choosing between two of them in the deck.
The order never changes a score; the library and shelves sort by score, then by it (DEC-176
point 6).

## Required context

- DEC-176; Sprint 112's deck shell. `application/library.py` (sort keys and the keyset cursor),
  `pages/HomePage.tsx` (sort menu), insights' score distribution.

## Deliverables

1. Migration 0031: `entries.score_rank` (nullable real). Changing an entry's score clears its
   rank.
2. `PUT /api/entries/{id}/rank {after|before: entry_id}` sets a rank between neighbours.
3. `/deck/rank/:type/:score`: two cards; tap the one liked more. A binary insertion places each
   unranked entry in about log2(n) choices; *Same* leaves the pair adjacent; *Later* skips.
4. The library's score sort orders by score, then rank, then title; the cursor carries the rank.
5. Insights' "most of what you rate lands at 6" offers *Put your 6s in order*.

## Acceptance criteria

1. Choices never write a score (tested).
2. Keyset pagination stays stable with ranks (tested across a page boundary).
3. Fit and accessibility on the rank deck.

## Verification

Per DEC-167: backend tests for the changed modules, `vitest related`, `make check`, the library
spec and a new rank deck spec, seen in the running app.

## Outcome

Delivered 2026-10-23 in `8eb6457`. Verified per DEC-167: `test_score_rank.py` (6, observed
failing first) with pagination, queries, API, isolation, migrations, history, bulk, views,
insights, export (207); the insertion unit tests (5); `vitest related`; `make check`;
Playwright `rank` (new), `accessibility` (new checks, both themes), `insights`, `library`,
`chores`, `command-bar` (77). Walkthrough on a fresh backend with five live books at 8: the
Insights link, the deck answered from the keyboard to a chosen order, and the library's score
sort following it.

1. Choices never write a score (API test; a changed score sets the rank aside by trigger).
2. Keyset pagination holds across a page boundary with ranked and unranked entries.
3. Fit and accessibility on the deck: on a phone the covers and the answers sit above the
   bottom navigation (a reachability check, not only a viewport check).

Deviations and notes:

- **Ranks are written as a whole order** (`PUT /api/entries/rank {entry_ids}`), not between
  neighbours: the page holds the order and saves it after each placement.
- **One sort value.** The score sort reads `score × 1,000,000 − rank` (unranked last), so the
  keyset cursor stays one comparison.
- **The rank page is not on the shared deck.** Two cards side by side, tapped, does not match
  the deck's one card and a swipe; it is its own page with the deck's keys in spirit (← → = s).
- Found and fixed in the run: the Insights link failed the suite's 44px touch-target rule;
  the phone's bottom navigation covered the answers under a full page header.
- The back link says *Library* even when the deck was opened from Insights (the shared
  `BackToLibrary`). Left.
