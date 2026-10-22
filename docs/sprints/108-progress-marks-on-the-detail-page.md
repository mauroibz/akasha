# Sprint 108 — Episodes and chapters on the detail page

**Sprint:** 108
**Status:** in_progress
**Roadmap revision:** 48
**Depends on:** 107
**Owner:** Mauro

## Objective

On a series, anime or book's detail page, an optional tracker shows how far the owner got: one
collapsed line that opens to rows of lights in the goal calendar's style, an episode or chapter
checked with a tap, a whole season with one more. Moving an entry to a status that means
stopping partway asks how far it got. Quiet and never required (DEC-171, DEC-172).

## Required context

- DEC-171; DEC-172 (the owner's "if i add 'dropped' as a status ask me how far i got into
  it"); DEC-169 (the calendar of lights and its rules: nothing red, nothing says behind);
  DEC-167.
- Sprint 107's Outcome. The API: `EntryResponse.progress_marks`, `ItemResponse.outline`,
  `ProgressSpecResponse.parts_field`, `StatusSpecResponse.abandoned`,
  `POST /api/items/{id}/outline` (422 `outline_unavailable`, 502 `provider_failure`).
- `pages/DetailPage.tsx` (the personal region, the progress `PropertyRow`, the opinion save,
  the `rows` region); `features/detail/OpinionDialog.tsx` (the progress field);
  `pages/HomePage.tsx` (`onStatus` on a library row); `features/goals/GoalBand.tsx`
  (`placeClass`, the light styles); `api/library.ts` (`patchEntry`, `patchItem`,
  `progressFor`); `e2e/add-detail.spec.ts`, `e2e/accessibility.spec.ts`, `e2e/seed.ts`.

## Current implementation baseline

Observed at Sprint 107's close: the detail page shows *Episodes watched* (and now *Chapters
read* for books) as `N / total units` in a `PropertyRow`, edited through the opinion dialog's
number field. Every `rows` field is drawn in its own region, so a series' `season_episodes`
would appear there as a table. Status changes reach the API from the opinion dialog, a library
row's status popover, the inbox list, the deck and bulk actions.

## Deliverables

1. `features/progress/marks.ts`: the marks as drawn (stored marks, else the first `progress`
   in outline order), toggling one, toggling a part, filling through one, counting.
2. `features/progress/ProgressTracker.tsx`, in the personal region under the progress row:
   one line, collapsed by default ("Episodes · 23 of 62"); open, one row per part with its
   label (*Season 2*) and its lights, lit and unlit as the goal calendar draws them. A
   single-part outline has no label. Absent for a domain without progress.
3. Tapping a light toggles it; tapping a part's label checks the whole part, or clears it
   when it is all checked. Each change is one `PATCH` with the full marks.
4. Where the domain declares `parts_field` and the item has none: *Load the episode list*
   (the outline action; a quiet line on failure). Where the outline is missing its total: a
   small *Add chapters* field that saves the total to the item.
5. The lights are toggle buttons named for what they are ("Season 2, episode 5, watched");
   arrow keys move between them.
6. **How far did you get?** Setting an entry to a status its domain declares `abandoned` —
   from the detail page or a library row — opens a small dialog: the lights, where a tap
   fills everything up to and including that one, or a count where there is no outline;
   *Save* and *Skip*. Skip writes nothing more.
7. The parts field is not drawn again as a table in the `rows` region.
8. Phone: fits 390px, lights wrap, no sideways scroll.
9. The product spec describes the tracker and the question.

## Acceptance criteria

1. Checking an episode, a season, and clearing a season each write the right marks and the
   count follows; tested.
2. An imported count with no marks draws the first N lit and is stored on first touch;
   tested.
3. *Load the episode list* and *Add chapters* give an item its lights; tested.
4. The tracker is collapsed by default and absent for films and albums.
5. Dropping an entry from the detail page and from a library row asks how far; a tap on a
   light saves everything through it; *Skip* saves nothing; tested.
6. The accessibility spec passes on an open tracker and on the question, in both themes.

## Verification

Per DEC-167: `vitest related` for the changed files, `make check`, the detail-page Playwright
spec and the accessibility spec, and the tracker in the running app on a scratchpad copy of
the local library with a live series and book, in Paper, Ink and at 390px: a season checked,
a book given chapters, an imported count drawn, an entry dropped and asked.

## Explicit non-scope

- Ratings, notes or dates per episode or chapter.
- The tracker anywhere but the detail page: not on library rows, the Now strip or the deck.
- Asking how far from the inbox, the deck or a bulk action: those file many entries at once
  or in a hurry, and a question per card is the interruption the deck exists to avoid.
- Episode titles.

## Commit checkpoints

1. `[ADD]` The tracker on the detail page.
2. `[ADD]` How far did you get, when an entry is dropped.

## Risks and decisions to surface

- A 1,000-episode anime is a lot of lights; the row wraps and the line stays collapsed by
  default. If it reads badly in the walkthrough, group by hundreds and record it.

## Outcome

_Not started._
