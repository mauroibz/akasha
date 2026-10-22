# Sprint 106 — The inbox, one at a time

**Sprint:** 106
**Status:** ready
**Roadmap revision:** 47
**Depends on:** 105
**Owner:** Mauro

## Objective

After a large import the inbox can be sorted one entry at a time, on a phone as well as a
desktop: a full-screen deck where each card carries a large cover and the whole title, and the
status, score and shelves are set on the same screen without scrolling. An entry can be passed
and left for later. The owner, 2026-10-22, with a screenshot of the inbox at phone width where
every title was cut to three letters: *"the list to go though them is useless, all the titles
are cutoff. Design and implement an interactive way of going though them one at a time … it
should include a way for me to 'pass', move to the next one and leave them for later. It should
work on both desktop and mobile and feel fun to use"* (DEC-170).

## Required context

- DEC-170; DEC-167; DEC-079 (triage lives under Import); product spec, *Triage — the inbox*.
- `pages/TriagePage.tsx` (status drafts, the target status rule, invalidations),
  `api/library.ts` (`patchEntry`, `getLibraryPage`), `features/library/labels.ts`,
  `features/shelves/OpeningCover.tsx` (`TypesetCover`), `lib/motion.ts`, `App.tsx`.
- `e2e/triage.spec.ts`, `e2e/seed.ts`.

## Current implementation baseline

`/inbox` is a virtualized list: checkbox, a thumbnail hidden below `sm`, title and creator, a
status select, a score select and an apply check. At 390px the two selects and the check take
the row, and the title column is left about 100px: "A Fe…", "Geor…".

## Deliverables

1. `/inbox/deck`, opened from the inbox's header (*One at a time*), carrying the inbox's own
   filter. A full-screen layer over the app shell, sized to the dynamic viewport so the
   controls never scroll on a phone.
2. A card per entry: the cover large (a typeset cover where there is none), the full title,
   creator and year. Tapping the cover turns the card over to its back: subtitle, year,
   formats, the importer's suggestion and where it came from.
3. On the same screen: the domain's choosable statuses as large buttons (the target status rule
   of the list: a draft, else the importer's suggestion, else the domain default), a 1–10 score
   row with a clear, and the shelves as toggles when there are any.
4. *File* writes status, a touched score and the shelves in one request and moves on; *Later*
   passes, leaving the entry in the inbox and putting it at the back of the deck. Dragging the
   card right files it and left passes it; the card leans and is stamped as it goes. The next
   two cards stand behind the current one.
5. *Undo* puts back the last card, filed or passed; a filed card's status, score and shelves are
   restored.
6. Keyboard: the domain's status hotkeys, `1`–`9` and `0` for score, `Enter` or `→` to file,
   `Space` or `←` for later, `Backspace` to undo, `i` to turn the card, `Escape` to leave.
7. The end of the deck: how many were filed and passed, the filed covers fanned, *Go through
   the N you passed* and *Back to the inbox*.

## Acceptance criteria

1. At 390×664 and 1440×900 the cover, the whole title, the statuses, the score and the actions
   are on screen without the page scrolling; tested in Playwright.
2. Filing sends one `PATCH /api/entries/{id}` with the target status, and the score only when
   the owner touched it (an untouched provisional score stays provisional); tested.
3. *Later* sends nothing; the passed card comes back after the others; tested.
4. Undo restores a filed entry's status, score and shelves; tested.
5. A swipe files and passes on a touch-sized viewport; tested in Playwright with a drag.
6. `prefers-reduced-motion` keeps every flow working without fly-outs (the Vitest suite runs
   reduced).
7. The accessibility spec passes on the deck.

## Verification

Per DEC-167: `vitest related` for the changed files, `make check`, `e2e/triage-deck.spec.ts`,
`e2e/triage.spec.ts` and the accessibility spec, and the deck in the running app at 390px and
1440px in both themes, a swipe seen.

## Explicit non-scope

- Discard from a card. The product spec keeps discard a deliberate, selection-only action.
- Conflict resolution on the card; editing metadata from the card (the detail page does both).
- Any backend or schema change.

## Outcome

_Not started._
