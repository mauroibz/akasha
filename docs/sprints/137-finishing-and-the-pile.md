# Sprint 137 — Finishing, and the pile

**Sprint:** 137
**Status:** completed
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

Completed 2026-11-23 (DEC-192). Commits: `d631cc6` (the pile in rounds), `5d2a741` (*Mark as
read*), `ffeb541` (finishing records when), `097eef8` (the pile as a list), and the closing
documentation commit.

Delivered:

1. A library card moved to a finished status opens the finish sheet for that status
   (`FinishDialog` takes `status`), *Today* chosen; *Cancel* writes nothing and the card keeps
   its status. The sheet also asks *Still an 8?*, so the separate *Still* dialog no longer
   follows a card's finish. The opinion dialog fills an empty finished date with today when a
   finished status is chosen, and keeps a date already there. Bulk and triage unchanged.
2. `features/finish/label.ts`: *Mark as* the domain's finished status label ("Mark as read",
   "Mark as watched", "Mark as completed"; "Mark finished" where a domain has none), on the
   library's Now strip, Home's On now and Up next, the detail page and the new pile page.
3. `rank_pile` orders its scored candidates in rounds by `(item type, normalized creator)`:
   every creator's best before any creator's second. Home, `GET /api/pile` and goal picks.
4. **Deviation:** the library shows one domain at a time, so a cross-library pile cannot be a
   library filter. The pile is its own page, `/pile` (`features/pile/PilePage.tsx`): every
   waiting entry in ranked order, the strongest reason, a library filter, *Start* or *Mark as*,
   and *Sort in cards →* to `/deck/planned`. `GET /api/pile` accepts up to 1,000. *N on the pile*
   in Up next and the greeting open it; *Sort* beside Up next's opens the deck.

Acceptance criteria:

1. `LibraryPage.test.tsx` (the sheet with *Today*, today's date sent; *Cancel* sends nothing),
   `OpinionDialog.test.tsx` (fills today; keeps a set date).
2. `label.test.ts`; the On now, Up next, Now strip and detail tests use the new names. No
   `item_type ==` added.
3. `test_one_creator_does_not_fill_the_top_of_the_pile` (five by one author, three by others:
   the first four are four creators; the rest keep the score's order).
4. `UpNext.test.tsx`, `GreetingBar.test.tsx`, `PilePage.test.tsx` (3), and `e2e/home.spec.ts`
   *the pile's count opens the pile as a list, and Sort the deck*.

Verification: backend `test_ranking` (22), `test_goals`, `test_home_api`, `test_library_source`,
`test_isolation`; Vitest on the touched files (finish, detail, library page, home, pile, App);
Playwright `home.spec.ts`, `rescore.spec.ts`, `accessibility.spec.ts` 69 passed; `make check`.
Walkthrough on a seeded library (six waiting Stephen King books and four other authors): Up
next shows one King then four others; `/pile` at 1440 and 390 (no overflow); a card set to
*Read* opens *You finished Dune* with *Today*; the opinion dialog shows today under *Finished*.

Environment note: a local Akasha 1.5.7 container listens on 127.0.0.1:8000, where the e2e dev
server proxies unstubbed `/api` calls; with it up, 16–17 accessibility tests fail on `main` too.
Run Playwright with `AKASHA_E2E_BACKEND=http://127.0.0.1:9` while it runs.
