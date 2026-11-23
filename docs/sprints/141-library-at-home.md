# Sprint 141 — The library is the home

**Sprint:** 141
**Status:** completed
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

Completed 2026-11-23 (DEC-193). Commit: `1a41bf2`.

- **`/` is the Library.** `/library` redirects to `/` with its query and hash. The navigation
  is Library, Shelves, Insights, Diary; the phone's tab bar is Library, the bar's button,
  Shelves, Insights. Internal links point at `/`.
- **The front** (`features/home/LibraryFront.tsx`) sits where the *Now* strip sat, on the plain
  Library only: the greeting (a second-level heading now), *On now* (Home's module, replacing
  the Library's strip, which is deleted), *Lately* as one row of covers, the showcases in the
  existing 12-column packing, then an *Everything* heading over the grid. It draws nothing
  while loading, on an error, on a malformed answer and for an empty library.
- **Showcases** are `next`, `question`, `suggested` and the two families. `now`, `lately`,
  `libraries`, `shelves`, `tidy`, `lent` and the all-media `year` are no longer modules; their
  components and payload sections are deleted. A 3.1 layout naming them loads, without them.
- **`GET /api/home`** always reads `greeting`, `now` and `lately`; `year`, `domains`, `tidy`,
  `shelves` and `lent` are removed, with their queries.
- *Edit home* is unchanged apart from listing fewer rows; 142 replaces it.

Acceptance: 1 by `LibraryFront.test.tsx` and `e2e/home.spec.ts`; 2 by `App.test.tsx` and the
e2e redirect test; 3 by `test_home_layout.py` (a stored 3.1 layout) and the front's tests;
4 by `library.spec.ts` in the heavy-library project (DOM budget unchanged), the home and
accessibility specs, and `test_home_api.py`'s budget test with every showcase shown.

Verification: backend `test_home_layout`, `test_home_api`, `test_app_shape`, `test_isolation`
83 passed; Vitest 631 passed; Playwright chromium and heavy-library, full run 223 passed with
17 expecting the old address, then those files 230 passed and `home`, `library`,
`accessibility` 95 passed; `make check`. Looked at on a copy of the development library at
1440 px in *Paper* and 390 px in *Ink*: greeting, one book under way, eight covers in Lately,
*Up next* beside *Your 2026 books*, then the grid. No overflow, no console errors.

Deviations:

- Only *Up next* and the libraries' years are shown by default; *One question* and *More like
  this* default to hidden. On Home they were shown. With all of them above it the grid started
  two screens down. A stored layout keeps what its owner chose.
- A cover in *Up next* and *More like this* is capped at 152 px. With two picks in a wide
  showcase each was 380 px across (the judgement call the 3.0 handoff recorded).
- An *Everything* heading was added above the grid; the medium tabs stay in the sticky toolbar
  at the top rather than beside that heading, because that toolbar must keep its height while
  the grid scrolls (DEC-139's rule for the virtualizer).
- *Lately* says "Added +2" under a cover where the list said "Added X and 2 more".
- The greeting's counts are unchanged (entries, the goal, the pile, *Edit home*).

Observed, left: *On now* is still a bordered box holding one large entry and smaller ones
beside it, where the mockup draws equal cards; with one thing under way most of the box is
empty at 1440 px. The medium tabs read as if they governed *On now* and *Lately*, which are
across media. Both are for 142–143 to settle with Arrange and the media order.

Impact on later sprints: 142 replaces `EditHome` and adds the `insight:` family to
`application/home_layout.py`. 143 filters `now`, `lately` and `next` to *Front* media in
`application/home.py`. 146 needs chores' own counts for *Tidy up*: `/api/home` no longer has
`tidy`.
