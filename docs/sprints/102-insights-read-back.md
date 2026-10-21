# Sprint 102 — Insights, read back to you

**Sprint:** 102
**Status:** in_progress
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

Not started.
