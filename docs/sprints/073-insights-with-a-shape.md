# Sprint 073 — Insights with a shape

**Status:** ready
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

_Not started._
