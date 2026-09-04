# Sprint 071 — What the numbers say

**Status:** planned
**Depends on:** 070
**Roadmap revision:** 38

> Planned from [`../ui-cohesion-proposal.md`](../ui-cohesion-proposal.md) §3.5, §3.7 and
> §3.8. **Accepted by the owner as DEC-136.** Renumbered from 072 to 071 — see
> `070-one-surface.md`'s own note and DEC-136.

## Objective

Apply the two insights rules that need data rather than paint: a count that is a
proportion is drawn as one, a row carries the faces of what it counted, and a filtered
screen says what it is filtered by. The shelves screen becomes a ranking you can open;
the library says what it is showing.

## Required context

- [`../ui-cohesion-proposal.md`](../ui-cohesion-proposal.md) §1 rules 2, 3 and 4; §2
  findings 5, 6 and 11; §3.5, §3.7, §3.8; §6 (the join is measured, not assumed).
- [`070-one-surface.md`](070-one-surface.md) — the primitives this sprint builds on. Read
  what actually shipped.
- `docs/decisions.md` DEC-134 (the covers-on-a-ranking-row work: the lateral top-3 join
  and **its measured cost** — this sprint repeats that join on a much smaller list),
  DEC-133 (`magnitude`, the bar, and the one-row-open disclosure), DEC-131 (the insights
  query budget), DEC-026 (tokens).
- Code, read fresh: `frontend/src/pages/ShelvesPage.tsx:150-215` (the rows, the count at
  `:193-197`), `frontend/src/features/library/InsightsRanking.tsx` (the bar, the
  `CoverStack`, the disclosure — reused, not re-derived),
  `frontend/src/features/library/insights.ts` (`magnitude`),
  `frontend/src/pages/HomePage.tsx:748-757` and `:978-1002` (`InsightFilterChip`, and the
  `filtersFromParams`/`paramsFromFilters` pair it clears through),
  `frontend/src/api/shelves.ts` (`ShelfWithCount`),
  `backend/src/book_tracker/api/library.py:69-73` (`ShelfResponse`) and `:1078-1080`,
  `backend/src/book_tracker/application/library.py:575-588` (`list_shelves`, the existing
  count subquery) and the insights covers join DEC-134 added.
- Tests: `frontend/src/pages/ShelvesPage.test.tsx`, `HomePage.test.tsx`,
  `backend/tests/test_library_api.py`, `test_library_queries.py`,
  `scripts/benchmark_library.py`.

## Current implementation baseline

- A shelf row is a name, a plain-text count, *Rename* and *Delete*. Nothing links to
  `/?shelf=slug`, which the library supports perfectly well — the one screen about shelves
  is the one place a shelf is a dead end.
- `list_shelves` answers from `ShelfRow` plus one count subquery. No covers.
- `InsightFilterChip` names the insights `key`/`value` filter and clears it. Shelf, format,
  status and the search query are states inside select triggers, and a library narrowed to
  eleven rows explains itself only if you open three controls.
- The import preview's summary line is three numbers at identical weight.

## Deliverables

1. **`ShelfResponse.covers`** (and `ShelfWithCount.covers` on the client) — up to three
   cover URLs per shelf, from the same lateral top-3 join DEC-134 already built and
   benchmarked for insights. **The only backend change in this line.**
2. **A shelf row is a ranking row**: a magnitude bar for its share of the largest shelf,
   up to three covers of what is on it, the count, and the name as a link into
   `/?shelf=slug`. *Rename* and *Delete* stay exactly where they are.
3. **The bar and the cover stack are the ones already built** — `magnitude` and
   `CoverStack` from the insights feature, reused rather than re-derived. If they need
   generalizing to be reusable, that generalization is the deliverable.
4. **An active-filters row on the library**: one dismissable chip per set filter — shelf,
   format, status, query, insights key — generalized from `InsightFilterChip`, clearing
   through the same `paramsFromFilters` path. The selects keep their state; the chips are
   what makes a narrowed library legible.
5. **Counts carry weight** wherever a set of counts describes one whole: shelf sizes,
   status facets, and the import preview's `N ready · N need a choice · N have errors`.
