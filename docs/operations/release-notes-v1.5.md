# Akasha v1.5 — release notes

**The series release.** Sprints 049 through 055, developed on `sprint-049-series` and merged in one
go, add television series as Akasha's fifth domain, import a Trakt library and an IMDb account, roll
watched episodes into a progress count, and close every defect the line recorded — plus the three
places the verification gates were costing more than the evidence they bought.

**Tagged `v1.5.0`** at the merge, after the plan's 55 sprints completed back to back.

## A note on versioning

`1.5.0` is a feature release on top of v1.4. **Nothing migrates.** The series domain, both import
connectors, the episode roll-up and every defect fix are application-level; the domain contract is
now four-for-four on shipping a domain with no schema change. The pre-upgrade backup still runs on
startup and finds nothing to do.

The version surfaces — `backend/pyproject.toml`, `frontend/package.json`, the FastAPI version and
the generated OpenAPI contract — say `1.5.0` together.

## What's new since v1.4.0

- **Series are a full domain.** Search and add through Wikidata with TVmaze as the fallback — both
  keyless — and paste almost any series link: Wikidata, IMDb, TMDB, TVDB and TVmaze URLs all resolve
  through the exact identity claims Wikidata already holds. A series has its own statuses (Watching,
  Completed, On hold, Dropped, Plan to watch), its own formats, and its own metadata: creators,
  original title, countries, languages, genres, episode and season counts, episode length, network,
  airing status, cast and synopsis. Two providers means one film reachable two ways: an IMDb id
  matches exactly, whichever source a row arrived from.
- **Episode progress.** The count you're at, one integer on the entry — "76 / 77 episodes". It comes
  from a Trakt archive's watch history (distinct episodes watched, rewatches counted once, specials
  left out) or a MyAnimeList export, and it is never capped by the total: an airing series' cached
  total is stale by definition, so the reader's number always wins.
- **The Trakt import.** Upload the export .zip exactly as it downloads. Watched films and shows,
  ratings, the watch history's episode roll-up and the watchlist become records in both the Movies
  and Series libraries from one archive. Trakt's 1–10 scores map 1:1 with nothing marked
  provisional. Season and episode ratings are counted and skipped — a series holds one score — and
  the archive's account-settings members, which carry your email address, are never opened (a test
  proves it). A show whose history is missing falls back to Trakt's play count and says so on its
  row.
- **The IMDb import.** Both export shapes — a ratings CSV and a list CSV — in one connector, with
  films and shows routed to their libraries by `Title Type` and anything Akasha doesn't hold
  counted on the preview screen rather than failed. Your ratings come across exactly.
- **A real synopsis.** A series stores the synopsis somebody would actually read: when Wikidata's
  one-line description and TVmaze's full synopsis disagree, the fuller answer wins for that field —
  declared per domain, never "the last provider wins", and your own text is untouchable however
  short. The same rule runs whether a series arrived by search or by import.
- **Smaller repairs that were recorded, not left.** A pasted link that names nothing now reads
  "not found" instead of a provider outage. The background backfill no longer re-queues rows for
  ever on conditions a domain never declared.
- **Faster verification for whoever builds next.** The parallel browser gate is green and is the
  gate (about 44 s against 102 s serial); coverage is charged to the exhaustive run and an on-demand
  target, not to every focused test run; the lint gate no longer polices local walkthrough files;
  a green frontend unit run is silent.

## Upgrading

Nothing migrates and nothing new is configured. Pull, rebuild the container, and the existing
database opens as-is. The two new import tabs (IMDb, Trakt) appear on the Import screen; a Trakt
export is a VIP feature on trakt.tv and the guide says so.

## What this release deliberately does not do

- **Seasons and episodes are not entities.** A series is one item with one progress count; the
  watched-episode detail lives in the import, not in the library.
- **No Trakt or IMDb sync.** Both connectors read an archive; a connector that talks to the service
  is a different thing and is not planned.
- **No new auth.** v1 remains LAN-only, by design.
