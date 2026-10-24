# Sprint 124 — Only what is there, and one question

**Sprint:** 124
**Status:** planned
**Roadmap revision:** 51
**Depends on:** 123
**Owner:** Mauro

## Objective

The personal region shows only the rows that hold a value, and asks one question at a time about the most useful gap (DEC-179 point 3, mockup 1A).

## Required context

- DEC-179 and the *A second look* mockups (section named in the objective); DEC-176, DEC-178.

## Deliverables

1. Empty rows are hidden on the detail page; status, score and shelves always show.
2. Below the rows, one question card: the most useful empty field first (finished date for something finished, then format, start date, place), with quick answers and *I don't remember*.
3. *I don't remember* is kept per entry and field and stops that question (migration 0033).

## Acceptance criteria

1. Answering fills the field and shows the next question (tested).
2. *I don't remember* survives a reload and is never asked again for that entry (tested).
3. Migration 0033 arrives and leaves (tested).
4. Fits at 390px; accessibility passes.

## Verification

Per DEC-167: the tests for the changed code, `vitest related`, `make check`, the Playwright
specs for the changed screens, and the changed flow seen in the running app.

## Outcome

Not started.
