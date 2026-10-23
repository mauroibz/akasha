# Sprint 112 — The deck, for any chore

**Sprint:** 112
**Status:** completed
**Roadmap revision:** 49
**Depends on:** 111
**Owner:** Mauro

## Objective

The inbox deck's one-card-at-a-time shell takes any queue of entries and any set of answers.
Two chores ship on it: *Still want this?* over the planned pile (keep, let go, later) and *Find
a cover* over entries without one (pick a candidate, skip) (DEC-176).

## Required context

- DEC-170, DEC-176; Sprint 106's Outcome. `pages/TriageDeckPage.tsx`, `features/triage/deck.ts`,
  `features/triage/DeckCard.tsx`, `features/detail/CoverDialog.tsx` (cover candidates),
  `StatusSpec.planned`.

## Deliverables

1. A shared deck shell (`features/deck/`): the layer, the card stack, swipe, keys, undo, the
   end screen; a chore supplies its queue, its answers and how each answer is written and undone.
   The inbox deck becomes the first chore with no change in behaviour.
2. *Still want this?* (`/deck/planned`): entries in a planned status, oldest added first. *Keep*
   (right) leaves it; *Let go* (left) deletes the entry after the end screen's single
   confirmation of all let-go cards, so nothing is deleted card by card; *Later* passes.
3. *Find a cover* (`/deck/covers`): entries whose item has no cover; the card shows up to six
   candidates from the existing cover-candidates endpoint, fetched only for the card on screen.
4. A *Chores* entry point listing the decks with their counts, from the command bar and from
   Settings → Your data.

## Acceptance criteria

1. The inbox deck's existing Vitest and Playwright suites pass unchanged.
2. Let-go cards are deleted only after confirmation at the end, and undo before then restores
   them with no request.
3. A chosen cover installs through the existing cover endpoint; skipping sends nothing.
4. Fits at 390×664 and 1440×900; accessibility spec passes on both new decks.

## Verification

Per DEC-167: `vitest related`, `make check`, `e2e/triage-deck.spec.ts` and a new
`e2e/chores.spec.ts`, and both decks in the running app.

## Explicit non-scope

Duplicates (113). Missing details as a deck (the detail page's *Fill from provider* covers it).

## Outcome

Delivered 2026-10-23 in `4ebabaf` (the shell, a `[REF]`), `b1bd77a` (a copy fix) and the chores
(`7feefa1`). Verified per DEC-167: backend `test_chores.py` with the list suites (45);
`vitest related` (265); `make check`; Playwright `triage-deck`, `triage`, `chores` (new),
`command-bar` and `accessibility` (69, with new checks on the chores page and both decks in
both themes). Walkthrough on a fresh backend with live Open Library: four books on *To read*,
one film on the watchlist, two books without covers; 390×740 Ink and 1280×900 Paper.

1. The inbox deck's suites passed unchanged after the shell was extracted (13 Vitest, 28
   Playwright).
2. Let-go cards are deleted only at the end, after one confirmation, in one bulk request; undo
   before then sends nothing (Vitest, Playwright; walkthrough: Piranesi removed, four kept).
3. A chosen cover installs through the existing endpoint; *Later* sends nothing (Vitest,
   Playwright; walkthrough: Ficciones took one of six live candidates).
4. Fits at 390×664 and 1440×900; accessibility passes on both decks and `/deck`.

Found during the walkthrough and fixed: Open Library offered candidates whose image does not
load or is a thumbnail; choosing one failed with 422 and the card came back. The deck now drops
them, as the detail page's cover chooser already did, and words the failure as the chore's.
Also fixed: the inbox deck's end read "Nothing filed this time.." with two full stops.

Deviations and notes:

- `GET /api/entries` takes `cover=missing` (part of the cursor's filter key).
- An installed cover is not taken back by *Undo*: the card returns so another cover can replace
  it. There is no endpoint to remove a cover, and adding one for this was not worth it.
- *Keep* writes nothing; a kept card comes back the next time the chore runs. Remembering a
  keep would need a "last asked" date per entry; left for the revisit work (DEC-176 point on
  resurfacing), which needs the same thing.
- TDD order: the two chore pages were written before their tests were first run; the tests were
  written first and observed only after. The backend filter test was observed failing first.
