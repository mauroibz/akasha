# Sprint 102 — Insights, read back to you

**Sprint:** 102
**Status:** completed
**Roadmap revision:** 46
**Depends on:** 101
**Owner:** Mauro

## Objective

The Insights page reads the library back as prose with character: one lead sentence carrying the
figures that matter, then numbered sections divided by rules instead of boxes, each a sentence
and a chart no bigger than its data. Sizing is uneven on purpose: big serif numerals, real covers,
small supporting text. This is the canvas the owner approved (DEC-169).

## Required context

- DEC-169; DEC-132 and DEC-139 (the earlier insights decisions this page replaces the look of,
  not the data); DEC-167.
- The canvas: https://claude.ai/artifact/6vt1GZ5nBi5zYq67ibZh3c, boards *Insights, redrawn —
  desktop* and *Insights — phone*.
- `frontend/src/pages/InsightsPage.tsx`, `features/library/{InsightsCard,LongTailCard,
  ScoreDistributionCard,ChronologyCard,insights,useInsights,useScoreDistribution}.ts(x)`,
  `application/library.py` (`rank`, `score_distribution`, `_insight_explode`, `_insight_labels`).

## Current implementation baseline

One card per declared key in a responsive grid, a full-width score histogram, chip clouds for the
long tail, a domain strip and a sort control. Subjects list provider variants separately
(*Fiction*, *Fiction / General*). One book's language is `{'` and shows as a chip.

## Deliverables

1. `GET /api/insights/summary?type=` (same filters as `/api/insights`): held, finished (entries
   with a finish date), rated, unrated, the modal score, and the earliest-dated item's title and
   year. Domain-agnostic: no branch on item type.
2. Subject folding in the ranking: case, surrounding whitespace and a trailing generic qualifier
   (`, general`, `/ General`) fold into one row; its label is the commonest plain spelling.
3. A grouping value with no letters or digits (`{'`) is not counted under any key.
4. The page: domain tabs as text, the lead sentence, numbered sections (rating, the top key as a
   ranked list with fanned covers and score chips, subjects typeset by weight, the chronology key,
   a single proportional bar for a key with few values such as language, and the remaining keys
   as one line each with "and N more"). Charts are compact (at most about 80px tall). Phone
   width is one column with the same order.
5. The old card components the page no longer uses are deleted with their tests.

## Acceptance criteria

1. The summary endpoint returns correct figures for a seeded library and respects filters.
2. "Fiction", "Fiction, general" and "FICTION / General" rank as one row of three.
3. A punctuation-only grouping value never appears as a row.
4. The page renders the lead sentence and sections for every domain, in both themes, with no
   boxed cards; each subject and ranked row still opens the library filtered to it.
5. The accessibility spec passes on the page.

## Verification

Per DEC-167: the insights backend tests, the route-structure tests, `vitest related`, `make
check`, the insights and accessibility specs, and screenshots of the page in Paper, Ink and at
390px.

## Outcome

Delivered 2026-10-21. Verified per DEC-167: `test_insights_read_back.py` (4), the insights,
library, isolation, app-shape, error-envelope, item-type, conformance and domain suites (358),
`vitest related` (260), `make check`, the insights, accessibility and library specs (55), and the
page in the running app on a copy of the owner's library (the board's 2026-10-21 backup) in
Paper, Ink and at 390px.

- **AC1.** `GET /api/insights/summary`: held, finished (a finish date, as the Diary counts),
  rated, unrated, the modal score (a tie goes up), the earliest-dated item; filters as every
  insight. Route-structure and isolation tests updated.
- **AC2.** Rankings group through a new SQLite function, `insight_group`: `normalize_text` plus a
  trailing " general" folded into its head. The label prefers a spelling without the qualifier.
  The library's `key`/`value` filter matches the same way, so the folded row opens all three.
- **AC3.** A value with no letters or digits groups to nothing and is not a row: the owner's
  `{'` language is gone from Insights.
- **AC4.** The page: domain tabs as text, a lead sentence, then numbered sections divided by
  rules. Rating: the usual score in 7–9rem serif beside ten bars at most 72px tall. The
  domain's first leading key is a ranked list: serif rank numerals, fanned covers, the leader
  drawn larger, rows that open in place. Then many-valued keys typeset by weight, the chronology
  as short bars with its grain toggle, keys of two to six values as one share bar, the rest as
  one line each. Every value still opens the filtered library.
- **AC5.** The accessibility spec passes on the page (both orders, a row open).

Also: each domain declares `plural_label` (required, checked by conformance, on
`/api/item-types`); `countLabel` uses it, and the Diary no longer says "2 animes". A
`bg-primary-deep` utility gives the readable amber as a fill. The old card components
(InsightsCard, LongTailCard, ScoreDistributionCard, ChronologyCard, HeroSummary,
InsightsRanking) and the helpers only they used are deleted.

**Deviations.**
- The lead sentence judges ("You rate generously") rather than restating the modal score,
  which the rating section already states; it says nothing about scores below five ratings.
- The ranked list goes to the first leading key in the domain's declared order, not the key
  with the strongest lead, so a book's list is its authors rather than its subjects.
- The phone spec's strip check required the domain strip to overflow. Text tabs fit five
  domains at 390px, so it now checks the strip scrolls in its own box (`overflow-x: auto`)
  and stays inside the viewport.

**Seen and left.** Subjects imported from some providers include call numbers ("658.4/012",
"Hd30.28 .r854 2011"); they are the owner's data and show in "And the rest". In Ink the deep
amber is the brighter one, so the leading decade stands out less than in Paper.

Commits: `0cc2c78`, `5c454dc`, `4f94fb7`.
