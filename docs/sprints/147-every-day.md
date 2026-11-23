# Sprint 147 — Every day

**Sprint:** 147
**Status:** planned
**Roadmap revision:** 56
**Depends on:** 146
**Owner:** Mauro

## Objective

The Journal gains the *Every day* widget: this week or this month as a grid of days, lit on the days something was read, watched or finished.

## Required context

- DEC-193; [`../library-first-proposal.md`](../library-first-proposal.md) section 3.6 and the mockup.
- DEC-169 and DEC-171 (lights: unlit is plain, nothing says behind), DEC-172 (progress marks), DEC-146 (per-user data).
- Backend: where progress and finishes are written (`application/` entry patching), `alembic/versions/`. Frontend: the Journal's widget slot, `features/progress/Lights.tsx` for the drawing.

## Current implementation baseline

Progress marks record which episode or chapter is done, not when. Entries carry `date_started`, `date_finished` and `date_added`.

## Deliverables

1. **The record.** One migration: `lit_days (user_id, day, entry_id, source)` with source `progress`, `finish` or `tap` and an optional entry, unique per user, day and entry. Logging progress or finishing an entry of a counted medium writes today for that entry; the migration back-fills from stored finish and start dates.
2. **The API.** `GET /api/lit-days?from=&to=` and `PUT`/`DELETE /api/lit-days/{day}` for a tap; which media count is stored with the media preferences and defaults to the *Front* ones.
3. **The widget.** *This week* and *This month* as a grid of days, Monday first, today outlined, a lit day in the accent; the count is said in words ("14 days in November"). No streaks.
4. **What was it for?** Lighting a day asks one question, in place: the entries under way are offered as covers, one tap each, more than one allowed, with *Something else* (the bar's library search) and *Just light it*. Nothing else is asked: no amount, no note. A lit day names what it was for; tapping it again shows them and offers to unlight. The flow is kept to that one step (the owner, 2026-11-23: "it must be kept simple and calm").

## Acceptance criteria

1. Logging an episode today lights today for that entry; removing the mark does not unlight it if it was also tapped.
5. Lighting today with two things under way offers both; choosing one lights the day and the day then names it. *Just light it* lights the day with no entry. Choosing an entry changes nothing on the entry itself.
2. The widget never shows more than a month; a future day cannot be lit.
3. Two users' days are separate; a medium that does not count does not light a day (pytest).
4. Each day is a toggle button named by its date; the grid is operable by keyboard; no serious axe violation.

## Required tests (TDD)

`test_lit_days.py` (writes, back-fill, isolation, API), the widget (Vitest), `e2e/` one spec for the widget.

## Verification

Per DEC-167: the tests covering the changed code, `make check`, the Playwright specs for the changed screens, and a look at them in the running app at 1440 and 390 px in *Ink* and *Paper*. Migrate a copy of a real library and check the back-fill.

## Explicit non-scope

A year view, streaks, reminders. Logging progress from the question (a later expansion the owner named as possible).

## Commit checkpoints

`[ADD]` lit days and their API; `[ADD]` the widget; `[DOCS]` close.

## Risks and decisions to surface

- "Today" is the person's local day; the client sends it, as the finish sheet does.

## Outcome

_Not started. On completion record delivered behavior, commands and actual results, commit IDs, deviations/decisions, and impact on every future sprint._
