# Sprint 131 — Home: the remaining modules, and Edit home

**Sprint:** 131
**Status:** completed
**Roadmap revision:** 54
**Depends on:** 130
**Owner:** Mauro

## Objective

Home carries every module in the approved design, and each person can reorder, resize and hide
them, with the layout stored on the server.

## Required context

- DEC-183; the proposal §2 and the mockup's *On the phone, and editing* section.
- Sprint 130's Outcome and DEC-184; `features/home/` (`layout.ts` holds the module keys
  `now`, `next`, `year`, `libraries` and the column spans; the year spans 12 until Lately takes
  the five columns beside it at 7), `application/home.py`, `api/home.py`, and the empty
  `/api/home` stub every e2e spec gets from `e2e/console.ts`.
- The sources: `/diary/timeline` (Lately), `/duplicates`, the covers deck and finished-unscored
  queries behind `/deck` (Tidy up), `features/play` and `features/questions` (One question),
  `/shelves`, `/loans`.
- Migrations: `backend/alembic/versions/0035_join_indexes.py` is the latest.

## Deliverables

1. Modules: `Lately` (finishes, score changes, additions, newest first, eight rows), `TidyUp`
   (duplicate pairs, items without a cover, finished without a score; each count opens its deck),
   `OneQuestion` (one Play question answered in place), `Shelves` (most recently used shelves with
   counts), `LentOut` (open loans). A module with nothing to show is hidden until it has something.
2. Migration `0036_home_layouts`: `home_layouts(user_id PK → users, layout_json, updated_at)`.
3. `GET /api/home/layout` and `PUT /api/home/layout`: an ordered list of
   `{module, size: "S"|"M"|"L", hidden}`; unknown module keys ignored on read and refused on write;
   missing modules appended with their defaults on read.
4. *Edit home*: a panel listing modules with drag (and keyboard up/down) to reorder, S/M/L, and a
   switch to hide; *Reset* restores the default.
5. `/api/home` gains the new sections and honours `hidden` (skips work for hidden modules).

## Acceptance criteria

1. Each new module renders from stored data and links to the screen that resolves it (tested).
2. A layout saved by one user does not change another's (tested with auth on).
3. A stored layout naming a module that no longer exists still loads (tested).
4. Reordering works with the keyboard; axe passes with the panel open.
5. At 390 px every size is full width and only changes how much a module shows.
6. The migration upgrades and downgrades cleanly on a copy of a real-shaped library.

## Required tests (TDD)

Backend: layout API (round trip, isolation, unknown keys, defaults), migration test, home
sections. Frontend: each module and the panel. E2E: `e2e/home.spec.ts` gains edit, reorder and
hide, persisting across a reload.

## Verification

Per DEC-167, plus a walkthrough of Home and Edit home in the running app at both widths.

## Explicit non-scope

The ranked pile (132); recommendations (133+).

## Commit checkpoints

`[FEAT]` modules; `[DB]`/`[FEAT]` layout storage and API; `[FEAT]` Edit home; `[DOCS]` close.

## Risks and decisions to surface

Drag-and-drop library: prefer what the tier board already uses over adding a dependency.

## Outcome

Completed 2026-11-22. Home carries every module of the approved design except *More like this*
(Sprint 134), and each person reorders, resizes and hides them, stored on the server. The three
things Sprint 130's walkthrough left are fixed. Choices the plan left open are DEC-185.

**Delivered**

- `GET /api/home` gains `lately`, `tidy`, `question`, `shelves`, `lent` and skips a hidden
  module (`8a4a151`); `GET`/`PUT /api/home/layout` over `home_layouts`, migration
  `0036_home_layouts` (`8a4a151`); `GET /api/entries?unscored=true` (`8a4a151`).
- The five modules, *Edit home* (drag by pointer events on a handle, arrow keys, S/M/L, hide,
  Reset), row packing, sizes changing how much shows (`e9dbcdd`).
