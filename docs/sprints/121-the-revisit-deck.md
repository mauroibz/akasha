# Sprint 121 — The revisit deck

**Sprint:** 121
**Status:** completed
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

Delivered 2026-10-23 in `8b61b07`. Verified per DEC-167: `test_revisit.py` (observed failing
first) with isolation and the API suite (73); page tests (2) and the chores page test;
`vitest related` (285); `make check`; Playwright `chores` (revisit fit and flow) and
`accessibility` (52). Walkthrough on a fresh backend at 390 Ink: *Stoner* (9, 2021, a note)
and the 2021 *Dune* film (7, 2021) offered, Dune kept, Stoner changed to 6 with a line; both
then rest (the queue reads 0) and their histories hold `(7, 7, time)` and `(6, 9, time, …)`.

1. Keeping and changing each write one history row with the chosen reason (Vitest, API,
   walkthrough).
2. A score kept today does not come back for a year (API test, moving the row's date).
3. Fits at 390×664 and 1440×900; accessibility passes.

Deviations and notes:

- **The reasons are *Went back to it* and *Time*,** one wording for every library, rather than
  each domain's word for a reread (the mockup's *Rewatched it*): the domains declare no such
  word, and inventing one per domain in the shared layer is the branching the contract forbids.
- **Undo is off** in this deck: an answer is a history row, and taking one back would be
  another row, not an undo.
- **The eyebrow is *Revisit*:** "Look again" wrapped at 390px.
- The owner's note on the mockups ("02 … how often someone would open it if not prompted")
  may have meant this deck; DEC-178 records the reading. If so, this sprint is one commit.
