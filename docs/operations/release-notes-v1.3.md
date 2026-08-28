# Akasha v1.3 — release notes

**The anime release.** Sprints 038 through 043, developed on `sprint-038-anime` and merged in one
go, add anime as Akasha's third domain, import a MyAnimeList library, and turn Triage into one clear
decision per row.

**Tagged `v1.3.0`** at the merge after the owner's final Triage approval pass.

## A note on versioning

`1.3.0` is a feature release on top of v1.2. Nothing needs migrating by hand; migrations `0015`
and `0016` run on startup after the normal pre-upgrade backup. The first adds optional per-entry
progress. The second removes the database constraint that incorrectly froze import connector names.

The four version surfaces—`backend/pyproject.toml`, `frontend/package.json`, the FastAPI version and
the generated OpenAPI contract—say `1.3.0` together.

## What's new since v1.2.0

- **Anime is a full domain.** Search and add through AniList, with Kitsu as a fallback. Anime has
  its own statuses, formats and metadata: Watching, Completed, On hold, Dropped and Plan to watch;
  TV, movie, OVA, ONA, special and music video; studios, genres, season, episode count and duration.
- **MyAnimeList import.** Upload MyAnimeList's gzipped anime XML as downloaded, or unpack it first.
  Status, 1–10 score, dates, rewatches, watched episodes, notes and tags arrive in Triage. This is a
  safe snapshot rather than a two-way sync; a repeated import does not overwrite owner edits.
- **Useful records after a thin import.** Imported MAL ids enqueue background enrichment. AniList
  fills empty covers, studios, years, seasons, genres and synopses, with Kitsu as fallback, while the
  existing fill-empty-only rule protects anything already curated.
- **Progress belongs to the entry.** Anime can record watched episodes independently of the
  provider's total. Zero, unknown and a positive count stay distinct, and a stale provider total is
  never allowed to overrule the owner's number.
- **One Triage decision per row.** Inbox is implied rather than repeated. The status selector shows
  the imported suggestion or domain default, and a quiet dark button with a yellow check commits
  that row. There is no second Apply/Discard bar. Uncommitted targets survive navigation and refresh
  within the browser tab; failures remain ready to retry. Explicit checkbox bulk actions remain.

## What the third domain proved

Anime and its importer were built without a domain-specific screen or a branch on `item_type` in a
shared layer. The registry-driven contract held: the domain was a package plus small registration
points, and the MyAnimeList connector was one implementation plus one registry tuple. The shared
work this line did was for reusable capabilities—non-ISBN enrichment and optional progress—not for
anime special cases.

The database did expose one old coupling: import batch kinds were frozen to Goodreads and Calibre.
Migration `0016` removes that vocabulary constraint so the next connector does not require a schema
change. The next planned sprint sharpens the mechanical safeguards found during this trial.

## Known and left

- **MyAnimeList manga exports are deliberately refused.** Manga would be another domain, not anime
  rows with different labels.
- **Import is a snapshot.** Re-import adds missing records and never refreshes an existing entry's
  watched-episode count; explicit owner changes remain authoritative.
- **Watched-episode progress is visible on cards and Detail, not in the dense Triage row.**
- **Some Kitsu records have no studio data**, and its production list can include publishers; AniList
  remains primary for that reason.
- A filtered Triage search whose last row leaves still says `Inbox is clear` although other rows may
  exist, and `Accept all suggested` can remain visible on a filtered result with no suggestions.
- v1 still has no authentication. Keep Akasha on a trusted LAN, never the public internet.
