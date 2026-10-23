# Sprint 113 — Duplicates, in the deck

**Sprint:** 113
**Status:** completed
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

Delivered 2026-10-23 in `54b1980`. Verified per DEC-167: `test_duplicates.py` (5, observed
failing first) with isolation, library API and migrations (111); `vitest related` (21);
`make check`; Playwright `chores` and the accessibility checks (8, both themes). Walkthrough on
a fresh backend with live Open Library: *Ficciones* (1983, from search, Read, 9) and a
hand-entered *Ficciones (Spanish Edition)* (To read, a note, the Argentina shelf), as an import
would leave them; 390×740 Ink and 1280×900 Paper.

1. A merge never overwrites a kept value (API test field by field; walkthrough: status Read and
   score 9 kept, the note and the shelf filled in, the other entry 404).
2. A dismissed pair never returns, and the answer can be taken back (API, Vitest).
3. A merge across domains is 422 `different_libraries`; another user's entries are 404
   (isolation probes); two open loans are 409 `both_lent`.
4. Fits at 390×664 and 1440×900; accessibility passes.

Deviations and notes:

- **Both notes survive.** When both entries have notes the kept entry's come first and the
  other's follow after a blank line. Keeping only one would lose what the owner wrote; this
  extends rather than overwrites. Recorded as DEC-177.
- **The merged-away item stays** for the prune sweep, as after any delete (DEC-158); the sprint
  file said it would be pruned.
- **Candidates need a creator.** Two entries with no creator are never paired: a title alone
  ("Untitled", "Poems") is too weak a match.
- **Undo** is disabled after a merge (the deck's new `canUndo`); *They're different* undoes.
- The add path already refuses a near match unless confirmed, so duplicates mostly arrive by
  import; the tests confirm the near match to make them.
