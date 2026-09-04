# Sprint 067 — Insights with faces

**Status:** completed
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

**Delivered.** All six deliverables and acceptance criteria 1–8 are built and tested, with one
corrected reading of this sprint's own text along the way — **DEC-134**.

- **Deliverable 1 (covers) and AC1/AC2, corrected.** The sprint text gated `covers` on a
  domain's `chooses_covers`, which is `False` for every shipped domain but book even though
  album, anime, movie and series entries all carry real cover art — that flag is the manual
  Open Library cover-picker (DEC-067 row 7), not a claim about whether a domain has covers at
  all. Raised to the owner before building (it would have shipped covers for exactly one
  domain) and built the corrected way: `LibraryService._insight_covers` selects up to three
  members per row whose item actually has `cover_path`, ordered by score desc, then
  `date_added` desc, then entry id desc — the same three on a repeat request (AC1), empty only
  when no member has a cover (AC2), regardless of domain. `InsightRowResponse.covers: list[str]`.
- **Deliverable 2 (library totals), AC3.** `InsightResponse.total_entries`/`rated_entries` —
  the ranked set's own totals from `_filtered_entries`, computed once per `rank()` call and
  independent of `key`, not a sum of rows (which over-counts a many-valued key: a book with two
  creators is two rows under `creators`).
- **Deliverable 3 (the superlative strip), AC4.** `computeSuperlatives` in
  `features/library/insights.ts`, drawn from the leading key alone (the same key `orderKeys`
  already picked): most collected (the count leader), highest rated (best mean meeting
  `min_rated`), steadiest (lowest `score_spread` among those with one — which needs two ratings
  to exist at all). A superlative with no honest answer is left off rather than guessed at.
  Rendered by `SuperlativeStrip.tsx`, with the library-totals line ("N of your M are rated").
- **Deliverable 4 (covers on the row), AC8.** `InsightsRanking.tsx`'s `CoverStack` draws up to
  three from `row.covers` beside the collapsed row's label, through `CoverImage`; the expanded
  member list already drew full covers per entry since Sprint 066's `InsightsMembers`, needing
  no change. Both render from the one ranking response the counts come from, so nothing about
  a cover holds up a row's numbers — proved in `InsightsPage.test.tsx` by asserting the count
  and score chip are visible while the cover `<img>` is still at `opacity-0` (jsdom never fires
  `load`).
- **Deliverable 5 (filter passthrough), AC5/AC6.** `GET /api/insights` gains
  `status`/`shelf`/`format`/`q`, validated by the same `EntryStatus`/`EntryFormat` enums
  `/api/entries` uses, forwarded to `rank()`'s existing `statuses`/`shelves`/`formats`/`q`
  parameters. An invalid value is refused identically (422); a status filter's row counts agree
  with `/api/entries` over the same filters plus `key`/`value`.
- **Deliverable 6 ("within my current filters").** Off by default. `HomePage` writes its
  status/shelf/format/query filters to `localStorage` (`rememberLibraryFilters`) on every
  change, the same pattern the remembered domain already uses; `InsightsPage` reads that
  snapshot once and, when the toggle is on, forwards it through `useInsights`. States in words
  which filters are applied, or says plainly the library has none set, rather than leaving a
  narrower ranking unexplained.

- **AC7, re-measured.** `scripts/benchmark_library.py`'s seed set `cover_path=None` on every
  item, which would have measured the covers query against an always-empty join — corrected to
  give twelve items in thirteen a cover. At 5,000 entries under write contention:
  `creators/count` 294.2ms p95 (277.8ms without covers, DEC-133), `creators/score` 307.9ms,
  `publisher/count` 365.9ms (208.3ms before — the largest jump, still well inside budget),
  `year`/`decade` unaffected. Every scenario stays inside the 500ms budget.

- **Verification.** `make check` green. Backend **1,333** passed (1,328 + 5 new:
  `test_covers_come_from_the_rows_own_members_deterministically_ordered`,
  `test_a_ranking_row_with_no_covered_members_returns_an_empty_list`,
  `test_total_entries_and_rated_entries_honour_the_ranked_sets_filters` in `test_insights.py`;
  `test_a_status_filter_narrows_a_ranking_and_agrees_with_entries`,
  `test_an_invalid_status_filter_is_refused_as_entries_refuses_it` in `test_insights_api.py`).
  Frontend **243** passed (231 + 12: 4 `computeSuperlatives` unit tests in `insights.test.ts`,
  5 new `InsightsPage` component tests — the superlative strip's three-and-fewer cases, covers
  rendering before load, the remembered-filters toggle in both states — 3 remembered-filters
  unit tests in `library.test.ts`). Full Playwright:
  **113 passed, 2 skipped, 0 failed**, including the updated `insights.spec.ts` and
  `accessibility.spec.ts` axe checks with the new strip and cover stack in the tree.
  `python scripts/validate_project.py` green. `make smoke-container` not owed — the diff adds
  no deployment configuration.

- **Walkthrough (DEC-025), done.** A throwaway backend (`scripts/walkthrough.py`) on an
  ephemeral port against a fresh `/tmp` data directory, seeded through the real HTTP API: 12
  books and 13 albums with real creators, scores and statuses, a real image uploaded through
  `POST /api/items/{id}/cover` to all but two entries per domain, left uncovered on purpose.
  Verified first over HTTP (covers, totals, filter narrowing, suppression all correct against
  hand-computed expectations), then in a real browser — a dev frontend on `:5180` proxied at
  the throwaway backend (`AKASHA_E2E_BACKEND`). Covers rendered on **both** the book and the
  **album** domain (`chooses_covers=False`), with counts matching each row's actual covered
  membership exactly; the deliberately uncovered book row showed no cover slot; the superlative
  strip named three different rows plus the library-totals line; the filters toggle was off by
  default, said the library had no filters set until one was written to the remembered key,
  then named it and the following request carried `status=read`; zero console errors
  throughout. The owner's own instance at `:8000` was untouched; the throwaway backend,
  frontend and data directory were torn down at close.

  **One defect found, out of scope, not fixed:** at 390px the domain radiogroup (five real
  domains) overflows the viewport by about 39px. `InsightsPage.tsx`'s header markup is
  unchanged since Sprint 066's close (diffed to confirm); it was never exercised at more than
  one or two domains by either sprint's own mocked component/e2e tests, which is why AC9's
  390px check stayed green through both. Recorded rather than fixed — full account in
  **DEC-134**.

- **Deviations, all in DEC-134:** the corrected covers gate (above); the AC7 seed fix (above);
  the out-of-scope radiogroup overflow (above, carried forward, not this sprint's to fix).

- **Commits (five, not the sprint doc's planned four 1:1 — deliverable 2 landed with deliverable
  1 rather than as its own commit, since both are additions to the same `rank()` response pass,
  and deliverable 5's backend and frontend halves are two commits that ended up sharing a
  title):**
  1. `bedd3aa` `[ADD] A ranking row carries the covers behind its number` — covers + library
     totals (deliverables 1–2).
  2. `d61316d` `[ADD] Rank inside the filters you already set` — the backend filter passthrough
     (deliverable 5's route).
  3. `8255778` `[ADD] The three things worth saying about a domain` — the superlative strip and
     row covers (deliverables 3–4).
  4. `bb26a1a` `[ADD] Rank inside the filters you already set` — the frontend toggle
     (deliverable 5's UI, deliverable 6). Same title as commit 2 by oversight; different diff.
  5. `1000cfe` `[TEST] Hold Sprint 067 to a real budget and a real browser` — the AC7 benchmark
     seed fix and the e2e/accessibility fixture updates.
