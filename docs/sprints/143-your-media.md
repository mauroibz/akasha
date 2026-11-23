# Sprint 143 — Your media

**Sprint:** 143
**Status:** in_progress
**Roadmap revision:** 56
**Depends on:** 142
**Owner:** Mauro

## Objective

Each person orders their media and marks each *Front*, *Kept* or *Off*; every chooser, the bands and the bar follow.

## Required context

- DEC-193; [`../library-first-proposal.md`](../library-first-proposal.md) section 3.4 and the mockup.
- Technical spec 6.6 (the domain contract: no branch on a medium's name above the registry); DEC-146 (per-user data).
- Backend: `domains/` registry, `api/item_types` (wherever `GET /api/item-types` lives), `application/home.py`, the settings storage for per-user preferences, `alembic/versions/`.
- Frontend: `features/library/useItemTypes.ts`, `components/DomainStrip.tsx`, `features/command/CommandBar.tsx`, `pages/SettingsPage.tsx`, `pages/SetupPage.tsx`.

## Current implementation baseline

Observed 2026-11-23 while writing the proposal (section 2); re-observe at activation. The registry's order (Book, Album, Anime, Movie, Series) is every chooser's order for everyone; a medium with no entries is still shown.

## Deliverables

1. **Storage and API.** One migration: a per-user ordered list of `(item_type, presence)` with presence `front`, `kept` or `off`. `GET`/`PUT /api/media`; a medium the list does not name is appended as *Kept* if it has entries and hidden if it has none.
2. **Applied everywhere.** `useItemTypes` returns the person's media in order without the *Off* ones; choosers, the bar's default medium and the Journal follow it. Now, Lately, the greeting and *Up next* read *Front* media only (server side, in `application/home.py`).
3. **The control.** A *Your media* list in Arrange and in Settings: drag to order, a three-way control per medium. The first run asks "What do you keep?" once.

## Acceptance criteria

1. With Anime first and Albums off: the Library opens on Anime, no chooser lists Albums, an album under way is absent from Now, and its entries still exist and export.
2. A *Kept* medium is in the grid and the bar and absent from Now and Lately.
3. Two users keep separate lists (pytest, isolation).
4. No `item_type ==` comparison is added above the registry (`test_app_shape`).

## Required tests (TDD)

`test_media_preferences.py` (API, defaults, isolation), `test_home_api.py` (Front only); `useItemTypes`, the control (Vitest); `e2e/library.spec.ts`.

## Verification

Per DEC-167: the tests covering the changed code, `make check`, the Playwright specs for the changed screens, and a look at them in the running app at 1440 and 390 px in *Ink* and *Paper*. Migrate a copy of a real library and check counts.

## Explicit non-scope

Hiding a medium from import sources or export.

## Commit checkpoints

`[ADD]` media preferences and their API; `[MOD]` everything reads them; `[ADD]` the control and the first-run question; `[DOCS]` close.

## Risks and decisions to surface

- Turning *Off* a medium that is the Library's remembered medium.
- Deep links to an *Off* medium's entry still open.

## Outcome

Completed 2026-11-23 (DEC-193). Commits: `BACK` (storage, API, the front filtered), `FRONTH`
(the control, the choosers, the first-run question).

- **Storage and API.** Migration 0039, `media_preferences`. `application/media.py` and
  `GET`/`PUT /api/media`. `GET /api/item-types` is unchanged.
- **Applied.** `useShownItemTypes` orders and filters the choosers on the Library, the bar,
  Insights, tiers, the rank list and shelves. `GET /api/home` reads `now`, `lately`, `next`
  and the greeting's entry and goal from *Front* media only.
- **The control.** `YourMedia` in Arrange (below the tray) and in Settings: two arrows per
  medium and Front/Kept/Off, announced, stored at once; the Library's strip and front follow
  without a reload. `WhatDoYouKeep` on the empty Library for someone who holds nothing and has
  not chosen.

Acceptance: 1 by `test_media.py` (front only; kept and off still listed and counted), the
`library.spec.ts` strip test and the walkthrough; 2 by `test_media.py`; 3 by `test_media.py`
(isolation, and the route table in `test_isolation.py`); 4 by `test_app_shape.py`, unchanged in
what it forbids, with the two routes added to its fixture.

Verification: backend `test_media` 10, with `test_home_api`, `test_home_layout`,
`test_app_shape`, `test_isolation`, `test_ranking`, `test_recommendations` 151 passed; Vitest
641 passed; Playwright chromium and heavy-library, full run, 239 passed and 2 skipped by
design; `make check`. A copy of the development library migrated 0038 to 0039 on start: 22
items, 19 entries and 5 shelves before and after, integrity ok, no foreign-key violations.
Walked through at 1440 and 390 px: without a choice the list read Books and Albums in front
and Anime, Movies and Series off ("nothing yet"), and the strip showed only the two held;
moving Albums first and setting Books to Kept reordered the strip at once, the Library opened
on Albums, and *On now* (a book) left the front. No overflow, no console errors.

Deviations:

- Without a stored choice the default is derived: held media in front, the rest off, and
  everything in front when nothing is held. The sprint said an unnamed medium is "appended as
  Kept if it has entries"; that still holds once a list is stored. Deriving the first answer
  is what removes the three empty tabs the owner saw, without their doing anything.
- The registry endpoint does not filter. An *Off* medium's entries must still open and read in
  their own words, so choosers filter on the client and labels use the whole registry.
- The Add form's medium select and the importers still list every medium: adding the first
  item of a medium by hand or by import is how it comes to be held.
- The greeting's counts (entries, the pile) are still of the whole library.
- Moving is two arrow buttons per row, not a drag: five rows.

Observed, left: Arrange is long on a phone (the tray, then the media).

Impact on later sprints: 146's Journal tabs take `useShownItemTypes`. 147 defaults "which
media count" to the *Front* ones via `MediaService.front()`.
