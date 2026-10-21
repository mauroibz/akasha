# Sprint 100 — Re-file and saved views

**Sprint:** 100
**Status:** in_progress
**Roadmap revision:** 45
**Depends on:** 099
**Owner:** Mauro

## Objective

An item that landed in the wrong library can be moved to the right one, keeping everything that
is yours about it; and a library filter you use often can be saved under a name and reached from
the command bar.

## Required context

- `docs/sprints/ROADMAP.md`, "Not scheduled": *Re-file an item into another domain* (the
  re-file shape: search the target domain, confirm, create properly, transfer the entry, remove the
  old item, record an undo effect) and *Saved views*; `docs/guides/adding-a-domain.md` §8;
  DEC-139 (saved views accepted in principle); DEC-167.
- `application/add.py`, `application/library.py`, `application/undo.py`, the import effects
  ledger, `features/command/CommandBar.tsx`, `pages/HomePage.tsx` (filters).

## Deliverables

1. **Re-file.** `POST /api/entries/{id}/refile` with a confirmed target-domain record: creates the
   item in the target domain from the provider record, moves the entry's status (mapped to the
   target's default when not declared there), score, notes, dates, shelves and formats the target
   declares, removes the old item when nothing else references it. Detail page: *Move to another
   library…* opens a dialog that searches the target domain and confirms.
2. **Saved views.** A `saved_views` table (migration), `GET/POST/DELETE /api/views`; the library's
   *Save view* names the current filters; saved views appear in the command bar's *Go to* and
   open the library filtered.

## Acceptance criteria

1. A series re-filed as an anime keeps score, notes, finish date and shelves; a status the anime
   domain lacks becomes its default; the old item is gone.
2. A saved view reopens the exact filters it was saved with; another person never sees it.

## Verification

Per DEC-167, plus the route-structure tests and a migration up/down; `vitest related`,
`make check`, the detail and command-bar specs.

## Outcome

_Not started._
