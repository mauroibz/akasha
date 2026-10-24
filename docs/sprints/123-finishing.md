# Sprint 123 — Finishing

**Sprint:** 123
**Status:** planned
**Roadmap revision:** 51
**Depends on:** 122
**Owner:** Mauro

## Objective

Anything under way can be finished in one step from its page and from the library's *Now* strip, with one sheet that asks when, the score and the format (DEC-179 point 2, mockup 1C).

## Required context

- DEC-179 and the *A second look* mockups (section named in the objective); DEC-176, DEC-178.

## Deliverables

1. A *Finished* action on the detail page and on each *Now* card while the entry is under way.
2. The finish sheet: when (today chosen; yesterday; pick a date), the score, and the format, each skippable; with a score already set it asks "Still an 8?" as the score question.
3. Moving an entry to its under-way status fills an empty start date with today, in the shared layer, for every domain that has one.

## Acceptance criteria

1. Finishing from the page and from *Now* sets the finished status and the date chosen (tested).
2. A reread finished this way writes one score-history row (tested).
3. An empty start date is filled on starting and an existing one is kept (tested).
4. Fits at 390px; accessibility passes.

## Verification

Per DEC-167: the tests for the changed code, `vitest related`, `make check`, the Playwright
specs for the changed screens, and the changed flow seen in the running app.

## Outcome

Not started.
