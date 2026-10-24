# Sprint 121 — The revisit deck

**Sprint:** 121
**Status:** ready
**Roadmap revision:** 50
**Depends on:** 120
**Owner:** Mauro

## Objective

Old scores come back one card at a time: "Still a 9?", keep it or give the one it has now,
with *Reread it* or *Time* and a line of why, written to the score history (DEC-178, mockup 03).

## Required context

- DEC-178, DEC-176; Sprints 112 (the deck shell), 114 (score history) and 115 (`StillDialog`,
  `rescore.ts`). `features/deck/Deck.tsx`, `pages/ChoresPage.tsx`.

## Deliverables

1. `GET /api/revisit`: finished, scored entries whose latest score event is more than a year
   old (or that have none), oldest first, across every library.
2. `/deck/revisit`: the cover, "You gave it 9 in October 2024", the note if any, the score
   row, the reason chips (the domain's word for a reread: *Reread it*, *Rewatched it*), a line
   of why, *Later*, and *Keep 9* or *Change to 6*.
3. A chore on `/deck` with its count.

## Acceptance criteria

1. Keeping and changing each write one history row with the chosen reason (tested).
2. A score kept today does not come back for a year (tested).
3. Fits at 390×664 and 1440×900; accessibility passes.

## Verification

Per DEC-167: backend tests, `vitest related`, `make check`, the chores spec, seen in the
running app.

## Outcome

_Not started._
