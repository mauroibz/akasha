# Sprint 109 — Undo on the card, and facts that fill themselves

**Sprint:** 109
**Status:** in_progress
**Roadmap revision:** 49
**Depends on:** 108
**Owner:** Mauro

## Objective

A status or score changed from a library card can be taken back with one tap for a few seconds
after. The detail page's *Edition facts* lists only the facts it has, and offers one *Fill from
provider* action that fills the empty ones without touching any value already there (DEC-176).

## Required context

- DEC-176; DEC-167; DEC-028 (the rollback mark); DEC-170 and Sprint 106's Outcome (undo in the
  deck, the provisional-flag deviation).
- `features/library/usePatchEntry.ts`, `pages/HomePage.tsx` (the mutation and its `onSaved`),
  `features/library/VirtualLibrary.tsx`; `pages/DetailPage.tsx` (*Edition facts*, the refresh
  dialog); `api/library.ts`.
- `application/library.py` (`update_entry`), `api/library.py` (entry `PATCH`, `refresh_item`,
  `_primary_provider`), `application/enrichment.py` (`_fill_empty_fields`,
  `enqueue_enrichment_backfill`).

## Current implementation baseline

A card's status or score change is optimistic and rolled back on failure, with no way to undo a
success. A `PATCH` with any score sets `score_provisional` to 0, so an undo could not restore a
provisional score as provisional. *Edition facts* prints every inline field, "—" when empty;
its only provider action is *Refresh from provider*, which overwrites behind a confirmation.

## Deliverables

1. Entry `PATCH` accepts `score_provisional: true` with a score, so a write can put back a
   provisional score as it was. `false` or absent keeps today's behaviour.
2. After a card's status or score change succeeds, a toast names the item and the change and
   carries *Undo* for its lifetime; *Undo* writes back the previous status, score and
   provisional flag in one `PATCH`. A failed undo says so and leaves the value.
3. The deck's undo restores the provisional flag too (closes Sprint 106's recorded deviation).
4. `POST /api/items/{id}/fill`: fetch from the item's primary provider and fill only empty
   fields (year, subtitle, metadata keys, cover when none), answering the item and the names
   filled. With no primary source, queue the domain's enrichment for that item and answer
   `queued`. A provider failure answers 502 and changes nothing.
5. *Edition facts* shows only fields with values. When any declared field is empty it ends with
   "N details missing" and *Fill from provider*, which reports what it filled ("Filled year and
   publisher", "Nothing new from Open Library", "Queued; this fills in the background").
   *Refresh from provider* stays, as the overwrite.

## Acceptance criteria

1. Undo after a card score change restores the previous score, including no score and a
   provisional score as provisional; after a status change, the previous status (Vitest, API).
2. A fill never changes a non-empty field (backend test with a recorded provider response that
   disagrees with a stored value).
3. An item without a primary source queues exactly one enrichment job for itself.
4. An item with every field filled shows no missing line and no fill button.
5. The library and detail Playwright specs that cover these screens pass; the accessibility spec
   passes on the detail page.

## Required tests (TDD)

- Backend: `PATCH` with `score_provisional`; `/fill` fills empties only, never overwrites, 502
  leaves the item, no-source queues one job.
- Vitest: the card undo toast and its write; the deck undo's provisional flag; the detail page's
  hidden empty facts, missing count and fill result copy.

## Verification

Per DEC-167: backend tests for the changed modules, `vitest related`, `make check`, the
Playwright specs covering the library cards and the detail page, and both screens in the
running app.

## Explicit non-scope

- Undo for bulk changes, deletion, notes or dates.
- A field-by-field choice of what to fill.

## Commit checkpoints

1. `[ADD]` undo on the card (API flag plus toast). 2. `[ADD]` fill from provider and the quieter
facts. 3. `[DOCS]` close.

## Risks and decisions to surface

- A toast stacked on a rapid series of changes: each change gets its own undo of its own
  previous value; undoing an older one after a newer one is allowed and writes that older value.

## Outcome

_Not started._
