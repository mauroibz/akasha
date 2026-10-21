# Sprint 089 — Search and activity

**Sprint:** 089
**Status:** ready
**Roadmap revision:** 45
**Depends on:** 088
**Owner:** Mauro

## Objective

Library search finds a book by any creator, series, subject or note, ranked, at any library size;
and background work is visible from anywhere in the app through one event stream and a small
activity indicator in the shell.

## Required context

- [`../production-grade-proposal.md`](../production-grade-proposal.md) §2.4 R4, §2.3 I6, §6.1,
  §6.3; DEC-165, DEC-166 (no heartbeat), DEC-167 (verification scope).
- `backend/src/book_tracker/application/library.py:842-852` (the `LIKE` search),
  `domain/normalization.py` (`normalize_text`), `backend/alembic/versions/` (latest `0022`).
- `infrastructure/jobs.py` (`record_progress`, added in 088), `api/imports.py` (job routes).
- `frontend/src/components/AppShell.tsx`, `frontend/src/pages/ImportPage.tsx:300` (the
  `setInterval` poll), `frontend/src/api/keys.ts`.

## Current implementation baseline

- Search is `LIKE '%q%'` over `title_normalized` and `creator_primary_normalized` only.
- Job progress is written per row by import search (088); enrichment writes progress only when
  it completes. Nothing streams; the import page polls on an interval.

## Deliverables

1. Migration `0023`: an FTS5 table over title, every creator, series, subjects and notes, filled
   from existing rows and kept by triggers, with text folded by `normalize_text` before indexing.
   The library query uses it, ranked by bm25 with title weighted highest; an empty or
   punctuation-only query falls back to no filter.
2. `GET /api/events`: Server-Sent Events for the current user's jobs (queued, progress, finished,
   failed), with a heartbeat comment every 15 s. Polling the job table every second server-side
   is acceptable; one producer per connection.
3. The shell's mark carries a breathing amber dot while any of the user's jobs run; it opens a
   small list of recent jobs with failures and *Retry*. The import page drops its interval poll
   for the stream.

## Acceptance criteria

1. Searching a secondary creator, a series name, a subject or a word from a note finds the entry;
   accents are ignored; a title match ranks above a note match.
2. The migration upgrades a copy of a real database and downgrades cleanly.
3. A job's progress reaches an open page within two seconds without the page polling.
4. The activity dot appears while a job runs and disappears when none do; reduced motion stops the
   breathing, not the dot.

## Required tests (TDD)

- Backend: search by each indexed field; ranking; migration up/down on a temp database; the
  events endpoint emits queued → progress → finished for one job.
- Vitest: the activity indicator renders from a stream of events.

## Verification

Per DEC-167: the backend tests above, `vitest related`, `make check`, the import and library
Playwright specs, and a screenshot of the indicator with a job running.

## Explicit non-scope

- The command bar's library half (094) uses this search; it is not built here.
- Metrics and provider health (101).

## Outcome

_Not started._