6. **Measured, not assumed.** The shelves query is benchmarked before and after, on a
   library with the shelf count and entry count the benchmark script can produce, and the
   numbers go in the outcome.

## Acceptance criteria

1. A shelf row links into the library filtered to that shelf, and the library arrives
   showing it.
2. Two shelves holding 30 and 10 entries render bars whose widths differ in the same
   proportion; the count remains text, and the bar is decorative to assistive technology.
3. A shelf with entries shows up to three covers; a shelf whose entries have no covers
   shows the shared placeholder, not a gap; an empty shelf shows neither and says it is
   empty.
4. A library filtered by shelf, format, status or query shows a chip naming each filter;
   dismissing one clears exactly that filter and leaves the others set.
5. The insights breadcrumb keeps working and is one chip among the others, not a second
   idiom.
6. `GET /api/shelves` stays inside its budget with covers added, measured on a seeded
   library; the numbers are in the outcome and in a decision record if they are
   surprising.
7. The shelves screen and the library hold at 390px with no horizontal body scroll and
   44px targets; zero serious axe violations on both.
8. **The existing suites pass unchanged**, except where a test asserts finding 5, 6 or 11
   — each named in the outcome.

## Required tests (TDD)

| Behavior | Layer | File |
|---|---|---|
| `list_shelves` returns up to three covers per shelf, empty when none | integration | `test_library_queries.py` |
| `GET /api/shelves` carries `covers` in its schema | api | `test_library_api.py` |
| A shelf row links to `/?shelf=slug` | component | `ShelvesPage.test.tsx` |
| Bar width proportional to shelf size; bar is aria-hidden | component | `ShelvesPage.test.tsx` |
| Covers, placeholder and empty shelf all render distinctly | component | `ShelvesPage.test.tsx` |
| One chip per set filter; dismissing one keeps the others | component | `HomePage.test.tsx` |
| The insights breadcrumb is one of those chips | component | `HomePage.test.tsx` |
| Preview summary counts carry visible weight | component | `ImportPage.test.tsx` |
| Shelves and library at 390px, no horizontal body scroll | e2e | `frontend/e2e/library.spec.ts` |
| No serious violations on shelves and a filtered library | e2e | `frontend/e2e/accessibility.spec.ts` |

## Verification

- `make check`, `make test`, `python scripts/validate_project.py`
- The exhaustive backend suite; `openapi.json` regenerated for the new field.
- `npx playwright test` — owed.
- `python scripts/benchmark_library.py` before and after, for the shelves path.
- **Walkthrough (DEC-025):** against real imported data, open the shelves screen, follow a
  shelf into the library, narrow it with two more filters, drop one chip, and report what
  the shelves screen actually looked like with the owner's real shelves and covers.

## Explicit non-scope

- Everything Sprint 070 owns: the primitives, the covers on detail, the import preview's
  language, the 390px strip.
- Shelf reordering, nesting, colours or icons. A shelf is a name and a set.
- New library filters. The chips name the filters that exist.
- Cross-domain rankings, entity pages, time series — still the insights proposal's §5.
- Filtered export. It is the export proposal's §5 and stays there.

## Commit checkpoints

1. `[ADD] Tell the shelves list what is on each shelf`
2. `[MOD] A shelf you can open, at the size it actually is`
3. `[MOD] Say what the library is filtered by, whichever filter it is`
4. `[MOD] Give a count the weight it has`

## Risks and decisions to surface

- **A join on a request that answers from one table.** Small — tens of rows — but it is a
  backend change with a benchmark precedent, and DEC-134 measured the same join rather
  than assuming it. Do the same.
- **Chips can crowd the library header at 390px** where four filters are set. Decide
  whether they wrap or scroll, and measure it; the strip's answer in Sprint 070 is the
  precedent.
- **Covers on a shelf row invite a shelf detail page.** It is not in scope, and the library
  filtered by shelf is that page.
- **`ShelfWithCount` is used by `AddForm` and `ShelfPicker` too.** A new optional field is
  additive, but check both before assuming it.

## Outcome

_Not started._
