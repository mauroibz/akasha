# Sprint 130 — Home: the module grid

**Sprint:** 130
**Status:** ready
**Roadmap revision:** 54
**Depends on:** 129
**Owner:** Mauro

## Objective

Akasha opens on Home: a dense 12-column grid whose first modules show what is under way, what is
next, the year, and one tile per library domain, all from one `GET /api/home` that reads stored
data only. The library keeps working, unchanged, at `/library`.

## Required context

- DEC-183; [`../home-and-recommendations-proposal.md`](../home-and-recommendations-proposal.md)
  §2; the mockup [`../home-and-recommendations-mockup.html`](../home-and-recommendations-mockup.html)
  (open it in a browser; covers are blanked).
- Technical spec §6.6 (the registry contract) and the invariant that no provider is consulted
  while rendering a page.
- Backend: `api/library.py` (`/now`, `/diary`, `/diary/timeline`, `/insights`, `/item-types`),
  `api/goals.py` and `application/goals.py` (`progress`, `picks`), `application/library.py`
  (`now()`), `domain/registry.py`, `domain/spec.py`.
- Frontend: `App.tsx` routes, `pages/HomePage.tsx` (today the library), `components/AppShell.tsx`
  (navigation; `/` is labelled *Library*), `components/DomainStrip.tsx`, `features/goals`,
  `features/diary`, `components/CoverImage.tsx`, `index.css` tokens (*Ink* and *Paper* themes).
- Every `navigate("/")` and e2e `page.goto("/")` that means "the library".

## Current implementation baseline

`/` renders `HomePage`, which is the library (filters, grid/list, virtualized). `/now` returns
entries in progress across domains. Goals expose progress and `picks` (waiting entries with a
reason: a favourite creator's, or the longest waiting). The Diary has month buckets and a
timeline. Navigation's first item is *Library* at `/`.

## Deliverables

1. **The move.** `pages/HomePage.tsx` becomes `pages/LibraryPage.tsx` at `/library`; every
   in-app link and redirect that meant the library points there; a `/` URL with library query
   parameters (`type`, `status`, `q`, `sort`, …) redirects to `/library` with them. Navigation
   gains *Home* first and keeps *Library*.
2. **`GET /api/home`** (`api/home.py`, `application/home.py`): one response with
   - `greeting`: today's date, the single most recently touched in-progress entry with the
     days since it started, library totals (entries, the current year's goal progress per domain
     that has one, pile size);
   - `now`: entries in progress across domains (reuse `Library.now()`);
   - `next`: up to five planned entries per the existing goal picks order (a placeholder order
     until Sprint 132), each with its reason;
   - `year`: for the current year, finished entries per month with their cover ids and domain,
     and each domain goal's target and count;
   - `domains`: one tile per registered domain that has entries: count, count per status
     category, score histogram, mean score, three best-scored covers, and how many lack a cover.
   The endpoint performs no network I/O (tested by forbidding provider calls) and answers in
   under 150 ms on a 10,000-entry library.
3. **The grid** (`features/home/`): a `HomePage` with a 12-column CSS grid, and modules
   `GreetingBar`, `OnNow` (actions: log progress where the domain tracks it, *Finished* via the
   existing finish sheet, *Set aside*), `UpNext` (*Start* moves an entry to in progress),
   `YearModule` (twelve months, covers in each, empty slots for what the goal still needs, the
   current month marked), `LibraryTiles` (each opens `/library?type=…`). Sizes are column spans
   from a static default layout; Sprint 131 makes it editable.
4. **The phone.** Below 720 px every module is full width in the same order; covers become
   horizontal rows; tiles go two across.
5. OpenAPI and `api/schema.d.ts` regenerated; technical spec gains the `/api/home` contract.

## Acceptance criteria

1. Opening `/` shows Home; `/library` shows the library exactly as `/` did; `/?type=anime`
   lands on `/library?type=anime` (tested in vitest and one e2e).
2. `/api/home` returns the five sections from stored data with zero provider calls (tested with
   a provider that fails the test if called), and per user: another user's entries never appear
   (tested with auth on).
3. Each module renders from the endpoint's payload, shows nothing broken for an empty library
   (a first-run message instead), and its actions change the entry (tested).
4. Domain tiles come from the registry; no `item_type ==` branch is added above it.
5. No horizontal scroll at 390 px and 1440 px in both themes; axe passes on Home.
6. Every existing e2e spec that opened the library at `/` opens `/library` and passes.

## Required tests (TDD)

- Backend: `tests/test_home_api.py` — sections, empty library, per-user isolation, no provider
  calls, the timing budget on a seeded large library.
- Frontend: `features/home/*.test.tsx` for each module; `App.test.tsx` for the routes and redirect.
- E2E: `e2e/home.spec.ts` (Home renders, *Start* and *Finished* work, a tile opens the filtered
  library), plus the updated library specs.

## Verification

Per DEC-167: the tests above, `npx vitest related` on changed files, `make check`, the Playwright
specs that cover Home and the library, and a look at Home in the running app with a realistic
library at 1440 px and 390 px, recorded in the worklog.

## Explicit non-scope

Lately, Tidy up, One question, Shelves, Lent out, Edit home (Sprint 131); ranking (132); any
recommendation (133+).

## Commit checkpoints

`[FEAT]` the library at `/library` with the redirect; `[FEAT]` `/api/home`; `[FEAT]` the grid and
modules; `[TEST]` e2e; `[DOCS]` close.

## Risks and decisions to surface

- The finish sheet and progress logging live in the detail page today; reuse their components
  rather than duplicating behavior.
- The greeting's "Day N of …" uses the entry's start date when one exists; without one, omit it.

## Outcome

_Not started._
