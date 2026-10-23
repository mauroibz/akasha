# Sprint 117 — The tier board

**Sprint:** 117
**Status:** completed
**Roadmap revision:** 49
**Depends on:** 116
**Owner:** Mauro

## Objective

A domain's scored entries shown as a tier list: one row per score, covers in rank order. Moving
a cover inside a row re-ranks it at once; moving it to another row is a proposal, applied only
when the owner confirms "Apply 3 changes" (DEC-176 point 6).

## Required context

- DEC-176; Sprints 114 (history) and 116 (ranks). `pages/InsightsPage.tsx`,
  `features/insights`, `lib/motion.ts`.

## Deliverables

1. `/tiers/:type`: rows 10 to 1 (empty rows collapsed), covers by rank; drag and drop with
   pointer and keyboard (pick up, arrows, drop).
2. A pending-changes bar listing proposed score moves ("Solaris 8 → 9") with *Apply* and
   *Discard*; applied changes are written with `score_reason` `time`.
3. Reached from Insights' score section and the command bar.

## Acceptance criteria

1. No score changes before *Apply*; *Discard* restores the board.
2. Keyboard drag works; accessibility passes; 390px usable (rows scroll sideways inside
   themselves, the page does not).

## Verification

Per DEC-167: `vitest related`, `make check`, a new tiers spec, seen in the running app.

## Outcome

Delivered 2026-10-23 in `ecd2512`. Verified per DEC-167: the board unit tests (4) and page
tests (4, the *Discard* case observed failing first); `vitest related` (42); `make check`;
Playwright `tiers` (new), `rank`, `insights`, `command-bar`, `accessibility` (49). Walkthrough
on the Sprint 116 backend with books at 10 to 7: *Solaris* proposed 8 → 10 and applied; its
history reads `(8, first), (10, time)`. 1280 Paper and 390 Ink, no sideways scroll.

1. No score changes before *Apply*; *Discard* returns only the proposals and keeps orders
   already saved (Vitest).
2. The keyboard works: Enter picks up, arrows move along a row and between rows, Escape puts
   it back, Enter puts it down (Vitest, Playwright). Accessibility passes, a cover picked up
   included. At 390px a full row scrolls inside itself; the page does not.

Deviations and notes:

- **Tap to pick up, tap to place**, not drag and drop. HTML drag and drop does not work on
  touch, and a pointer drag on rows that scroll sideways fights the scroll; two taps work
  everywhere and map onto the keyboard.
- **The bar sits above the phone's navigation.** The first version was covered by it; the
  phone spec checks the *Apply* button is what a tap there hits.
- Empty rows are short and dashed rather than faded: fading put the score chip under the
  contrast threshold (axe).
