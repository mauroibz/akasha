# Sprint 115 — The score history on screen, and "Still an 8?"

**Sprint:** 115
**Status:** completed
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

Delivered 2026-10-23 in `3f94d09`. Verified per DEC-167: `vitest related` (278), the rescore
unit tests (4), five new detail-page tests and a card test (each observed failing first),
`test_score_history.py` (7), `make check`, Playwright `rescore` (new), `accessibility` (new
checks in both themes), `add-detail`, `progress-marks`, `library`, `lent`, `editorial` (89).
Walkthrough on a fresh backend with live Open Library: *Solaris* (read, 8, finished
2019-05-01, four chapters) and *Stalker* (watched, 9); 390×800 Ink and 1280×900 Paper.

1. Each path that finishes a scored entry asks once: the opinion dialog, a library card, the
   tracker's last light (Vitest per surface; Playwright for the light).
2. *Keep* records a confirmation; a change records the new score with its reason and note
   (walkthrough: 8 → 9 "after a reread", the note shown under *Why*).
3. The history row is drawn only from two scores on, and reads correctly (Vitest, walkthrough).
4. Detail specs and accessibility pass; no sideways scroll at 390px.

Deviations and notes:

- **The inbox deck does not ask.** Filing an import as *Read* is not finishing something
  again, and asking on every scored import would be the intrusion the owner warned about.
- **The last light asks but does not change the status** (DEC-175); after a reread the entry
  stays *Reading* until the owner sets it. Seen in the walkthrough; left as decided.
- **A film is asked at once** (*Start again* on a domain with no under-way status) and the
  answer also records the day and one more rewatch.
- **Migration 0030 changed after its commit** (unreleased): the insert trigger dates a score
  that arrives with a finish date by that date, as the backfill does. Found in the
  walkthrough, where a 2019 finish was scored "today".
- Seen and left: at 390px the personal region's date values wrap ("2026-10-" / "23"),
  because each row keeps room for its hidden *Change* button. Existing; recorded.
