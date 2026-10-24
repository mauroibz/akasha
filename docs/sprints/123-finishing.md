# Sprint 123 — Finishing

**Sprint:** 123
**Status:** completed
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

Delivered 2026-10-24 in `49c7921`. Verified per DEC-167: `test_finishing.py` (observed failing
first) with the library API, score history, isolation and domain-conformance suites (284);
`FinishDialog.test.tsx`, the detail page and Now strip tests (each new test red first);
`vitest related` (292); `make check`; Playwright `rescore` (the finish flow and its phone fit),
`progress-marks`, `library` and the finish-sheet accessibility checks in both schemes.
Walkthrough on a fresh backend at 390: *Rayuela* moved to Reading got today as its start; its
*Now* card's *Finished* took a 9 and *Physical*, and the strip emptied; *Solaris* (8, 2019)
started again and finished from its page with the score kept, one `reread` history row.

1. Finishing from the page and from *Now* sets the finished status and the date chosen
   (Vitest, Playwright, walkthrough).
2. A reread finished this way writes one score-history row (Playwright, walkthrough).
3. An empty start date is filled on starting and an existing one is kept (API test).
4. Fits at 390px; accessibility passes.

Deviations and notes:

- **The question is part of the sheet**, not a second dialog after it: "Still an 8?" is the
  score question's legend when a score exists, and finishing keeps or changes it as the
  *Still* dialog does.
- **Formats are the domain's own** (a book's are Physical, Borrowed, Digital), not the
  mockup's Paperback and Ebook.
- **An entry added already under way is not dated**: an import's "currently reading" says
  nothing about today.
- **Prerequisite repair:** the progress row's *Show chapters* pushed the detail page one pixel
  sideways at 390px; on a phone it reads *Show*, and the name keeps the unit.
