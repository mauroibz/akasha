# Sprint 064 — The Spotify import, and the album domain's first enrichment

**Status:** in_progress
**Depends on:** 025, 026, 031, 052, 061, 062
**Roadmap revision:** 35

## Objective

An owner drops Spotify's account-data export into the Import screen and their saved albums
arrive in the library with real MusicBrainz metadata, covers and tracklists — measured at
roughly 95% resolving to an exact release, with the remainder going to Triage rather than
being guessed at.

## Required context

- `docs/spotify-import-and-insights-viability.md` — **read first.** Every number in this
  sprint comes from there, including which of the two Spotify exports is usable.
- `docs/decisions.md` DEC-052 (albums have no cross-provider identity, and why),
  DEC-076 (Spotify is an architecture goal, not a commitment), DEC-077 (a track is
  metadata on the album, not a child entity), DEC-080 (a connector is a package, not a
  patch to `ImportPage.tsx`), DEC-082 (planning by identity), DEC-113 (why
  `identity_kinds` is a tuple: a domain's sources supply different keys), DEC-116,
  DEC-125 (MusicBrainz throttles with `503`, and the retry budget that survives it).
- `docs/specs/technical-spec.md` §6.5 (imports) and §7.1.
- Code, read fresh: `domain/importers.py` (`ImportInputSpec`, `NormalizedImportRecord`,
  the `export` kind Sprint 061 added), `domains/movie/trakt.py` and
  `domains/movie/letterboxd.py` (the two zip readers, and the closest models),
  `domains/album/providers.py` (`MusicBrainzProvider`, `_json`'s pacing and retry),
  `domains/album/__init__.py` (`ALBUM_IDENTITY`, and `enrichment=None` — which this
  sprint changes), `application/enrichment.py`, `application/imports.py`,
  `domain/spec.py` (`EnrichmentSpec`).
- Tests: `test_trakt_import.py` (the model), `test_musicbrainz.py`, `test_enrichment.py`,
  `test_import_contract.py` / `test_domain_conformance.py`.

## Current implementation baseline

Measured 2026-09-02 against the owner's own export and live MusicBrainz; the viability
document holds the full tables.

- **The export is a zip, and there are two of them.** Only *Account Data* is usable.
  *Technical Log Information* looks like a library — it contains 291 `spotify:album:`
  URIs — but they are recommendation-carousel impressions (`discover-weekly`,
  `release-radar`, `made-for-x-dailymix`) totalling 28 distinct albums. It must be
  refused by name, not scavenged.
- **`YourLibrary.json` carries `albums` with an exact `spotify:album:` URI** — 157 in the
  owner's library — plus 1,362 saved `tracks` that carry only track URIs and album
  *names*.
- **Spotify ids resolve to MusicBrainz releases through MusicBrainz's own URL
  relationships**: `GET /ws/2/url?resource=https://open.spotify.com/album/<id>&inc=release-rels`.
  44 of 60 sampled (**73%**) resolved exactly. A `releasegroup:"…" AND artist:"…"` search
  recovered **10 of the remaining 16**. Combined: ~95% exact, ~5% for Triage.
- **The album domain declares `enrichment=None`**, on the reasoning that one MusicBrainz
  fetch already returns everything an album has. That premise holds for a search-added
  album and fails for an imported stub — which is exactly the case `BOOK_ENRICHMENT`
  exists for. **This is the sprint's one structural change.**
- **`MusicBrainzProvider` does not implement `fetch_by_identifier`.** It is on the
  `Provider` protocol and every enriching domain's adapter has one; the album adapter
  never needed it.
- **No new `ImportInputSpec.kind` is needed.** Sprint 061 added `export` for "a small set
  of opaque files a source's own export produced", and Trakt and Letterboxd already read
  zips through `upload`. DEC-076's worry that Spotify would need an OAuth input does not
  apply to a file drop.

## Deliverables

1. **`domains/album/spotify.py` — `SpotifyImporter`.** Reads the account-data zip, takes
   `YourLibrary.albums`, and emits one `NormalizedImportRecord` per saved album carrying
   the title, the artist, and `identifiers={"spotify": "<id>"}`. It refuses the
   technical-log bundle with a typed error naming the export to request instead, and
   refuses a zip carrying neither. Guidance (`guide`, `help_url`, `empty_state`) is the
   connector's own, per DEC-080.
2. **`ALBUM_ENRICHMENT`, replacing `enrichment=None`.** `identity_kinds=("spotify",)` —
   a search-added album carries no `spotify` identifier and so is never queued, which
   preserves the original decision exactly where it was right. `provider_order=
   ("musicbrainz",)`. `completeness_fields` chosen from what an imported stub genuinely
   lacks and a resolved album genuinely has, so a legitimately empty field never
   re-queues a row for ever (DEC-116).
3. **`MusicBrainzProvider.fetch_by_identifier("spotify", value)` — the two passes.**
   First the URL relation; on a miss, a `releasegroup:"…" AND artist:"…"` search accepted
   only on an exact normalized title-and-artist match. Anything weaker raises
   `record_not_found`, which is an answer and not an outage. Both passes go through the
   existing paced, bounded, retrying `_json`.
4. **The resolution pass records which one matched.** A URL-relation match and a text
   match are different strengths of evidence, and Triage should be able to say which it
   is rather than presenting them identically.
5. **Track roll-up, opt-in and threshold-gated, defaulting to off.** The measurement is
   why it is not the default: rolling up 1,362 saved tracks adds 41 albums, of which 9
   have two or more saved tracks and 4 have three or more. The rest are albums where the
   owner saved one song, which is a statement about a song.

## Acceptance criteria

1. Dropping the account-data zip previews the saved albums with title and artist, and
   commits them; dropping the technical-log zip is refused with a message naming the
   correct export. Both proved against the owner's two real files.
2. An imported album with a `spotify` identifier is enriched to full MusicBrainz metadata
   — creators, label, country, format, track count and tracklist — with a cover installed.
3. A `spotify` id with no MusicBrainz URL relation but an exact title-and-artist match
   resolves through the second pass; one with neither is left as an unresolved row in
   Triage, not silently dropped and not matched to something near.
4. **A search-added album is never queued for enrichment.** It carries no `spotify`
   identifier, and this must be asserted rather than assumed — it is the whole reason
   `enrichment=None` was right before this sprint.
5. Re-importing the same export creates no duplicates: the second run matches the existing
   items through `item_sources`/`item_identifiers`.
6. A full 157-album import completes without exhausting MusicBrainz: the resolve pass is
   paced and runs as a background job, and the screen shows progress rather than blocking.
7. Undo reverses a Spotify import exactly as it reverses a Trakt one.
8. Playlists, streaming history, podcasts and the follow graph are not read.

## Required tests (TDD)

| Behavior | Layer | File |
|---|---|---|
| `YourLibrary.albums` → records with a `spotify` identifier | importer | `test_spotify_import.py` (new) |
| The technical-log bundle is refused by name | importer | `test_spotify_import.py` |
| A zip with neither shape is refused | importer | `test_spotify_import.py` |
| Roll-up is off by default; on, it honours the threshold | importer | `test_spotify_import.py` |
| URL-relation resolve, from a recorded response | provider, replayed | `test_musicbrainz.py` |
| Text fallback accepted only on an exact match; near miss raises `record_not_found` | provider, replayed | `test_musicbrainz.py` |
| A `spotify`-identified stub is queued; a search-added album is not | application | `test_enrichment.py` |
| Re-import is idempotent | application | `test_spotify_import.py` |
| The connector satisfies the import contract | conformance | `test_import_contract.py` |

Provider assertions run against committed recordings captured in their own commit
(DEC-025). **Any test double must match the adapter it stands for** — Sprint 062's lesson.

## Verification

- `python scripts/validate_project.py`, `make check`, `make test`, `make smoke-container`
- `npx playwright test` — **owed**, because a connector adds a tab to the Import screen.
  Sprint 061's blocker is a prerequisite: `frontend/node_modules/.vite/deps` is owned by
  `root`, which stops Vite's dev server and Playwright's `webServer`. Fix the ownership or
  record the gate as blocked; do not quietly skip it.
- **Walkthrough (DEC-025):** drop the owner's real `my_spotify_data_2.zip` into the running
  container, watch the resolve job, and inspect what landed — including at least one row
  that resolved by text rather than by relation, and the unresolved rows in Triage.
  **Also drop the technical-log bundle** and confirm the refusal reads clearly. The
  owner's export is private, gitignored, and never committed as a fixture; the suite uses
  hand-built bundles matching the verified structure, exactly as Sprint 061 did.

## Explicit non-scope

- **The Spotify Web API and OAuth.** The better long-term product and a much larger sprint
  — token storage, refresh, and a new input kind. Nothing here blocks it: both paths
  produce the same normalized album rows.
- **Playlists** (345 further albums, on the strength of one track appearing in a list),
  **streaming history** (one row in this export; the fuller data is a separate, slower
  Spotify request), **podcasts** (no domain), **the follow graph**.
- **Importing tracks as entities.** Rejected by DEC-077 and not reopened.
- **Reopening DEC-052's `no_shared_identity`.** This sprint adds an enrichment key, which
  is a different thing from a merge identity: `spotify` keys a *lookup*, and two search
  candidates still merge on nothing.
- **Insights.** Sprint 065.

## Commit checkpoints

1. `[TEST] Record MusicBrainz's Spotify URL relations`
2. `[ADD] Resolve a Spotify album id to a MusicBrainz release`
3. `[MOD] An imported album is worth enriching`
4. `[ADD] Import a Spotify library from its account export`
5. `[DOCS] Close sprint 064 and hand off`

## Risks and decisions to surface

- **Giving albums an `EnrichmentSpec` reverses a deliberate decision** and needs an entry
  superseding the `enrichment=None` reasoning without rewriting it. The original premise
  was true for the only way an album could then be created; an importer is a second way,
  and AC4 is what keeps the original case unchanged.
- **157 albums is one library.** The 73%/95% figures are the owner's own collection,
  skewed to popular and Latin American music. Re-measure before treating them as general,
  and expect the text-fallback share to be higher for obscure catalogue.
- **The resolve pass is long.** MusicBrainz is paced at roughly one request per second, so
  157 albums is minutes, and a text fallback doubles the calls for those rows. It must be
  a background job with visible progress — Sprint 059's offload seam and the existing
  import-job machinery are the tools. It must also survive throttling: DEC-125 raised the
  album adapter to the full retry budget for exactly this reason.
- **A text match is weaker evidence than a relation match**, and presenting them
  identically would hide a guess. Deliverable 4 exists so the distinction survives into
  Triage; if that proves noisy in the walkthrough, say so rather than dropping it.

## Outcome

_Not started._
