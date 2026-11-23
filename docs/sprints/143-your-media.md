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

_Not started. On completion record delivered behavior, commands and actual results, commit IDs, deviations/decisions, and impact on every future sprint._
