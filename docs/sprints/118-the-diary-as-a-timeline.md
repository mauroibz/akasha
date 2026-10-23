# Sprint 118 — The Diary as a timeline

**Sprint:** 118
**Status:** ready
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

_Not started._
