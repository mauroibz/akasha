# Sprint 100 — Re-file and saved views

**Sprint:** 100
**Status:** completed
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

**Delivered.**

- **Saved views.** Migration `0024_saved_views` (unique per person and name, cascades with the
  user); `GET/POST/DELETE /api/views`, where saving under a used name replaces its query.
  *Save view* sits at the end of the library's active-filter chips and stores the library's own
  URL query. Each view appears in the command bar as *Go to {name}* and opens `/?{query}`.
- **Re-file.** `POST /api/entries/{id}/refile` creates the confirmed record in the provider's
  domain through the add path, then deletes the old entry.
  - Carried across: status (the target's default when the target lacks it), score, notes, the
    passage fields the target declares, and shelves. Formats the target lacks are dropped.
  - Attachments move to the new item. The old item and its cover are deleted under the
    `prune_items` rule (DEC-168).
  - Refused: the same domain (`422 refile_same_domain`) and a target already in the library
    (`409 refile_target_exists`).
  - The Detail page's *Move to another library…* picks the library, searches it on a press, and
    moves the entry to the record chosen.

**Acceptance.**

1. `test_refile.py`: a series refiled as anime keeps score, notes, finish date and shelf; DVD is
   dropped; the old entry and item are gone. A book's `reading` becomes a movie's `watchlist`.
   Walked through live: Cowboy Bebop moved from Wikidata series to Kitsu anime (`mal:1`), and the
   old entry and item both answer 404.
2. `test_saved_views.py` plus the isolation registry: a view reopens its query exactly, and
   another person neither lists nor deletes it (404). Walked through live: *Books I read* saved
   from `?type=book&status=read` and reopened from the command bar at the same URL.

**Verification (DEC-167).**

- Backend: `test_saved_views`, `test_refile`, `test_isolation`, `test_library_api`,
  `test_app_shape` and `test_cached_add`, all green. Migration down and up runs inside
  `test_saved_views`.
- Frontend: `vitest related` on the changed files (20 files, 236 tests) and `make check`, both
  green.
- No Playwright spec was rerun. The live walkthrough drove the detail and command-bar flows
  instead (scratchpad `walk100.mjs`).

**Commits.** d89b83f, 467138d, 92f98db, af4d035.

**Deviations.**

- Re-file records no undo effect. The ROADMAP sketch mentioned one, but the sprint deliverables
  did not, and the undo ledger is batch-scoped to imports.
- Deleting the old item departs from DEC-158's "delete leaves the item": see DEC-168.
