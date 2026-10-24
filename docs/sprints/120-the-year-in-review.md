# Sprint 120 — The year in review

**Sprint:** 120
**Status:** completed
**Roadmap revision:** 50
**Depends on:** 119
**Owner:** Mauro

## Objective

One page per year, reached from the Diary, that reads the year back in the Insights sentence
style: what was finished across every library, the best of it, how it was rated, month by
month, the scores changed and why, and a line the owner wrote (DEC-178, mockup 04).

## Required context

- DEC-178, DEC-176; the mockup page; Sprints 102 (Insights read back) and 114 (score history).
- `pages/DiaryPage.tsx`, `pages/InsightsPage.tsx`, `features/insights` (`prose.ts`),
  `application/library.py` (`diary`, `insights_summary`), `api/library.py`.

## Deliverables

1. `GET /api/diary/{year}/review`: counts per domain of what was finished that year; the
   highest scores; the score distribution of those finished; finishes per month; the score
   changes recorded that year with reasons and notes; one note from that year.
2. `/diary/:year/review`: a lead sentence with the figures in amber, then numbered sections,
   each a sentence and a chart no bigger than its data; plural domain names from the registry.
3. The Diary's year switch offers *Your {year}* for a year with finishes.

## Acceptance criteria

1. Counts cross domains and match the Diary for that year (tested).
2. A year with nothing finished says so in a sentence; no empty charts.
3. Accessibility and 390px fit.

## Verification

Per DEC-167: backend tests for the changed modules, `vitest related`, `make check`, a new
review spec and the Diary spec, seen in the running app.

## Explicit non-scope

Sharing or exporting the page; a notice when a year ends.

## Outcome

Delivered 2026-10-23 in `92923b2`. Verified per DEC-167: `test_year_review.py` (observed
failing first) with the diary, timeline, isolation and API suites (78); the sentence tests
(4) and page tests (2); `vitest related` (287); `make check`; Playwright `year-review` (new,
desktop and phone), `diary-timeline`, `insights` and `accessibility` (52). Walkthrough on a
fresh backend: four live books and the 2021 *Dune* film finished in 2025, opened from the
Diary's 2025 at 1280 Paper and 390 Ink.

1. Counts cross domains and match the Diary for the year (API test).
2. A year with nothing finished says so in one sentence and draws no chart.
3. Accessibility passes; no sideways scroll at 390px.

Deviations and notes:

- **The link appears only on a year with finishes.** The Diary opens on the current year,
  which may have none yet; the owner chooses a past year first (seen in the walkthrough).
- **The rating section is Insights' own**, so it is titled "How you rate" on a past year.
- A finish carries the score it had then (as the timeline does, Sprint 118).
- Computed when opened, never frozen (DEC-178).
