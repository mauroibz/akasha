# Sprint 144 — Shelves are a view

**Sprint:** 144
**Status:** ready
**Roadmap revision:** 56
**Depends on:** 143
**Owner:** Mauro

## Objective

Shelves stop being a second library: the index is a view of *Everything*, a shelf opens as the library filtered to it, and the pile and *Lent out* are built-in shelves.

## Required context

- DEC-193; [`../library-first-proposal.md`](../library-first-proposal.md) section 2.3 and 3.5 and the mockup.
- DEC-139 (shelves redrawn), DEC-176 (lending), DEC-192 (the pile as a list), product spec 3.3.
- Frontend: `pages/ShelvesPage.tsx`, `pages/ShelfPage.tsx`, `pages/LibraryPage.tsx` (view switch, shelf filter, *Pin to library*), `features/pile/PilePage.tsx`, `pages/LentPage.tsx`, `features/shelves/`.
- `e2e/shelves.spec.ts`, `e2e/suggested-shelves.spec.ts`, `e2e/lent.spec.ts`.

## Current implementation baseline

Observed 2026-11-23 while writing the proposal (section 2); re-observe at activation. `/shelves` is its own screen with drawn boards; `/shelves/:slug` draws a shelf with its own card and no filters; the Library has a shelf filter and pinned shelves; `/pile` and `/lent` are separate lists.

## Deliverables

1. **The Shelves view.** The Library's view switch becomes *Covers · Table · Shelves*; *Shelves* draws the boards (the index's drawing, sort and *New shelf*), across media. `/shelves` redirects to it.
2. **A shelf is the filtered library.** `/shelves/:slug` renders the Library's grid filtered to the shelf under the shelf's name and sentence, with rename and delete; the same card, controls and filters.
3. **Built-in shelves.** *The pile* and *Lent out* appear among the shelves, marked as built in and not deletable; `/pile` and `/lent` redirect to them and keep their own actions (*Sort*, *Returned*).

## Acceptance criteria

1. The Shelves view lists every shelf with its covers and count; a mixed shelf says which media it holds.
2. Changing a status or score on a shelf's page works as on the Library.
3. `/shelves`, `/pile` and `/lent` redirect; *Pin to library* is gone, since a shelf can be a showcase.
4. No serious axe violation or overflow at 390 and 1440 px in the Shelves view and on a shelf.

## Required tests (TDD)

The view switch, the shelf route (Vitest); `e2e/shelves.spec.ts`, `e2e/lent.spec.ts` rewritten.

## Verification

Per DEC-167: the tests covering the changed code, `make check`, the Playwright specs for the changed screens, and a look at them in the running app at 1440 and 390 px in *Ink* and *Paper*.

## Explicit non-scope

Shelves with a rule (145).

## Commit checkpoints

`[ADD]` the Shelves view; `[MOD]` a shelf as the filtered library; `[MOD]` built-in shelves; `[DOCS]` close.

## Risks and decisions to surface

- A shelf holds several media and the grid is one medium at a time: a shelf's page shows every medium it holds, grouped.

## Outcome

_Not started. On completion record delivered behavior, commands and actual results, commit IDs, deviations/decisions, and impact on every future sprint._
