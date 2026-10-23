# Sprint 118 — The Diary as a timeline

**Sprint:** 118
**Status:** completed
**Roadmap revision:** 49
**Depends on:** 117
**Owner:** Mauro

## Objective

The Diary gains an *All years* view: one timeline across every library, in order, with finishes,
starts again and score changes as events, so the film after the book shows by itself (DEC-176
point 7).

## Required context

- DEC-176; Sprint 114 (score events). `pages/DiaryPage.tsx`, `application/library.py`
  (`diary`), `api/library.py`.

## Deliverables

1. `GET /api/diary/timeline?before=`: events newest first, keyset-paged: finished, started again,
   score changed (with reason).
2. The Diary's year switch gains *All years*; the view is a vertical timeline grouped by year and
   month, small covers, the domain shown by its plural name, a score change as "7 → 9, reread".

## Acceptance criteria

1. Events across domains interleave by date; paging is stable.
2. Accessibility and 390px fit; the per-year view is unchanged.

## Verification

Per DEC-167: backend tests for the changed modules, `vitest related`, `make check`, the Diary
spec, seen in the running app.

## Outcome

Delivered 2026-10-23 in `a420400`. Verified per DEC-167: `test_diary_timeline.py` (3, observed
failing first) with isolation and the diary suite (56); `vitest related` (281); `make check`;
Playwright `diary-timeline` (new) and `accessibility` (new timeline checks, both themes; 44).
Walkthrough on a fresh backend: *Solaris* (finished 2019 at 7, reread to 9 with a note),
*Dune* the book (2019) and the film (2021, later 7 → 6), *Stoner* (2024); 1280 Paper and
390 Ink, no sideways scroll.

1. Events across domains interleave by date; paging is stable (tested across a day with two
   finishes); a bad cursor is 400.
2. The per-year view is unchanged; *All years* is the first option of the year switch.

Deviations and notes:

- **A finish shows the score it had then**, read from the history (the last change by the end
  of that day), else the score it has. The walkthrough showed *Solaris* "Finished 9" in 2019
  before this; the 9 belongs to the reread, which is its own event.
- **No "started again" event.** *Start again* records no row of its own; the reread shows
  through the score it produced. A row for it would need a table this line does not have.
- The Diary's lede still says "month by month" over the timeline; it is true of both.
