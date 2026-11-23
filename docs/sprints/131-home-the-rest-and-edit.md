# Sprint 131 — Home: the remaining modules, and Edit home

**Sprint:** 131
**Status:** in_progress
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

_Not started._
