# Sprint 099 — More importers

**Sprint:** 099
**Status:** completed
**Roadmap revision:** 45
**Depends on:** 098
**Owner:** Mauro

## Objective

More of the places people keep their lists can be imported: StoryGraph and Hardcover for books,
AniList for anime, Simkl for films and series (proposal §7).

## Required context

- [`../production-grade-proposal.md`](../production-grade-proposal.md) §7; DEC-025 (recorded real
  responses), DEC-167.
- `backend/src/book_tracker/domains/book/goodreads.py` (the CSV-on-ISBN shape),
  `domains/anime/myanimelist.py`, `domains/movie/trakt.py`, `domain/registry.py`.

## Current implementation baseline

Nine connectors; none for StoryGraph, Hardcover, AniList or Simkl. No real export from any of the
four was available on this machine when the sprint ran.

## Deliverables

1. A StoryGraph CSV connector.
2. AniList: its MyAnimeList-format XML export through the existing MyAnimeList connector.
3. Hardcover and Simkl connectors, only against a real export.

## Acceptance criteria

1. A StoryGraph export previews and commits into the book domain, with ratings, statuses, dates
   and tags mapped.
2. An AniList export in MyAnimeList XML reads through the MyAnimeList connector.
3. No connector is built against a guessed format.

## Verification

Per DEC-167: the connector's tests, the conformance and generic import suites, `make check`, and
the import spec.

## Outcome

Delivered 2026-10-21 in part. Verified per DEC-167: `test_storygraph_import.py` (5), the
conformance, generic-import, detection and every connector's suites (431), `make check`, the
triage and import specs (44).

- **AC1.** `storygraph` connector: ISBN/UID becomes an ISBN only when it is one; quarter-star
  ratings double and round half up (Python's `round` is banker's: 4.25 had become 8) and are
  provisional; Read Status maps read/reading/to read/dropped; tags become shelves; only the mapped
  columns are required. Sniffed by `ISBN/UID` + `Read Status`. **Built from StoryGraph's
  published header, not from a recorded export**: confirm against a real file.
- **AC2.** AniList's list in MyAnimeList XML has the `<myanimelist>` root the MyAnimeList
  connector reads; its guide says so. No separate connector.
- **AC3. Hardcover and Simkl are not built**: no real export was available, and a connector
  written against a guessed format is the failure DEC-025 forbids. Waiting on the owner for a
  sample of each.

Also: every connector guide and the Inbox page said "Triage" after 096's rename; they say Inbox.
**Bookkeeping slip:** this sprint's commit (`4ce1768`) went in while the state still named 098
active; 098 was closed and 099 activated afterwards, in that order, by the sync script.
