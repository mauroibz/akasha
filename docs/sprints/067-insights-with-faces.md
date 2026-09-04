# Sprint 067 — Insights with faces

**Status:** planned
**Depends on:** 066
**Roadmap revision:** 36

> Planned from [`../insights-redesign-proposal.md`](../insights-redesign-proposal.md) and
> **accepted by the owner as DEC-132.** Activates when Sprint 066 closes.

## Objective

Give a ranking row a face and a context: the covers of the things behind the number, the
library totals a superlative needs to be a sentence, and the ability to rank inside the
filters you already have set.

## Required context

- [`../insights-redesign-proposal.md`](../insights-redesign-proposal.md) §2.7, §2.8 and §3 —
  what this sprint delivers and why the placement recommendation makes the filter passthrough
  cheap.
- [`066-insights-you-can-read.md`](066-insights-you-can-read.md) — the screen this lands on.
- [`065-insights.md`](065-insights.md) — the ranking query and its contract.
- `docs/decisions.md` DEC-131 (the query design and its measured budget — this sprint adds
  work to that query and must re-measure), DEC-067 row 7 (`chooses_covers`: not every domain
  has covers to show), DEC-062 (the library's remembered domain and how `type` interacts with
  facets).
- Code, read fresh: `application/library.py` `rank()`, `_insight_explode`, `_insight_row`,
  `_filtered_entries`; `api/library.py` `InsightRowResponse`/`InsightResponse` and the
  `/insights` route; `scripts/benchmark_library.py` `insights_scenarios()`;
  `frontend/src/components/CoverImage.tsx`.

## Current implementation baseline

- `rank()` **already accepts** `statuses`, `shelves`, `q` and `formats` and forwards them to
  `_filtered_entries`. `GET /api/insights` accepts none of them. The passthrough is four
  parameters and their validation, not new query work.
- `InsightRowResponse` carries no item reference of any kind. A row knows its normalized key,
  its label and three numbers.
- No endpoint reports how many entries in a domain carry a score. `/api/entries` returns
  `total` and `facets.status_counts`, neither of which is "rated".
- `CoverImage` already handles a null cover, a failed cover and the loading reveal, and
  `chooses_covers` already declares which domains have covers at all.
- `insights_scenarios()` in the benchmark exists and seeds a multi-creator shape — the harness
  this sprint's re-measurement needs is already there.

## Deliverables

1. **`InsightRowResponse.covers: list[str]`** — up to three cover URLs from the row's own
   members, chosen deterministically (highest scored first, then most recently added, then by
   id, so a repeat request returns the same three). Empty for a domain that declares
   `chooses_covers=False`, and empty rather than absent when members have no covers.
2. **Library totals on `InsightResponse`** — `total_entries` and `rated_entries` for the
   ranked set, so the superlative strip can say "7 of your 47" without a second request and
   without summing rows (which over-counts a many-valued key).
3. **The superlative strip** — most collected, highest rated, and steadiest from
   `score_spread`, drawn from the leading key. A superlative with no honest answer is not
   rendered.
4. **Covers on the row** — a stack of up to three in the collapsed row, full covers in the
   expanded member list, through `CoverImage` so the empty and failed states are the ones the
   rest of the application already uses.
5. **Filter passthrough on `GET /api/insights`** — `status`, `shelf`, `format` and `q`,
   validated as `/api/entries` validates them, forwarded to `rank()`.
6. **"Within my current filters"** — the Insights page offers ranking inside the library's
   remembered filters, off by default, saying in words which filters are applied.

## Acceptance criteria

1. A ranking row over a domain with covers returns up to three cover URLs belonging to
   entries that row actually counted; the same request twice returns the same three.
2. A domain declaring `chooses_covers=False` returns empty cover lists and the screen renders
   rows without a cover slot, not with an empty one.
3. `total_entries` and `rated_entries` describe the ranked set, and match the same filters the
   rows were computed under.
4. The superlative strip names three different things, or fewer when the library cannot
   support three, and never invents one.
5. `GET /api/insights?status=read&shelf=…` ranks only those entries, and the row counts equal
   what `/api/entries` returns for the same filters plus `key`/`value`.
6. An invalid filter value is refused the same way `/api/entries` refuses it.
7. **Performance:** the ranking with covers stays inside the budget DEC-131 set, measured
   through `scripts/benchmark_library.py` at 5,000 entries with the multi-creator seed — not
   asserted from a fixture, and re-measured rather than assumed unchanged.
8. Cover images never block the ranking: rows render with their numbers before any cover
   loads.

## Required tests (TDD)

| Behavior | Layer | File |
|---|---|---|
| Covers come from the row's own members, deterministically ordered | repository | `test_insights.py` |
| A `chooses_covers=False` domain returns empty cover lists | repository | `test_insights.py` |
| `total_entries`/`rated_entries` honour the same filters as the rows | repository | `test_insights.py` |
| Filter passthrough narrows a ranking; counts agree with `/api/entries` | api | `test_insights_api.py` |
| An invalid filter value is refused as `/api/entries` refuses it | api | `test_insights_api.py` |
| The superlative strip renders three, and fewer when it must | component | `InsightsPage.test.tsx` |
| Rows render before covers resolve | component | `InsightsPage.test.tsx` |
| The ranking with covers at 5,000 entries stays inside budget | benchmark | `scripts/benchmark_library.py` |

## Verification

- `make check`, `make test`, `make smoke-container`, `python scripts/validate_project.py`
- `npx playwright test`
- `scripts/benchmark_library.py` — the AC7 re-measurement, reported with its numbers, not its
  verdict.
- **Walkthrough (DEC-025):** the full redesigned screen against real imported data across
  every domain, including a domain without covers.

## Explicit non-scope

- Everything Sprint 066 delivers.
- The proposal's §5 list, unchanged: cross-domain rankings, entity pages, time series, new
  metrics, grouping by entry fields.
- Making Insights a library view mode. §3 of the proposal costs it and recommends against it;
  deliverable 6 is the part of its value that is cheap.
- Caching covers, resizing them, or any new image pipeline. Existing cover URLs only.

## Commit checkpoints

1. `[ADD] A ranking row carries the covers behind its number`
2. `[ADD] Say how much of the library a ranking is ranking`
3. `[ADD] The three things worth saying about a domain`
4. `[ADD] Rank inside the filters you already set`

## Risks and decisions to surface

- **The lateral top-3 is new work inside a query DEC-131 already had to repair once.** AC7
  exists because that budget was breached before, under write contention, and was fixed with a
  per-request temp table. Re-measure; if covers push it out, the fallback is to fetch them for
  visible rows only, on a second request, and that is a design change worth surfacing rather
  than absorbing.
- **"Rated" needs defining once.** `rated_entries` counts entries with a non-null score,
  including provisional ones carried from an import. Whether a provisional score should count
  is a product question and belongs to the owner, not to the query.
- **Deterministic cover choice matters more than it looks.** Three covers that reshuffle
  between renders read as a bug, which is why AC1 pins the ordering rather than leaving it to
  the planner.

## Outcome

_Not started._
