# Sprint 106 — The inbox, one at a time

**Sprint:** 106
**Status:** completed
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

Delivered 2026-10-22 in `5a21642`. Verified per DEC-167: `vitest related` for the changed files
(3 files, 17 tests: `deck.test.ts`, `TriageDeckPage.test.tsx`, the app), `make check`, a new
`e2e/triage-deck.spec.ts` (5), `e2e/triage.spec.ts` (23, unchanged and green with the new header)
and the accessibility spec (30, one new for the deck, front and back). Walkthrough: the deck at
390×664, 390×740, 800×1100 and 1440×900 in Ink and Paper on stubbed data, and at 390×740 against
the real backend with four manually added books and a shelf.

- **Deliverable 1.** `/inbox/deck`, a Radix dialog over the shell (focus held, `Esc` leaves) at
  `100dvh`. The inbox header gains *One at a time*, the primary button; *Accept all suggested*
  moves to secondary beside it. The deck reads the same query key and filter as the list.
- **Deliverable 2.** The card is the cover (a typeset cover when there is none). Tapping it, the
  corner button or `i` turns it over in 3D to *The back*: subtitle, creator, year, the import's
  suggestion, the score and whether it is provisional, formats, date added, and a link to the
  full page. The title is under the card, stepped down by length so the whole of it fits.
- **Deliverable 3.** Status as large buttons (the list's target rule, including the list's
  unsaved drafts), ten score buttons (tap again to clear), shelf toggles in one scrolling row.
- **Deliverable 4.** *File* sends one `PATCH /api/entries/{id}`; *Later* sends nothing and
  remembers the pass in the tab (`akasha.triage.passed.v1`). A drag leans the card up to 14°
  and stamps it with the target status or *Later*; let go past 96px (or flicked) it decides.
  The decision lands at once and a copy flies off, so keys pressed in quick succession are
  never dropped. The next two cards stand behind.
- **Deliverable 5.** Undo reverses the last card; a filed card's undo waits for its own request
  and then writes back the previous status and, if they were sent, score and shelves.
- **Deliverable 6.** Keys as planned. Space and Enter stay the focused button's own.
- **Deliverable 7.** *That's the deck* or *Inbox clear*, the last five filed covers fanned,
  "*N* filed · *M* left for later", *Go through the M you passed*, *Back to the inbox*.

Acceptance criteria:

1. Fit at 390×664 and 1440×900, including a provisional card: card, title (unclipped), statuses,
   score and both actions in the viewport, the layer not scrolling (Playwright).
2. One PATCH with the target status; an untouched provisional score is not sent (Vitest).
3. *Later* writes nothing; the passed card returns after the rest (Vitest, Playwright).
4. Undo restores status, score and shelves (Vitest; real backend: the entry read back
   `unsorted`).
5. Swipe right files, left passes, a short drag springs back (Playwright, mouse drag at 390px).
6. The Vitest suite runs reduced: every flow works with no fly-outs.
7. Accessibility spec passes on the deck, front and back.

Found and fixed during the walkthrough:

- A press on the turn-over button landed on its SVG icon; `instanceof HTMLElement` let the card's
  own tap handler turn it over a second time, so the button did nothing. The check is `Element`.
- The first design waited for the fly-out before moving on, and dropped keys pressed during it;
  the decision now lands first and a departing copy animates.
- A 104-character title was cut at three lines of 48px on desktop; titles step down by length.

Deviations and notes:

- TDD order: the pure deck module and the page were drafted before their tests; every test was
  then observed against the code, and two real defects above were found by the browser specs,
  not by unit tests.
- Undoing a filed card whose provisional score was changed restores the number but not the
  provisional flag (a PATCH with a score always confirms it). Recorded, not fixed.
- The container's Playwright browser build (1194) did not match the package's (1228); a symlink
  outside the repository bridged it. Nothing in the repository changed for it.
