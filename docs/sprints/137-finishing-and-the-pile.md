# Sprint 137 — Finishing, and the pile

**Sprint:** 137
**Status:** ready
**Roadmap revision:** 55
**Depends on:** 136
**Owner:** Mauro

## Objective

Finishing something always records when, a finish button reads as an action rather than a
status, *Up next* is varied, and the pile can be seen as a plain list as well as sorted in the
deck. From the owner's first review of 3.0 (DEC-192).

## Required context

- DEC-192 (the owner's review and the choices made from it); DEC-179 (the finish sheet,
  Sprint 123); DEC-186 (the ranked pile).
- Frontend: `features/finish/FinishDialog.tsx`; `features/library/VirtualLibrary.tsx` and
  `pages/LibraryPage.tsx` (`onStatus`); `features/detail/OpinionDialog.tsx`;
  `features/library/NowStrip.tsx`, `features/home/OnNow.tsx`, `features/home/UpNext.tsx`,
  `pages/DetailPage.tsx` (the four *Finished* buttons); `features/home/GreetingBar.tsx`;
  `features/library/library.ts` (the library's URL filters).
- Backend: `application/ranking.py` (`rank_pile`) and its callers (`application/home.py`,
  `api/pile.py`, `application/goals.py`); `backend/tests/test_ranking.py`.

## Current implementation baseline

The finish sheet (Today / Yesterday / Another day, the score, the format) opens only from a
*Finished* button. Choosing a finished status on a library card patches the status alone, and
the opinion dialog's status menu leaves the finished date as it was, so both leave the date
empty. The button says *Finished*, which is also the name of a status. `rank_pile` sorts by
score alone, so a creator with many waiting entries fills *Up next* (five Stephen King books on
the owner's library). *N on the pile* opens `/deck/planned`, the card deck.

## Deliverables

1. **Finishing records when.** On a library card, choosing a finished status opens the finish
   sheet for that status instead of patching; *Cancel* leaves the entry as it was. In the
   opinion dialog, choosing a finished status while the finished date is empty fills it with
   today, shown in its field and editable. The bulk and triage paths are unchanged: they
   classify imports finished long ago.
2. **The button names the action.** The four buttons read *Mark as {finished status}* in the
   domain's own word ("Mark as read", "Mark as watched", "Mark as completed"), taken from the
   registry's finished status.
3. **A varied Up next.** `rank_pile` keeps its scores and orders the result in rounds: every
   creator's best waiting entry before any creator's second. An entry without a creator is its
   own. Applies to Home, `GET /api/pile` and the goal picks.
4. **The pile as a list too.** *N on the pile* in *Up next* and the greeting opens the library
   filtered to every library's waiting statuses, in the list view; a *Sort* link beside it keeps
   the deck.

## Acceptance criteria

1. Choosing *Read* on a library card opens the sheet with *Today* chosen; *Finish* stores
   today's date; *Cancel* stores nothing. The opinion dialog fills today when a finished status
   is chosen and the date is empty, and keeps a date already there (Vitest).
2. The buttons say *Mark as read* on a book and *Mark as watched* on a film (Vitest); no
   `item_type ==` branch is added.
3. Five waiting books by one author and three by others: the first four picks are four
   different creators, and the order within a creator still follows the score (pytest).
4. *N on the pile* lands on `/library` with the waiting statuses and the list view; *Sort*
   opens the deck (Vitest, and the Home e2e).

## Required tests (TDD)

`FinishDialog`, `VirtualLibrary`/`LibraryPage` status change, `OpinionDialog`, the button
labels, `test_ranking.py` variety, `UpNext`/`GreetingBar` links, `e2e/home.spec.ts`.

## Verification

Per DEC-167, and a look at the library card, the detail page and Home in the running app.

## Explicit non-scope

Home's per-library year and shelf modules (138). Changing bulk or triage status changes.

## Commit checkpoints

`[MOD]` finishing records when; `[MOD]` the button's label; `[MOD]` varied Up next; `[MOD]` the
pile as a list; `[DOCS]` close.

## Risks and decisions to surface

- A status chosen in the opinion dialog alongside an older finished date: the date already
  there wins; only an empty one is filled.

## Outcome

_Not started._
