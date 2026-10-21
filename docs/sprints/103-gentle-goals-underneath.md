# Sprint 103 — Gentle goals, underneath

**Sprint:** 103
**Status:** in_progress
**Roadmap revision:** 46
**Depends on:** 102
**Owner:** Mauro

## Objective

A person can set a gentle goal per library (*N a month* or *N a year*), see how the year is
going by month, and ask for a few picks from what is waiting. This sprint builds the model and
the API; Sprint 104 builds the screens (DEC-169).

## Required context

- DEC-169; DEC-167. The canvas: https://claude.ai/artifact/6vt1GZ5nBi5zYq67ibZh3c, the goals
  boards.
- `domain/spec.py` (`StatusSpec.in_progress`, Sprint 098, the pattern for `planned`),
  `application/library.py` (`now`, `diary`), `api/library.py`, migrations 0024 and 0025.

## Current implementation baseline

No goals. Planned statuses exist by name only: book `to_read`, movie `watchlist`, anime and
series `plan_to_watch`. Albums record no finish date (`entry_fields` is empty), so a goal that
counts finish dates cannot exist for them.

## Deliverables

1. `StatusSpec.planned`, declared by the four domains above and published on `/api/item-types`.
2. Migration 0026, `goals`: user, item type, count (1–999), period (`month` or `year`), whether
   to suggest picks, timestamps; one goal per person and domain.
3. `GET /api/goals`, `PUT /api/goals/{item_type}`, `DELETE /api/goals/{item_type}`. A domain
   without `date_finished` in its `entry_fields` is refused with 422.
4. `GET /api/goals/{item_type}/progress?year=`: twelve monthly counts of entries finished in that
   year, the total, and the year's target (count × 12, or count).
5. `GET /api/goals/{item_type}/picks?limit=`: entries in a planned status, each with a reason.
   A *creator* reason when the entry's primary creator averages 8 or more over two or more rated
   entries in that domain (best average first), a *waiting* reason for the oldest added
   (oldest first). The two lists alternate, without repeats.

## Acceptance criteria

1. Setting, changing and removing a goal round-trips; another person never sees it.
2. Progress counts by month of finish date, and months count together: no field says behind.
3. Picks come only from planned statuses, carry their reason, and are stable between calls.
4. Shared layers never name a status: `planned` and `in_progress` are read from declarations.

## Verification

Per DEC-167: the new goals tests, migration up and down, route-structure and isolation tests,
conformance, `make check`.

## Outcome

Not started.
