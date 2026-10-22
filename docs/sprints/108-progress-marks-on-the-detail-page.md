# Sprint 108 — Episodes and chapters on the detail page

**Sprint:** 108
**Status:** planned
**Roadmap revision:** 48
**Depends on:** 107
**Owner:** Mauro

## Objective

On a series, anime or book's detail page, an optional tracker shows how far the owner got: one
collapsed line that opens to rows of lights in the goal calendar's style, an episode or chapter
checked with a tap, a whole season with one more. Quiet and never required (DEC-171).

## Required context

- DEC-171; DEC-169 (the calendar of lights and its rules: nothing red, nothing says behind);
  DEC-167.
- Sprint 107's Outcome and API; `pages/DetailPage.tsx` (the personal region and the existing
  progress control); `features/goals/GoalBand.tsx` and `goals.ts` (`calendarPlaces`, the light
  styles); `api/library.ts` (`patchEntry`).

## Current implementation baseline

To be observed at activation. Expected: the detail page shows *Episodes watched* as a number with
the total beside it, and no per-episode control.

## Deliverables

1. In the personal region, under the progress count: one line, collapsed by default —
   "Episodes · 23 of 62", "Chapters · 7 of 32". Nothing is shown for a domain without progress.
2. Open, one row per part: the part's label (*Season 2*) and its lights, lit for checked, unlit
   for the rest, drawn as the goal calendar draws them. A single-part outline (anime, books)
   is one row without a label, wrapping as needed.
3. Tapping a light toggles it; tapping a part's label checks the whole part, or clears it when
   it is all checked. Each change is one `PATCH` with the full marks; the count beside the line
   follows.
4. An entry with a count and no marks shows the first N lit; its first touch stores them as
   marks (DEC-171 point 3).
5. No outline yet: a series offers *Load the episode list* (Sprint 107's endpoint, with a quiet
   line if the provider fails); a book offers *Add chapters*, a small number field that saves
   `chapters` to the item.
6. Keyboard: the lights are a grid of toggle buttons, arrow keys move within it, each named
   ("Season 2, episode 5, watched").
7. Phone: fits 390px, lights wrap, no sideways scroll.
8. The product spec describes the tracker; the user guide, if one covers the detail page, too.

## Acceptance criteria

1. Checking an episode, a season, and clearing a season each write the right marks and update
   the count; tested.
2. An imported count with no marks draws the first N lit and is stored on first touch; tested.
3. *Load the episode list* fills a series without an outline; *Add chapters* gives a book its
   lights; tested.
4. The tracker is collapsed by default and absent for films and albums.
5. The accessibility spec passes on an open tracker in both themes.

## Verification

Per DEC-167: `vitest related` for the changed files, `make check`, the detail-page Playwright
spec and the accessibility spec, and the tracker in the running app on a copy of the owner's
library in Paper, Ink and at 390px: a season checked, a book given chapters, an imported anime
count drawn.

## Explicit non-scope

- Ratings, notes or dates per episode or chapter.
- The tracker anywhere but the detail page: not on library rows, the Now strip or the deck.
- Episode titles.

## Commit checkpoints

1. `[ADD]` The tracker on the detail page.

## Risks and decisions to surface

- A 1,000-episode anime is a lot of lights; the row wraps and the line stays collapsed by
  default. If it reads badly in the walkthrough, group by hundreds and record it.

## Outcome

_Not started._
