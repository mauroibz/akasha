# Sprint 114 — The score history, underneath

**Sprint:** 114
**Status:** planned
**Roadmap revision:** 49
**Depends on:** 113
**Owner:** Mauro

## Objective

Every change of an entry's score is kept with its date and why it changed (a reread, or time),
from every write path, and existing scores start the history (DEC-176 point 5).

## Required context

- DEC-176; DEC-171 (marks), DEC-175 (dates from lights). `infrastructure/models.py`,
  `application/library.py` (`update_entry`, bulk update), `application/imports.py` (commit and
  undo), `application/export.py`; the latest migration.

## Deliverables

1. Migration 0030: `score_events` (`id`, `entry_id` cascade, `score` nullable, `previous`
   nullable, `reason` nullable in (`reread`, `time`), `note` nullable, `recorded_at`). Triggers
   on `entries`: insert with a score records an event with no reason; an update that changes the
   score records one with reason `time` when there was a previous score. The backfill records one
   event per scored entry dated `date_finished`, else `date_added`.
2. Entry `PATCH` accepts `score_reason` and `score_note`: they label the event this write
   records, and with an unchanged score and `score_reason` the write records a confirmation
   ("still an 8") event.
3. `GET /api/entries/{id}/score-history`, oldest first.
4. `StatusSpec.finished`, declared on book `read`, anime and series `completed`, movie
   `watched`; published on `/api/item-types`; conformance requires it to be choosable.
5. Lossless JSON export carries the history.

## Acceptance criteria

1. Card, opinion dialog, deck, bulk, import commit, import undo and merge each record exactly
   the events their score changes imply (tests per path).
2. A write without a score change records nothing.
3. Migration up and down on a temporary SQLite copy; backfill counts equal scored entries.

## Verification

Per DEC-167: backend tests for the changed modules, `make check` with OpenAPI regenerated.

## Explicit non-scope

Screens (115).

## Outcome

_Not started._
