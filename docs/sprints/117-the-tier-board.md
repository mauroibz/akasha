# Sprint 117 — The tier board

**Sprint:** 117
**Status:** ready
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

_Not started._
