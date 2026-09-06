# Sprint 073 — Insights with a shape

**Status:** completed
**Depends on:** 072
**Roadmap revision:** 39

> Planned from [`../readability-proposal.md`](../readability-proposal.md) §1.2, §2 rule 11 and
> §3.2. **Accepted by the owner as DEC-139.**

## Objective

The insights page stops saying one thing twice in one idiom. The leading key becomes a hero that
carries its own superlatives, time is drawn in time order, the score distribution is drawn at all,
and the keys that were a grey footnote get cards sized by how much they have to say.

## Required context

- [`../readability-proposal.md`](../readability-proposal.md) §1.2 findings 8–13, §2 rule 11,
  §3.2, §5.2 (a charting library was priced and rejected), §7.
- [`../insights-redesign-proposal.md`](../insights-redesign-proposal.md) and `docs/decisions.md`
  **DEC-132** — the rules Sprints 066/067 established. Two survive unchanged and constrain this
  sprint: superlatives are drawn from the **leading key alone** (pooling every key answered
  "Fiction", true and useless), and a notice lives inside the thing it describes.
- `docs/decisions.md` DEC-131 (the insights query budget and its per-request temp table),
  DEC-134 (the covers join and its measurement), DEC-133 (`magnitude`, the one-row-open
  disclosure), DEC-026 (the ramp), DEC-052 and DEC-077 (no cross-domain identity — still out).
- Code, read fresh: `frontend/src/pages/InsightsPage.tsx` (all of it),
  `frontend/src/features/library/insights.ts` (`orderKeys`, `computeSuperlatives`, `quietSummary`,
  `magnitude`), `InsightsCard.tsx`, `InsightsRanking.tsx`, `SuperlativeStrip.tsx`,
  `useInsights.ts`, `frontend/src/lib/score.ts` (`meanScoreChipClass`, `scoreChipShape`),
  `backend/src/book_tracker/api/library.py:450-480` (the insights route),
  `backend/src/book_tracker/application/library.py` (`rank`, `_filtered_entries`, the facets block
  at `:875-950` — the shape the new count reuses).
- Tests: `frontend/src/features/library/insights.test.ts`, `frontend/src/pages/InsightsPage.test.tsx`,
  `frontend/e2e/insights.spec.ts`, `backend/tests/test_library_api.py`,
  `backend/tests/test_library_queries.py`, `scripts/benchmark_library.py`.

## Current implementation baseline

Measured 2026-09-05 against the owner's running instance at 1440×1100:

- Two cards are on screen: **Decade** and **Year**. They rank the same field at two grains — the
  Decade rows (2000s 6, 2010s 5, 1960s 3) are the Year rows added up.
- The superlative strip says *Holds the most: 2000s, 6 entries* directly above a row reading
  *2000s 6*; two of its three tiles named `2000s`.
- Every fact on the page is a horizontal amber bar with a count and a mean chip. There is no
  distribution and no time axis; decades are sorted by count, which destroys their only
  meaningful order.
- Creators, Series, Publisher, Subjects and Language are in the "Nothing much to rank yet"
  footnote, on a library whose two most concentrated facts are *Brandon Sanderson 5* and
  *Mistborn 5*.
- The page is `max-w-5xl` — 416px of margin at 1440 — and everything below y≈995 is empty.

## Deliverables

1. **The hero panel.** The leading key (`orderKeys`' first carded entry) is drawn full width with
   its top row promoted: a ~96px poster, the label, the count, the mean chip — and the three
   superlatives folded **inside** it, which is how finding 9's repetition ends without reopening
   DEC-132's leading-key rule.
2. **One card for a key and its rollup.** Decade and Year become a single card with a grain
   toggle. The rule is general, not a special case: where one key's values are a coarsening of
   another's, one card carries both grains.
3. **The chronology strip.** Decades in chronological order, bar height by count, fill by the
   mean's ramp band, an empty decade drawn as a gap rather than skipped. Derived on the client
   from rows the page already has — **no backend work in this deliverable**.
4. **The score distribution.** A new read-only endpoint returning per-score counts for a domain
   under the same filters `rank()` already honours, drawn as ten bars in the ramp with the
   unrated tail stated in words. This is the only backend change in the sprint.
5. **An asymmetric grid.** 12 columns at `xl`: hero at 12, then 8/4 and 4/4/4 by `orderKeys`
   rank, so a fifteen-value ranking is not the same size as a three-value one. The page width
   matches the library's.
6. **The long tail becomes a card.** "16 subjects appear once" as clickable values into the
   filtered library, replacing the grey footnote.
7. **Budget measured, not assumed.** DEC-131's benchmark runs before and after; the new endpoint
   gets its own scenario and its numbers go in the Outcome.

## Acceptance criteria

1. No key's values appear in two cards. Decade and Year are one card; switching grain does not
   refetch a ranking the page already holds unless the grain genuinely needs one.
2. The chronology strip renders its buckets in ascending time order, includes a bucket with zero
   count as a gap, and its fill colour is the band of that bucket's mean (no mean → the neutral
   surface, not a ramp colour).
