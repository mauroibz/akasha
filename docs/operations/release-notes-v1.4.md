# Akasha v1.4 — release notes

**The movies release.** Sprints 045 through 048, developed on `sprint-045-movies` and merged in one
go, add movies as Akasha's fourth domain, import a Letterboxd library, and give films posters.

**Tagged `v1.4.0`** at the merge, after the owner's imported films were confirmed showing posters in
Triage and the Library.

## A note on versioning

`1.4.0` is a feature release on top of v1.3. **Nothing migrates.** There is no new schema revision
in this release at all — the movie domain, its importer and its posters are entirely application-level,
which is the domain contract working as designed. The pre-upgrade backup still runs on startup and
finds nothing to do.

The four version surfaces — `backend/pyproject.toml`, `frontend/package.json`, the FastAPI version
and the generated OpenAPI contract — say `1.4.0` together.

## What's new since v1.3.0

- **Movies are a full domain.** Search and add through Wikidata, which is keyless and CC0. A film has
  its own statuses, formats and metadata: Watchlist and Watched; streaming, digital, Blu-ray and DVD;
  directors, original title, countries, original languages, genres, runtime and a bounded cast list.
  A film is watched and rewatched but never *started* — nobody records the day they began a
  94-minute film — so the entry has a Watched date and Rewatches and no start date.
- **Spanish first.** Titles, descriptions, countries, languages and genres come back in Spanish with
  English as the fallback: `Metrópolis`, `cine de terror`, `República de Weimar`.
- **Paste almost any film link.** Wikidata, IMDb, TMDB and Letterboxd URLs all resolve, including
  short `boxd.it` links. IMDb, TMDB and Letterboxd have no adapter here — their links resolve through
  the exact identity claim Wikidata already holds, so nothing is scraped.
- **Letterboxd import.** Upload the export .zip exactly as it downloads. Watched films, ratings,
  diary entries, reviews, the watchlist and tags become one record per film. Half-star ratings double
  exactly onto Akasha's 1–10 — 3½ stars is a 7, and unlike a Goodreads star nothing is marked
  provisional, because nothing was lost. Repeated diary rows are rewatches rather than duplicates.
  Deleted and orphaned entries, comments, likes, lists and your profile are deliberately not read.
- **Posters.** Films get cover art from Stremio's image service, which needs no key and no setup.
  Wikidata has no posters and structurally cannot — they are copyrighted, and its own film-poster
  property covered one of eight films sampled.
- **Recognising a film you already have.** An imported film can be offered as a match for one you
  added by hand, on title plus exact year, scoped to movies. It is always a suggestion you accept,
  never an automatic merge — and a remake keeps its own row, because the year must match exactly.

## What the fourth domain proved

Movies, their importer and their posters were built with no migration, no domain-specific screen and
no branch on `item_type` in a shared layer. The registry-driven contract held for the second time in
a row: a package, a few registration points, and every screen renders it.

One shared behaviour did change, and deliberately: the import matcher gained a title-plus-exact-year
suggestion for sources that carry no creator, scoped to a single domain. Without that scope a film
diary would have offered to merge films into books, because a novel and its adaptation routinely
share a title and a year.

## Known limitations in this release

Stated plainly rather than left to be discovered:

- **Movie posters depend on a third party's undocumented service.** Stremio's image CDN publishes no
  terms and no support commitment. If it changes or blocks non-Stremio clients, films go back to
  being coverless and nothing else breaks.
- **TMDB content is cached past six months and shown without attribution**, outside TMDB's API terms.
  TMDB is used only as a poster fallback for the ~2% of films carrying a TMDB id and no IMDb id. This
  is a recorded owner decision (DEC-103), not an oversight.
- **A film's search results are capped at six.** Ten Wikidata entities measured 1.9 MB against a
  2 MiB response limit, so a search reads them in small batches (DEC-099).
- **`POST /api/enrichment/backfill` re-queues every movie on every call.** The backfill counts a
  missing cover as "worth a lookup" in every domain regardless of what that domain declared
  (DEC-100). Harmless unless called repeatedly.
- **A link to a film that does not exist reports a provider failure**, not "not found".
  `/api/search/resolve` maps every provider error to HTTP 502; it predates this release and affects
  every domain (DEC-100).
- **The Letterboxd connector's UI was not exercised in a browser** before release. Its reader,
  mapping, archive safety, matcher and enrichment are covered by tests and by a real import through
  the API, but nobody approved a movie row from the Triage screen or undid a Letterboxd batch there
  (DEC-102).

## Upgrading

Pull the new image and restart. No migration runs, no configuration changes, and no key is required
for anything in this release. `TMDB_READ_TOKEN` is optional and affects only the poster fallback
described above.