- Sprint 130's findings: Year beside Lately at 7 and 5 (default layout, `e9dbcdd`); On now's
  actions on one line at 390 px (`7970a69`); the greeting names one library (`451d3cb`).
- Found in this sprint's walkthrough and fixed: Tidy up's unscored count across libraries opened
  as one library's share (`da08275`); a kept score read "9 → 9" in Lately (`9b072b2`).

**Acceptance criteria**

1. Each new module renders from stored data and links to what resolves it — backend
   `test_the_remaining_modules_read_the_library`, `test_one_question_asks_an_old_score_again_before_a_gap`,
   `test_tidy_ups_unscored_count_is_what_its_library_link_lists`; Vitest `modules.test.tsx`
   (each module's links); walkthrough clicked every Tidy up link (1 pair → duplicates deck
   "1 left"; 42 → covers deck "42 left"; 7 anime and 3 books → library "7 of 82", "3 of 106"),
   a shelf and Lent out, and answered One question in place.
2. One user's layout does not change another's — `test_one_persons_layout_does_not_change_anothers`
   (auth on, two sessions, and 401 without one); isolation policy table updated.
3. A stored layout naming a module that no longer exists still loads —
   `test_a_stored_layout_naming_a_module_that_no_longer_exists_still_loads` (unknown key, a
   non-object row, an unknown size) and `..._that_is_not_json_reads_as_the_default`; `/api/home`
   answers 200 beside it.
4. Keyboard reordering; axe with the panel open — Vitest `EditHome.test.tsx` (arrow keys, focus
   kept, live announcement, two presses before the parent re-renders); Playwright *Edit home
   reorders with the keyboard…* and *Edit home has no serious axe violations* at 390 and 1440.
5. At 390 px every size is full width — Playwright measures every module's width equal at
   390 px; walkthrough: all nine modules 358 px wide at 390, scroll width 0 in Ink and Paper;
   size tests for On now, Up next, Lately, Shelves.
6. The migration upgrades and downgrades cleanly — `test_0036_upgrades_and_downgrades_on_a_real_shaped_library`
   (two people, entries, a goal; foreign key and cascade checked); and a copy of the
   walkthrough's 347-entry library downgraded to 0035 and upgraded to head with every count
   unchanged (items 347, entries 347, shelves 4, loans 3, score events 275, goals 2),
   `integrity_check` ok and no foreign-key violations at each step.

**Tests run** (DEC-167): backend `test_home_api`, `test_home_layout`, `test_isolation`,
`test_library_batching`, `test_duplicates`, `test_chores`, `test_migrations`,
`test_security_migrations` — 152 passed; `/api/home` budget test 126–133 ms median (it reached
213 ms before duplicate pairs moved to plain rows). `npx vitest related` over the sprint's
frontend diff — 52 files, 389 passed. `make check` green. Playwright `home` (16), `library`,
`auth`, `chores` — 54 passed; `accessibility` 105 passed, 1 failed: *the add dialog over the
library* fails intermittently on a contrast probe inside the add dialog, and fails the same way
on the base commit with this sprint's changes stashed (1 of 4 runs), so it is not this sprint's.

**Walkthrough**: `scripts/walkthrough.py --keep`, seeded by a scratchpad script (347 generic
entries over five domains, score changes, shelves, loans, a duplicate pair, a book and an anime
goal with the anime touched last), vite on 5180. Recorded in the worklog.

**Deviations**

- The sprint file named "finished-unscored queries behind `/deck`"; there are none. Tidy up's
  third count opens the library through a new `unscored` filter, per library (DEC-185 §2).
- Lately reads ten rows, not eight, so its sizes differ; the default size shows eight.
- Commit tags follow `CONTRIBUTING.md` (`[ADD]`, `[FIX]`) rather than the sprint file's
  `[FEAT]`/`[DB]`, which that file does not define. The backend sections and the layout storage
  went in one `[ADD]` (`8a4a151`), and the frontend modules and *Edit home* in one (`e9dbcdd`),
  because both `HomePage` and `/api/home` carry the two together; `da08275` also carries
  Lately's ten-row read.
