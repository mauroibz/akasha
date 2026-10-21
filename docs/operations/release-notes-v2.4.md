# Akasha v2.4.0 — release notes

The production-grade release (DEC-165): a new look, one place to type anything, a redrawn
import, and the plumbing underneath made dependable. Sprints 087–101.

## What you will notice

- **Two themes.** *Ink* (a warmer dark) and *Paper* (warm light), chosen in Settings and
  following the device by default. Titles use a display serif. Every control, select, file
  input and loading state is drawn for both themes.
- **The detail page** shows your reading data as property rows, the way the approved mock
  drew it. A cover grows into its detail page and back; lists and pages enter instead of
  appearing.
- **The command bar.** `Ctrl+K` (`⌘K`), `/` or the search control opens one bar that finds
  things in your library, searches the web per library with an explicit *Add*, turns a pasted
  link or ISBN into a single confirm card, and runs actions (go to a page, import, switch
  theme, new shelf, open a saved view). Adding no longer lives in the library's filter box.
- **Paste and drop anywhere.** Pasting a link or ISBN outside a text field opens the bar
  already resolving it. Dropping a file anywhere routes it: an EPUB to quick add, an export to
  its importer. Links without `https://`, Spotify albums and Goodreads books now resolve.
- **Better library search.** Search finds a title by any creator, series, subject, genre or
  your own note, ignoring accents.
- **Activity.** Background work shows as a small indicator in the shell, fed by a live event
  stream; after an import, covers fill in as enrichment finishes, with a count.
- **Import, redrawn.** One *Import* entry in the navigation, carrying the Inbox count (Triage
  is now called *Inbox*). A drop area over a grid of source cards, a check step that shows
  covers and titles, and Export moved to Settings.
- **New importers.** StoryGraph CSV. AniList works through its MyAnimeList-format XML export.
  The StoryGraph importer was built from StoryGraph's published header, not a real export, so
  please report a file it misreads.
- **Now and Diary.** The library opens on a *Now* strip of everything in progress across every
  library, with one tap to advance it. *Diary* shows what you finished, month by month.
- **Move to another library.** An entry filed in the wrong library (a series that is really
  anime) moves from its detail page, keeping status, score, notes, dates and shelves. Formats
  the new library does not have are dropped. Moving back is a second move.
- **Saved views.** *Save view* at the end of the library's filter chips keeps the current
  filters under a name; saved views are in the command bar.
- **On a phone.** At phone width the header is one short band, the grid shows two covers a
  row, and dialogs rise as bottom sheets.
- **Installable app and share target.** Akasha is a PWA with an offline shell, and on Android
  it appears in the share sheet for IMDb, Letterboxd and Spotify links. Browsers only allow
  this over HTTPS, so a plain-HTTP LAN install does not get it.

## Under the hood

- Background jobs no longer lose an attempt to their own bookkeeping, and the request path no
  longer runs blocking database work on the event loop.
- Every error the browser sees has one shape and carries a request id that matches the log
  lines explaining it.
- The browser's API client is generated from the server's OpenAPI document, so a contract
  drift fails the build.
- Provider health reports whether each provider is answering (`working`, `degraded`, `down`),
  from its recent calls. The Add page names a provider that has stopped answering.
- The same provider search within 24 hours is answered from a cache.
- `AKASHA_METRICS=on` serves Prometheus text at `/metrics`: queue depth, job outcomes,
  provider calls and timings, request timings. Off by default.

## Fixed in this release

- `AKASHA_METRICS` and `AKASHA_PROVIDER_DAILY_LIMITS` were documented in `.env.example` but
  `compose.yaml` did not pass them to the container, so setting them in `.env` did nothing. They
  are passed now, and a test fails if a future setting is missed the same way.

## Upgrade

**Tagged `v2.4.0`.** Minor release: three migrations (`0023` search index, `0024` saved views,
`0025` provider response cache), no breaking change, no owner action. Startup takes a
pre-migration backup before applying them.

If you track the `compose.yaml` from the repository, fetch the new one: it carries the two
settings above.

```bash
docker compose pull && docker compose up -d
```

If you pin in `.env`, move the pin to `AKASHA_VERSION=2.4.0` (or track the `2.4` line).
