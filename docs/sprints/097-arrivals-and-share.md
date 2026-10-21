# Sprint 097 — Arrivals and the share target

**Sprint:** 097
**Status:** in_progress
**Roadmap revision:** 45
**Depends on:** 096
**Owner:** Mauro

## Objective

After an import, you watch it land: covers fill in as enrichment finishes, with a count of how
many are in. On an Android phone Akasha appears in the share sheet, so sharing an IMDb, Letterboxd
or Spotify page adds it. The app installs as a PWA with an offline shell.

## Required context

- [`../production-grade-proposal.md`](../production-grade-proposal.md) §2.3 I6, I7, §4.2 (share
  target), §5.1 (Done step), §5.3; DEC-165 point 3; DEC-167.
- `frontend/src/pages/ImportPage.tsx` (the result panel), `features/activity/` (the job stream),
  `features/command/` (the bar), `public/manifest.webmanifest`, `src/main.tsx`.

## Current implementation baseline

The result panel says how many entries were added and links to the Inbox; nothing shows
enrichment arriving. There is no service worker and no `share_target`.

## Deliverables

1. **Arrivals.** The result panel gains a strip of the batch's newest Inbox entries whose covers
   fill in as the batch's enrichment jobs finish (job events), with "N of M details in".
2. **Share target.** `share_target` (GET) in the manifest to `/share`, which opens the command bar
   with the shared URL or text; a service worker caching the app shell (network first), registered
   only in production over a secure context.
3. **Trust stated status (proposal §5.3, I7).** Not built: DEC-165 point 3 says the owner decides
   first. Recorded for the owner.

## Acceptance criteria

1. Committing an import shows the arrivals strip, and covers appear without a reload.
2. Opening `/share?url=https://www.imdb.com/title/tt0111161/` shows the bar resolving that link.
3. The production build registers the service worker; the dev server does not.

## Verification

Per DEC-167: `vitest related`, `make check`, the import and command-bar specs, a production build
check for the service worker, and a live import watched to completion.

## Explicit non-scope

Trust stated status (awaiting the owner); offline data (the shell only).

## Outcome

_Not started._
