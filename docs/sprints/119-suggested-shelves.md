# Sprint 119 — Suggested shelves

**Sprint:** 119
**Status:** planned
**Roadmap revision:** 49
**Depends on:** 118
**Owner:** Mauro

## Objective

The Shelves page proposes shelves from what the library already holds: the same creator three
or more times, the same series, and the same title across libraries (Dune the book and both
films). The owner accepts one in a tap or dismisses it for good (DEC-176 point 7).

## Required context

- DEC-176; DEC-139 and Sprint 105 (shelves as a room). `pages/ShelvesPage.tsx`,
  `application/library.py` (shelves), `domain/normalization.py`, the domains' `groupable` fields.

## Deliverables

1. `GET /api/shelves/suggestions`: proposals from stored data only, each with a name, a reason
   ("5 by Ursula K. Le Guin", "Dune in 3 libraries") and its entries; never one already matching
   an existing shelf or dismissed. Migration 0032: `shelf_suggestion_dismissals`.
2. `POST /api/shelves/suggestions/accept` creates the shelf with those entries.
3. A *Suggested* ledge at the top of the Shelves page, covers fanned, *Make this a shelf* and
   *Not useful*.

## Acceptance criteria

1. Proposals use only stored data (no provider in the request path, tested).
2. A dismissed proposal does not return; accepting one creates exactly its entries.
3. Accessibility and 390px fit.

## Verification

Per DEC-167: backend tests for the changed modules, `vitest related`, `make check`, the shelves
spec, seen in the running app.

## Outcome

_Not started._
