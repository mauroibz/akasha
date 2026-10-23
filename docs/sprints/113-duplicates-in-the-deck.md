# Sprint 113 — Duplicates, in the deck

**Sprint:** 113
**Status:** in_progress
**Roadmap revision:** 49
**Depends on:** 112
**Owner:** Mauro

## Objective

Possible duplicates are found from stored data and shown in the deck two at a time. The owner
picks which one to keep, or says they differ; the kept entry absorbs the other without losing
anything the owner wrote (DEC-176 point 4).

## Required context

- DEC-176; the data-safety invariant (imported user data is never overwritten).
  `application/library.py` (`delete_entry`, `update_entry`), `prune_items.py`,
  `domain/normalization.py`, Sprint 112's deck shell, Sprint 110's location and loans.

## Deliverables

1. `GET /api/duplicates`: pairs of the owner's entries in the same domain whose items share an
   identifier, or whose normalized title and first creator are equal. Each pair once, never one
   the owner dismissed. No provider is consulted.
2. Migration 0029: `duplicate_dismissals` (`user_id`, `entry_low`, `entry_high`, unique).
   `POST /api/duplicates/dismiss`.
3. `POST /api/duplicates/merge {keep, drop}`: in one transaction, the kept entry keeps every
   non-empty value; its empty score, notes, dates, progress and location are filled from the
   other; shelves and formats are unioned; the other's loans move over (an open loan only when
   the kept entry has none); the other entry is deleted and its orphan item pruned.
4. `/deck/duplicates`: a card with both covers side by side and the facts that differ; *Keep
   this one* on either side, *They're different*, *Later*. Undo before leaving the deck is not
   offered for a merge; the card asks once before merging.
5. The *Chores* list shows the duplicate count.

## Acceptance criteria

1. A merge never overwrites a kept non-empty value (tested field by field).
2. A dismissed pair never returns.
3. Merging across users or domains is refused.
4. Accessibility and fit at 390×664.

## Verification

Per DEC-167: backend tests for the changed modules, migration on a temporary SQLite file,
`vitest related`, `make check`, `e2e/chores.spec.ts`, the deck in the running app on a library
with real duplicates (an edition imported twice).

## Explicit non-scope

Fuzzy title matching beyond normalization; merging items without entries.

## Outcome

_Not started._
