# Sprint 098 — Now and Diary

**Sprint:** 098
**Status:** ready
**Roadmap revision:** 45
**Depends on:** 097
**Owner:** Mauro

## Objective

The library opens on what you are in the middle of: a *Now* strip of everything in progress
across every domain, with one tap to advance it. And a *Diary* shows what you finished, month by
month, across books, films, albums, anime and series: the reading journal the brand promises.

## Required context

- [`../production-grade-proposal.md`](../production-grade-proposal.md) §7 (Now, Diary); DEC-167.
- Each domain's `statuses` and `progress` spec (`domain/spec.py`, `domains/*/__init__.py`);
  `application/library.py` (`list_entries`, the `progress` patch rules); `pages/HomePage.tsx`;
  `features/library/useItemTypes.ts`; the nav in `components/AppShell.tsx`.

## Current implementation baseline

Progress is recorded per entry for domains that declare it (episodes, pages). There is no view of
"in progress" across domains, and nothing reads `date_finished` as a timeline.

## Deliverables

1. `GET /api/now`: the person's entries whose status is the domain's in-progress status
   (declared, not branched on type), most recently touched first, with progress and total.
2. A *Now* strip above the library grid (hidden when empty): covers with a progress bar and a
   `+1`/`+10` button sized by the domain's progress unit, saving through the existing patch.
3. `GET /api/diary?year=`: entries finished in a year, grouped by month, with per-domain counts.
4. `/diary`: months newest first, "March: 3 books, 5 films", each with its covers; a year switch.
   Reached from the nav (or the command bar's *Go to Diary*).

## Acceptance criteria

1. Every domain with an in-progress status appears in Now without code naming the domain (the
   conformance rule).
2. `+1` advances progress and the bar moves at once; a failure puts it back.
3. The diary's counts per month equal the entries finished that month.

## Verification

Per DEC-167, plus the route-structure tests for the two routes; `vitest related`, `make check`,
the library spec, and screenshots of Now and Diary on a copy of the owner's data.

## Outcome

_Not started._