3. The superlatives appear exactly once on the page, inside the hero, and still come from the
   leading key alone.
4. The score distribution's bars sum to the rated count; the unrated count is stated in words;
   an all-unrated library renders the panel with a stated zero rather than an empty box.
5. The new endpoint honours `type`, `statuses`, `shelves`, `formats` and `q` exactly as `rank()`
   does, and returns 422 on an unknown type the same way.
6. Cards are sized by rank: the hero spans the grid, and no two cards below it have the same span
   unless their rank tier is the same.
7. A long-tail value opens the library filtered to it, arriving with the chip that names the
   filter.
8. `/insights` holds at 390px with no horizontal body scroll and 44px targets; zero serious axe
   violations with a row expanded and the grain toggle used.
9. The insights query budget (DEC-131) is not regressed by the new endpoint; before/after numbers
   are in the Outcome.
10. Existing suites pass unchanged except where a test asserts findings 8–13; each named in the
    Outcome.

## Required tests (TDD)

| Behavior | Layer | File |
|---|---|---|
| Per-score counts respect type and each of the four filters | integration | `test_library_queries.py` |
| The score endpoint's schema, and 422 on an unknown type | api | `test_library_api.py` |
| A rollup key and its fine grain resolve to one card | unit | `insights.test.ts` |
| Chronological bucket order, zero buckets kept, band from the mean | unit | `insights.test.ts` |
| The hero renders the leading key with its superlatives inside it | component | `InsightsPage.test.tsx` |
| Superlatives appear once on the page | component | `InsightsPage.test.tsx` |
| Distribution bars sum to rated; unrated stated; all-unrated renders | component | `InsightsPage.test.tsx` |
| A long-tail value links into the filtered library | component | `InsightsPage.test.tsx` |
| 390px, no horizontal scroll, grain toggle exercised | e2e | `insights.spec.ts` |
| Zero serious violations with a row expanded | e2e | `accessibility.spec.ts` |

## Verification

- `make check`, `make test`, `python scripts/validate_project.py`.
- `python scripts/export_openapi.py` regenerated for the new route; `npm run api:check`.
- `npx playwright test`.
- `python scripts/benchmark_library.py` before and after, including the new scenario. Note the
  standing observation in `HANDOFF.md`: the `insights` ranking scenarios already exceed their
  budget under the contended condition on this workstation. Re-measure before assuming it is
  still true, and do not attribute a pre-existing number to this sprint's diff.
- **Walkthrough (DEC-025):** against a throwaway seeded backend that has a library with a real
  spread of years and scores, at 390 and at desktop width. Report whether the chronology reads as
  time and whether the hero stops the page repeating itself.

## Explicit non-scope

- Cross-domain rankings, entity pages, a creator identity (DEC-052, DEC-077).
- A charting library, or any new dependency (§5.2; DEC-037 pinned the chunk budget).
- Time series over `date_finished` ("what I read this year"). Tempting beside a chronology strip;
  it is a different question and a different query, and it is not in this proposal.
- The library (Sprint 072) and shelves (Sprint 074).

## Commit checkpoints

1. `[ADD] Count the scores a library actually holds`
2. `[MOD] One card per fact, at two grains`
3. `[ADD] Draw time in time order`
4. `[ADD] Show how you rate`
5. `[MOD] Size a card by how much it has to say`

## Risks and decisions to surface

- **The rollup rule needs a definition, not a hard-coded pair.** "Decade is Year coarsened" must
  be declared or derived, or the next domain's keys reintroduce the duplicate. Decide where that
  declaration lives — the domain's field spec is the obvious candidate — and record it.
- **A new endpoint on a budgeted query path.** DEC-131 exists because this budget was breached
  once. Measure.
- **Two encodings on one mark.** The chronology bar carries count in height and score in fill.
  That is defensible only because the ramp already means score everywhere; if it reads as
  decoration in the walkthrough, drop the fill rather than inventing a second scale.
