# Sprint 115 — The score history on screen, and "Still an 8?"

**Sprint:** 115
**Status:** ready
**Roadmap revision:** 49
**Depends on:** 114
**Owner:** Mauro

## Objective

The detail page shows how a score changed ("2019 · 7 → 2026 · 9, reread: …"). A finished entry
can be started again, and finishing it again asks "Still an 8?" with keep, change and an
optional line on why (DEC-176 point 5).

## Required context

- DEC-176; Sprint 114's Outcome. `pages/DetailPage.tsx`, the progress tracker and
  `HowFarDialog`, `features/detail/OpinionDialog.tsx`, `pages/HomePage.tsx` (status changes from
  cards), `StatusSpec.finished`/`in_progress`.

## Deliverables

1. A *Score over time* row on the detail page when the history has more than one event: a small
   line of scores with years, each event's reason and note on hover or tap.
2. *Start again* on a finished entry: moves it to the domain's in-progress status, sets
   *Started* to today, clears *Finished* and the marks after saying so, and increments
   `reread_count` where the domain has it. A domain with no in-progress status (films) asks
   the question at once and sets *Finished* to today.
3. *Still an 8?*: when an entry with a score moves into a finished status, from any surface
   (card, detail, tracker's last light, deck), a small dialog offers *Still 8*, the ten scores,
   and a line for why. The answer is written with `score_reason` `reread` when the pass began
   with *Start again*, else `time`. Dismissing writes nothing.

## Acceptance criteria

1. Each path that finishes a scored entry asks once (Vitest per surface).
2. Keep records a confirmation; change records the new score with its reason and note.
3. The history row reads correctly for one, two and many events.
4. Detail Playwright spec and accessibility pass; seen in the running app.

## Verification

Per DEC-167: `vitest related`, `make check`, the detail and library specs, the flow walked in
the running app.

## Outcome

_Not started._
