# Sprint 120 — The year in review

**Sprint:** 120
**Status:** in_progress
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

_Not started._
