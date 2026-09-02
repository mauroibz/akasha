# Akasha v1.5.7 — release notes

**Carries two sprints.** Sprint 061 (the Calibre export bundle) landed on `main` after `v1.5.6`
was published but was never released on its own, so it ships here alongside Sprint 062's
provider repairs. If you are upgrading from `v1.5.6`, both sections apply.

## From Sprint 062: search and add survive a provider having a bad day

Three external providers were degraded at the same time on 2026-09-02, and each one uncovered
something standing behind it. If movies and anime were returning nothing, albums and series were
searching but refusing to add, and series had no cover art, this is the release that fixes it.

- **Movie search works again while Wikidata's query service is behind.** Wikidata's replica pool
  has been running 15–17 seconds lagged, and both Wikidata adapters sent a `maxlag=5` courtesy
  parameter that made Wikimedia refuse every single read. Because movies are served by that one
  adapter, every movie search returned "Every enabled metadata provider failed". The parameter
  is meant for writes and bulk jobs, and the lag it answers to belongs to a different service
  than the one answering our reads, so it is gone from both adapters. The pacing, the response
  bound and the identifying User-Agent that these adapters actually owe are unchanged.
- **Series can be added again.** Adding a series found through TVmaze failed with "That could
  not be added" — the provider reported a language, and the series library has no field by that
  name, so the whole record was refused. A provider's language is now stored only by the
  libraries that have somewhere to put it. This had been broken since TVmaze was added, and only
  became reachable when Wikidata stopped answering.
- **Series show their cover art.** A series that only TVmaze knows about arrived with a blank
  tile, because the poster was only ever being built on the Wikidata path. Both paths build it
  now, from the IMDb id the record already carries and with no extra request. A title with no
  poster available is still shown without one.
- **TVmaze series carry the right language.** The adapter labelled every show English regardless
  of what TVmaze said, so Argentine, Japanese and French series were all filed as English.
- **Albums stop failing to add when MusicBrainz is busy.** MusicBrainz throttles by design and
  says so with a 503; the album reader gave up too early and turned that into "That could not be
  added". It now waits the way the rest of the application already does.
- **Anime search stops coming back empty.** AniList has disabled its public API upstream, which
  leaves Kitsu answering alone — and Kitsu was being cut off by our own five-second timeout
  before it could reply, since it regularly takes four to six seconds to start answering. Both
  the search budget and Kitsu's own are now sized above what it actually takes.

Nothing about this release changes a screen, a setting or a stored record. Existing libraries,
backups and imports are unaffected.

**Still true after this release:** movie search is served by Wikidata alone, so a genuine
Wikidata outage still leaves that library unsearchable. AniList's API is disabled upstream with
no stated return date, so anime search rests on Kitsu, and a Kitsu slow enough to exceed its
budget still produces an empty search.

## From Sprint 061: drag Calibre's own export bundle into the Calibre tab

A third way into the Calibre tab, beside the folder picker and the mount: drop in the
`part-NNNN.calibre-data` files that Calibre's own *Export/import all calibre data* produces, and
get the same preview, commit and undo every other Calibre path already has.

- **Ebooks attach automatically on this path**, because an export already contains the files —
  unlike a folder upload, where the browser never had the bytes to begin with.
- **Every reconstructed byte range is hash- and bounds-checked** before anything is written, and
  a reconstructed book path is confined to the library root the same way a read-side Calibre
  path already is.
- **Multi-library exports are refused rather than guessed at**, and `notes.db`, Calibre custom
  columns and plugin configuration are still not read.

Note that dragging an export uploads the entire library, ebook files included — 181 MB for an
18-book library of mostly text epubs, in the real sample this was verified against. The manifest
that would let the browser filter first is itself inside the upload.

## Upgrading

```bash
docker compose pull
docker compose up -d
```

No migration runs, no configuration changes, and a rollback to `v1.5.6` needs nothing but the
version pin.
