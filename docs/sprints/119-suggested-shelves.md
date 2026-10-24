# Sprint 119 — Suggested shelves

**Sprint:** 119
**Status:** completed
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

Delivered 2026-10-23 in `9bf7e60`. Verified per DEC-167: `test_shelf_suggestions.py` (5; the
cover case observed failing first) with isolation, API, migrations and the shelf room (114);
`vitest related` (166); `make check`; Playwright `suggested-shelves` (new), `shelves`,
`library` and `accessibility` (new checks, both themes). Walkthrough on a fresh backend with
three live Le Guin novels, *Dune* the book (Open Library) and the 2021 film (Wikidata): both
suggestions offered, *Dune* made into a shelf holding the book and the film.

1. Proposals use stored data only (a test with no provider wired).
2. A dismissed proposal never returns; accepting creates exactly its entries; a proposal a
   shelf already holds is not offered.
3. Accessibility and 390px fit; the ledge scrolls inside itself.

Deviations and notes:

- **Series reads a field named `series`.** It is a field's name, not a domain's (books declare
  it today), so the shared layer still never asks which domain it holds.
- **The inbox is left out**: an entry not yet filed is not yet the owner's library.
- Found and fixed before the commit: a member's cover URL used the entry id where the item id
  belongs (a test now covers it).
- Accepting a suggestion whose name an existing shelf already uses answers the existing
  `shelf_slug_conflict`; such a suggestion is not offered in the first place.
