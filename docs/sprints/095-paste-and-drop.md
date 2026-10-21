# Sprint 095 — Paste and drop anywhere

**Sprint:** 095
**Status:** in_progress
**Roadmap revision:** 45
**Depends on:** 094
**Owner:** Mauro

## Objective

Hand Akasha anything, anywhere: pasting a link or ISBN outside a text field opens the command bar
already resolving it; dropping a file anywhere shows a drop veil, detects what the file is, and
routes it (an EPUB to quick add, an export to its importer). More links resolve: without a
scheme, Spotify albums (keyless oEmbed) and Goodreads books (title search), per DEC-165.

## Required context

- [`../production-grade-proposal.md`](../production-grade-proposal.md) §2.2 A3, A4, §2.3 I5,
  §4.2, §4.3, §5.2; DEC-165 point 4; DEC-167.
- `backend/src/book_tracker/domain/importers.py` (the `Importer` protocol, `BrowsableImporter`
  as the optional-extension precedent), every connector under `domains/*/`,
  `application/providers.py` (`resolve_input`, the recognisers), `api/imports.py`.
- Frontend: `features/command/`, `features/import/handoff.ts` (Sprint 086's file hand-off to
  Import), `pages/ImportPage.tsx`.

## Deliverables

1. `sniff(head, name) -> float` as an optional importer extension; `POST /api/import/detect`
   (multipart, first 64 KiB) returns connectors ranked by confidence, for the signals in §5.2.
2. A shell-level drop veil ("Drop to add") that sends the files to detect and hands them to the
   matching importer through the existing hand-off; several EPUBs go to the ebook connector.
3. Global paste outside a field opens the bar with the pasted text.
4. Resolution: scheme-less links normalised; `open.spotify.com/album/…` via oEmbed title then
   MusicBrainz search; `goodreads.com/book/show/…-slug` via title search.

## Acceptance criteria

1. Each §5.2 sample file is detected as its connector; an unknown CSV falls back to the custom
   list.
2. Dropping a Goodreads export on the Library lands on Import with the Goodreads preview loading.
3. Pasting `imdb.com/title/tt0111161` (no scheme) on the Library opens the bar on that record.
4. A Spotify album link resolves through recorded oEmbed and MusicBrainz responses.

## Verification

Per DEC-167, plus the route-structure tests (`test_library_api.py`, `test_isolation.py`,
`test_app_shape.py`) for the new route; `vitest related`, `make check`, the import and command-bar
specs, and a live paste of a real link.

## Explicit non-scope

The import screen's redraw (096); the phone share target (097).

## Outcome

_Not started._
