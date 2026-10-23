# Sprint 112 — The deck, for any chore

**Sprint:** 112
**Status:** in_progress
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

_Not started._
