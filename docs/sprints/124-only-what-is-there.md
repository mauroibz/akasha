# Sprint 124 — Only what is there, and one question

**Sprint:** 124
**Status:** completed
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

Delivered 2026-10-24 in `1b90e73`. Verified per DEC-167: `test_unknown_fields.py` (observed
failing first; kept, returned, listed, exported and cleared; refused where the domain has no
such field; migration 0033 up and down) with the library API, export, isolation, conformance,
migration and app-shape suites (349); `questions.test.ts` and `OneQuestion.test.tsx` (red
first) and the detail page's tests, four of which asserted the old empty rows and now assert
the new contract; `vitest related` (308); `make check`; Playwright over every spec that opens a
detail page (96: `lent` and the house accessibility checks moved to the question and *Lend…*).
Walkthrough on a fresh backend at 390: *Cien años de soledad* (read, 10, nothing else) showed
Status, Score and Shelves and "1 of 4 · When did you finish it?"; a date, *I don't remember*
for the format and a one-tap *Living room, shelf 2* (a place already used) were saved; after a
reload it asked only when it began.

1. Answering fills the field and shows the next question (Vitest, walkthrough).
2. *I don't remember* survives a reload and is never asked again for that entry (API test,
   walkthrough).
3. Migration 0033 arrives and leaves (tested).
4. Fits at 390px; accessibility passes.

Deviations and notes:

- **A column, not a table:** `entries.unknown_fields` holds a JSON list; nothing queries
  across entries by it, and the export carries it as the entry's own.
- **The quick answers are a date, the domain's formats and up to four places already
  used**, rather than the mockup's *This year / Last year*: a finish date is a day, and
  "this year" would have to invent one. The date starts empty, never today.
- **The loan row stays while something is out or has been**, so a loan's history is not
  hidden; *Lend…* moved to the page's actions.
- **Seen and left:** at 390px a long place truncates beside its *Change* button.
