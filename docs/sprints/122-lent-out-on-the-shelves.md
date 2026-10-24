# Sprint 122 — Lent out, on the shelves

**Sprint:** 122
**Status:** completed
**Roadmap revision:** 51
**Depends on:** 121
**Owner:** Mauro

## Objective

What is lent out stands as the first ledge on Shelves, with who has each thing, instead of a page reached only from the command bar (DEC-179 point 1).

## Required context

- DEC-179 and the *A second look* mockups (section named in the objective); DEC-176, DEC-178.

## Deliverables

1. On `/shelves`, when anything is out, a *Lent out* ledge above the shelves: its covers, how many, and who has the one out longest.
2. The ledge opens the list of loans, which keeps its one-tap *It's back* and whose back link returns to Shelves.
3. Nothing is drawn when nothing is out.

## Acceptance criteria

1. The ledge appears with open loans and not without them (tested).
2. Opening it and marking one back updates the ledge (tested).
3. Fits at 390px and 1440px; accessibility passes.

## Verification

Per DEC-167: the tests for the changed code, `vitest related`, `make check`, the Playwright
specs for the changed screens, and the changed flow seen in the running app.

## Outcome

Delivered 2026-10-24 in `d94a9ef`. Verified per DEC-167: `ShelvesPage.test.tsx` and
`LentPage.test.tsx` (each observed failing first); `vitest related` (99); `make check`;
Playwright `lent`, `shelves`, `suggested-shelves` and the shelves accessibility checks (14).
Walkthrough on a fresh backend: two books lent (Sofi since April, Juan since September); the
ledge reads "2 things · Rayuela has been with Sofi for 6 months" at 390 and 1440, no sideways
scroll; *It's back* on both, then *← Shelves*: the ledge is gone.

1. The ledge appears with open loans and not without them (Vitest, Playwright).
2. Opening it and marking one back updates the ledge (Playwright, walkthrough).
3. Fits at 390px and 1440px; accessibility passes.

Deviations and notes:

- **The list keeps its address, `/lent`.** A shelf's address is its slug, and an owner's
  shelf could be called "Lent"; the ledge links to the list instead of borrowing a slug.
- **The e2e harness now answers `/api/loans?open=true` with nothing** by default: unstubbed,
  the request reached whatever backend was on port 8000 (the owner's check server, with a loan
  on it) and failed two unrelated shelves specs.
