# Sprint 138 — Home is your library

**Sprint:** 138
**Status:** planned
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

_Not started._
