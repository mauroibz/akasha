# Sprint 116 — A rank inside a score

**Sprint:** 116
**Status:** in_progress
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

_Not started._
