# Sprint 141 — The library is the home

**Sprint:** 141
**Status:** ready
**Roadmap revision:** 56
**Depends on:** 140
**Owner:** Mauro

## Objective

Akasha opens on the Library: *Now*, *Lately*, the showcases, *Everything*. Home as a screen is removed.

## Required context

- DEC-193; [`../library-first-proposal.md`](../library-first-proposal.md) section 2.2, 3.1 and 3.3 and the mockup.
- DEC-183–185 (Home, its payload and stored layout), DEC-192 (module families), DEC-023 (the Library's DOM budget).
- Frontend: `features/home/` (all), `pages/LibraryPage.tsx`, `features/library/NowStrip.tsx`, `features/library/VirtualLibrary.tsx`, `App.tsx` (`HomeRoute`), `components/AppShell.tsx`.
- Backend: `application/home.py`, `api/home.py`, `tests/test_home_api.py`.
- `e2e/home.spec.ts`, `e2e/library.spec.ts`, `e2e/accessibility.spec.ts`.

## Current implementation baseline

Observed 2026-11-23 while writing the proposal (section 2); re-observe at activation. `/` is Home, a 12-column grid of ten modules and two families from `GET /api/home`; `/library` is the Library with a *Now* strip above the grid. *On now* and *Now* show the same entries with different buttons.

## Deliverables

1. **Bands.** Above the grid the Library draws the greeting sentence, **Now** (every entry under way, one card with the medium's progress step and *Mark as …*, replacing both `OnNow` and `NowStrip`) and **Lately** (one row of covers: finished with score, added; from the payload's `lately`).
2. **Showcases.** The stored layout's remaining modules render between Lately and the grid with the existing packing: `next`, `suggested`, `question`, `year:<type>`, `shelf:<id>`. The modules `now`, `lately`, `libraries`, `shelves`, `tidy`, `lent` and the all-media `year` are retired from the layout; a stored layout naming them is read without error and they are dropped.
3. **Addresses.** `/` renders the Library; `/library` redirects to `/` keeping its query; the navigation loses *Home*. *Edit home* still opens the existing dialog until 142.
4. **The payload.** `GET /api/home` stops computing the retired modules.

## Acceptance criteria

1. `/` shows Now, Lately, the showcases and the grid in that order; with nothing under way Now is absent and the sentence says so.
2. `/library?status=…` lands on `/` with the same filter.
3. A stored layout from 3.1 with every old module loads; the retired ones are gone and the kept ones keep their order and size (pytest and Vitest).
4. The Library's DOM budget tests pass with the bands above the grid; no serious axe violation or overflow at 390 and 1440 px; Home's render budget test is carried over.

## Required tests (TDD)

`LibraryPage` bands, the Now card, Lately (Vitest); `test_home_api.py`, `test_home_layout.py` (retired keys); `e2e/home.spec.ts` rewritten against `/`, `e2e/library.spec.ts`.

## Verification

Per DEC-167: the tests covering the changed code, `make check`, the Playwright specs for the changed screens, and a look at them in the running app at 1440 and 390 px in *Ink* and *Paper*.

## Explicit non-scope

Arranging in place and new showcases (142). Media order (143). The Shelves view (144).

## Commit checkpoints

`[ADD]` Now and Lately bands; `[MOD]` showcases on the Library; `[MOD]` `/` is the Library; `[DEL]` Home's retired modules; `[DOCS]` close, product spec 7.

## Risks and decisions to surface

- The grid is virtualised against the window scroll; content above it changes its offset.
- The greeting's counts ("N to sort") arrive in 140.

## Outcome

_Not started. On completion record delivered behavior, commands and actual results, commit IDs, deviations/decisions, and impact on every future sprint._
