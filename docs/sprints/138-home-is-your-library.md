# Sprint 138 — Home is your library

**Sprint:** 138
**Status:** completed
**Roadmap revision:** 55
**Depends on:** 137
**Owner:** Mauro

## Objective

Home can show each library's year as the Diary's goal grid, with or without a goal, and any
shelf's covers, each a module the person turns on, sizes and places in *Edit home*. "This home
screen is your library" (the owner, DEC-192).

## Required context

- DEC-192; DEC-185 (the stored layout and its module keys); DEC-169 and DEC-179 (the goal band).
- Backend: `application/home_layout.py`, `application/home.py`, `api/home.py`,
  `application/goals.py`, the shelves tables; `backend/tests/test_home_api.py`,
  `test_home_layout.py`.
- Frontend: `features/home/` (`layout.ts`, `HomePage.tsx`, `EditHome.tsx`, `YearModule.tsx`,
  `ShelvesModule.tsx`), `features/goals/GoalBand.tsx` (`Slots`, `Bar`) and `goals.ts`
  (`slotsFor`), `api/home.ts`; the e2e console's layout stub.

## Current implementation baseline

Home's modules are a fixed set of ten keys. *The year* is twelve months led by one goal. The
Diary's goal band shows a domain's year as a grid of covers with a dashed slot for each one the
goal still needs; the owner likes it and wants it on Home for every library. *Shelves* lists
shelf names only.

## Deliverables

1. **Module families.** A layout key is a static module or `year:<item type>` or
   `shelf:<shelf id>`. The server lists every family member that exists (a registered domain; a
   shelf of this person) with a `label`, keeps a stored row only while its member exists, appends
   new ones with their default (a library's year shown, a shelf hidden), and refuses an unknown
   one on write.
2. **A library's year** (`year:<type>`, default M): "Your 2026 books", the count, of the goal's
   target when there is one; the goal band's slots (covers in finishing order, a dashed slot for
   each one still needed) when the goal is 24 or fewer, else the covers and the band's bar;
   without a goal, the year's covers. Shown only when the library has a finish this year or a
   goal. Opens the Diary.
3. **A shelf** (`shelf:<id>`, default M, hidden): its name, count, and covers of its most recent
   members, opening the shelf.
4. `/api/home` carries `library_years` and `shelf_rows` keyed by member, only for shown
   modules, read from stored data; *Edit home* lists the families under their labels.

## Acceptance criteria

1. A layout naming `year:book` and `shelf:<id>` round-trips; a deleted shelf's row disappears;
   another person's shelf id is refused (pytest).
2. `/api/home` gives a library's year with and without a goal, and a shown shelf's covers; a
   hidden module's section is absent; zero provider calls; the timing budget still holds (pytest).
3. The modules render, toggle and resize in *Edit home*, and an empty library's year is not
   drawn (Vitest; the Home e2e).
4. No `item_type ==` branch; axe passes and nothing overflows at 390 and 1440 px.

## Required tests (TDD)

`test_home_layout.py`, `test_home_api.py`, `features/home/*.test.tsx`, `e2e/home.spec.ts`.

## Verification

Per DEC-167, and Home in the running app with a realistic library at 1440 and 390 px.

## Explicit non-scope

Dragging modules (the arrows stay), modules for other things (a creator, a saved view).

## Commit checkpoints

`[ADD]` module families in the layout; `[ADD]` library years; `[ADD]` shelf modules; `[DOCS]`
close.

## Risks and decisions to surface

- A goal band shares `Slots` and `Bar` with the Diary rather than copying them.

## Outcome

Completed 2026-11-23 (DEC-192). Commits: `f5a336b` (module families in the layout and the two
`/api/home` sections), `96654ec` (the modules and *Edit home*), the label and technical spec
commit, and the closing documentation commit.

Delivered:

1. `application/home_layout.py`: `year:<item type>` for every registered domain whose
   `entry_fields` hold `date_finished` (books, anime, films, series; albums have none), default
   M and shown, after *Lately* so *The year* and *Lately* keep their row; `shelf:<id>` for each
   of the person's shelves, default M and hidden, at the end. Rows carry `label` ("Books this
   year", "Shelf: Favorites"); only `module`, `size` and `hidden` are stored. A deleted shelf
   drops out on read; an unknown member, another person's shelf included, is refused on write.
   The body takes up to 512 rows.
2. `library_years` and `shelf_modules` on `/api/home`, for shown members only, from stored data:
   a library's year reuses the year's finished rows (no new query); a shelf is two queries for
   all shown shelves together.
3. `features/home/LibraryYear.tsx` ("Your 2026 books"): the goal band's `Slots` with a goal of
   24 or fewer (S 4, M 6, L 8 columns), the band's `Bar` and the covers above 24, the covers
   alone without a goal (8, 12 or 24 by size, then "and N more"). `features/home/ShelfModule.tsx`:
   the shelf's name, "N on the shelf →" to the shelf, its covers. `Slots`, `Bar` and
   `slotsInOrder` are shared with the Diary's band (`features/goals`), not copied.
4. *Edit home* names family members by the server's label; `HomePage` draws a member only when
   the payload has it.

Acceptance criteria:

1. `test_home_layout.py`: `test_each_library_has_a_year_and_each_shelf_a_hidden_module`,
   `test_a_family_layout_round_trips_and_a_deleted_shelf_drops_out`,
   `test_a_family_member_that_does_not_exist_is_refused` (four cases),
   `test_another_persons_shelf_is_not_a_module`.
2. `test_home_api.py`: `test_each_librarys_year_and_a_placed_shelf_read_the_library` (a goal, a
   goal with nothing yet, no goal, a hidden year unread, a shown and a hidden shelf); the empty
   library gives both sections empty; `test_home_consults_no_provider` and the timing budget
   still pass.
3. `LibraryYear.test.tsx` (3), `HomePage.test.tsx` (a shelf and a year where the layout puts
   them, an empty year not drawn), `EditHome.test.tsx` (labels, switch, size), and two e2e
   tests in `home.spec.ts`.
4. No `item_type ==` above the registry (the year family comes from `entry_fields`). Axe with
   no serious violations and no overflow at 390 and 1440 px (the two e2e tests).

Verification: backend `test_home_layout` (19), `test_home_api` (13), `test_app_shape`,
`test_isolation`; `npx vitest related` over the changed files (86); Playwright `home.spec.ts`
and `diary-goal.spec.ts` 21 passed; `make check`. Walkthrough on the seeded library with a
book goal of 12 and three shelves: Home shows *Your 2026 books* (5 of 12, slots with the next
one marked) and *Your 2026 movies* (one cover); *Edit home* lists four library years and three
shelves (hidden); turning on *Shelf: Horror*, sizing it L and moving it up put it beside
*Lately*; at 390 px no overflow and no console errors.

Observed, left: a library's year without a goal and few finishes leaves its box mostly empty
beside a fuller neighbour, as *The year* did (DEC-184's finding); *Edit home* is long with many
shelves (it scrolls).