- **An empty decade is data.** A gap says "nothing from the seventies"; skipping the bucket says
  the seventies do not exist. Keep the gap.

## Outcome

Delivered as planned. One backend addition (deliverable 4); everything else is frontend.

### Backend

- `LibraryService.score_distribution()` (`backend/src/book_tracker/application/library.py`) —
  a `GROUP BY score` over the same `_filtered_entries` set `rank()` ranks, returning ten
  per-score counts plus the rated/unrated totals. `GET /api/insights/scores`
  (`backend/src/book_tracker/api/library.py`) exposes it, typed `type: ItemTypeName` exactly
  as `/api/insights` is, so an unknown domain is a 422 through the same mechanism (AC5).
  Tests: `test_library_queries.py` (counts, unrated tail, and each of type/status/shelf/format/q
  narrowing it independently) and `test_insights_api.py` (schema over HTTP, 422 on an unknown
  type, 422 on an invalid status filter — mirroring `/api/insights`'s own refusal).

### Frontend

1. **The hero panel** (`InsightsCard.tsx`'s new `hero` prop) — the leading key's top row (by
   whichever order is active) drawn large — cover, label, count, mean chip — with the three
   superlatives folded inside via a reused `SuperlativeStrip`, which no longer sits in its own
   page-level section. `ChronologyCard` gained the identical `hero` prop: the chronology card
   earns the lead as often as any other key (it did in the walkthrough's own library), and AC3
   does not carve out an exception for it.
2. **One card for a key and its rollup.** `labels.ts`'s `InsightKeyOption` gained an optional
   `grain` field — a declared rollup (`{ name: "decade", grain: { name: "year", ... } }`) rather
   than a hard-coded pair, satisfying the sprint's own risk note about where that declaration
   should live. `insights.ts`'s `resolveAnsweredKeys` pairs a rollup's coarse and fine grain into
   one answered entry; `ChronologyCard` renders the toggle and both views client-side from
   rankings the page already fetched (AC1 — no second request on toggle).
3. **The chronology strip** (`ChronologyStrip.tsx`, `insights.ts`'s `chronologyBuckets`) — decades
   in ascending time order, a zero-count decade kept as a gap, fill by the mean's ramp band, no
   mean drawn as the neutral surface. Entirely client-derived from the `decade` ranking already
   on the page; no backend change, as specified.
4. **The score distribution** (`ScoreDistributionCard.tsx`, `useScoreDistribution.ts`) — ten bars
   in the ramp, the unrated tail stated in words, an all-unrated library still renders the panel
   with a stated `0 rated` rather than an empty box.
5. **An asymmetric grid** — `insights.ts`'s `insightGridSpan` gives the first card after the hero
   8 of 12 columns, everything after it 4, at `xl`. The page container is `max-w-[1600px]`,
   matching the library's (Sprint 072).
6. **The long tail as a card** (`LongTailCard.tsx`) — a quiet key's whole ranking as clickable
   chips into the filtered library, replacing the "Nothing much to rank yet" footnote entirely.
7. **Budget re-measured.** `scripts/benchmark_library.py` gained the `scores` scenario. Measured
   this session at 5,000 entries, 100 contended jobs: `insights scores` p50 2.7ms / p95 2.8ms /
   max 2.9ms — negligible next to the budget, and the existing `creators`/`publisher`/`year`/
   `decade` scenarios were re-measured alongside it with no regression (`creators/count` p95
   299.2ms, `publisher/count` p95 372.7ms, both already the shape DEC-131 accepted). `VERDICT:
   every scenario is within budget.`

### Acceptance criteria

1. No key's values in two cards; Decade/Year is one card; toggling costs no refetch — held
   (`insights.test.ts`'s `resolveAnsweredKeys` tests, `InsightsPage.test.tsx`'s grain-toggle test
   asserting the request count is unchanged after toggling).
2. Chronology strip in ascending order, zero-count bucket kept as a gap, fill from the bucket's
   own mean band — held (`insights.test.ts`'s `chronologyBuckets` tests).
3. Superlatives appear exactly once, inside the hero, from the leading key alone — held
   (`InsightsPage.test.tsx` asserts exactly one `[data-insight-hero]` and exactly one instance
   each of "Holds the most"/"Highest rated"/"Steadiest" on the page).
4. Distribution bars sum to the rated count; unrated stated; all-unrated renders a stated zero —
   held (`InsightsPage.test.tsx`).
5. The new endpoint honours `type`/`statuses`/`shelves`/`formats`/`q` exactly as `rank()` does,
   422 on an unknown type — held (`test_library_queries.py`, `test_insights_api.py`).
6. Cards sized by rank; the hero spans the grid; no two cards below it share a span unless the
   same rank tier — held (`insightGridSpan`'s 8/4/4/4… pattern, asserted in `insights.test.ts`
   and visible in the walkthrough screenshots).
7. A long-tail value opens the library filtered to it, with the naming chip — held
   (`InsightsPage.test.tsx`'s long-tail link test).
8. `/insights` holds at 390px, no horizontal scroll, 44px targets, zero serious axe violations
   with a row expanded and the grain toggle used — held (`insights.spec.ts`'s phone-fit test now
   exercises the grain toggle and re-checks overflow after it; `accessibility.spec.ts`'s existing
   insights axe checks pass unchanged).
9. The insights query budget is not regressed — held, numbers above.
10. Existing suites pass unchanged except where a test asserts findings 8-13 — held. Changed,
    all anticipated by this sprint's own redesign:
    - `InsightsPage.test.tsx`: the opening test's `cardTitles`/quiet-line assertions (Decade/Year
      merge, footnote replaced by a long-tail card); duplicate-text assertions for the hero's
      promoted row switched to `getAllByText` (the same fact now legitimately appears twice —
      once promoted, once in the ordinary list); the insights-call count assertion updated for
      the added `language` fixture key and the one new score-distribution request.
    - `insights.spec.ts` / `accessibility.spec.ts`: both insight fixtures needed an
      `/api/insights/scores` stub (registered after the broader `/api/insights` route, so
      Playwright's most-recently-registered-wins rule gives it the match) and a decade-row `key`
      fix (`"1960"`, not `"1960s"` — the label, not the key, since `chronologyBuckets` reads it
      as a number). Neither is a finding-8-13 assertion changing meaning; both are fixture bugs
      the new coverage surfaced immediately, fixed before they could hide behind a stub that
      happened not to need the field before.

### Deviation found and fixed mid-sprint, not left for the Outcome to merely note

The first walkthrough render (real data, not a fixture) showed the hero rendering with no
superlatives at all when the *chronology* card was the leading key — `renderRankedCard`'s hero
flag reached `InsightsCard` but `ChronologyCard` had no hero mode to receive it. This is exactly
the scenario the walkthrough gate exists to catch: every unit and component test passed with
fixtures that happened to keep Authors in the lead. Fixed by giving `ChronologyCard` the same
promoted-top-row-plus-superlatives treatment `InsightsCard` has, computed from the decade
ranking regardless of which grain is currently displayed. Re-verified in a second walkthrough
render (screenshots below).

A second, smaller readability issue surfaced in the same walkthrough: the three superlative
tiles at 390px squeezed into one row truncated both the label ("2000s" to "2...") and wrapped
the title mid-word. `SuperlativeStrip` now stacks one tile per row below `sm` and switched its
tile background to `bg-surface-raised` so it reads as a distinct surface against the card's own
`bg-surface` rather than blending into it.

### Verification

- `make check`, `make test` (backend 1361, frontend 291) — green.
- `python scripts/export_openapi.py` regenerated for the new route; `npm run api:check` — green.
- `npx playwright test` — 124 passed, 2 skipped, 0 failed on the clean run. One run in between
  showed `accessibility.spec.ts`'s "the degraded provider notice" failing under parallel load —
  confirmed a rerun of the known, pre-existing, unrelated-file timing sample (2/2 passed in
  isolation both times), not a regression; not weakened or skipped.
- `python scripts/benchmark_library.py --entries 5000 --jobs 100` before and after — numbers
  above.
- Walkthrough (DEC-025): a throwaway backend (`scripts/walkthrough.py`), seeded via the real API
  with 20 books across 12 creators spanning 1951-2019 (all seven decades in that span actually
  held — the seed did not happen to produce a gap decade, so `chronologyBuckets`' zero-count
  path is proven only by its unit tests, not by this walkthrough) and scores across the full
  1-10 range plus two unrated. Driven with Playwright at 1440×1000 and 390×844: zero horizontal
  overflow at either width, zero console/page errors, the grain toggle exercised and reverted
  cleanly. The hero (Decade, in this library — its lead beat Creators') showed its promoted top
  row and all three superlatives; the chronology strip drew all seven decades in time order;
  the score distribution's bars matched the seeded spread with the unrated count stated;
  Creators/Publisher sat 8/4 and Language/Subjects/Series sat 4/4/4, as specified. The fixes
  above were both found and repaired during this walkthrough, not after it.
