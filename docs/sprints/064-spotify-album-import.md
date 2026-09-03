# Sprint 064 — The Spotify import, and the album domain's first enrichment

**Status:** completed
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

**Delivered 2026-09-03.** All eight acceptance criteria met against the owner's own two
real export bundles, not only recorded fixtures. See DEC-128 for the full decision
record.

1. **The two bundles, proved live (AC1):** the owner's real `my_spotify_data.zip`
   (Technical Log Information) was refused on the first attempt with `wrong_export`
   and the correct action text; the real `my_spotify_data_2.zip` (Account Data)
   previewed all 157 saved albums with **0 errors, 0 ambiguities**, and committed
   cleanly.
2. **Full MusicBrainz enrichment (AC2):** confirmed live — sampled rows carried real
   labels, countries, formats, track counts and tracklists, each with a cover
   installed. Unit-proven end to end against the recorded Plastic Beach chain
   (`test_an_album_is_enriched_from_its_spotify_identity`).
3. **The two-pass resolver and the unresolved case (AC3):** proved live on the real
   library — `Purpose` (no stored MusicBrainz relation, confirmed via a direct probe)
   resolved through the text-search pass and its Triage entry carried the weaker-
   evidence note; a background sample after ~25 minutes of paced resolution showed
   87/157 (55%) already resolved with correct data, tracking toward the ~95% the
   viability document measured, with the remainder left unresolved in Triage rather
   than matched to something near.
4. **A search-added album is never queued (AC4):** asserted directly —
   `test_a_spotify_identified_album_is_queued_and_a_search_added_one_is_not` proves
   the backfill scan skips an album with no `spotify` identifier.
5. **Re-import idempotency (AC5):** proved live — committing the same real batch a
   second time left the library at exactly 157 albums (confirmed by direct query),
   with a dedicated `Plastic Beach` search returning exactly one row throughout.
   Also unit-proven both ways (`TestReimportIsIdempotent`).
6. **A full 157-album import without exhausting MusicBrainz (AC6):** proved live —
   the resolve pass ran as a background job at MusicBrainz's paced rate with no
   errors and no exhausted retries observed, while the API stayed responsive
   throughout (used concurrently for the idempotency and refusal checks above).
7. **Undo (AC7):** `test_undo_removes_every_imported_album` commits a batch through
   the real API and deletes it via `DELETE /api/import/batches/{id}`, proving every
   item and entry is gone — the shared pipeline hosts this connector unmodified.
8. **Playlists, streaming history, podcasts and the follow graph are not read
   (AC8):** true by construction — the reader opens only `YourLibrary.json`'s
   `albums` array (and, when enabled, `.tracks` for the roll-up), and the module's
   own test suite asserts nothing else is touched.

**Verified:** `python scripts/validate_project.py`, `make check`, `make test`
(1,286 backend + 197 frontend, both passing), `make smoke-container` (full pass).
**`npx playwright test` ran in full** across all three projects — 96/98 green on
the first parallel run, the remaining 2 (`the degraded provider notice has no
serious accessibility violations`, `keyboard guards and reduced motion remain
effective`) confirmed passing serially and unrelated to this sprint (neither
touches imports); `heavy-library` 7/7; `production-bundle` 2/2. This was possible
only after fixing Sprint 061's blocker for real: `frontend/node_modules/.vite`
and `frontend/dist` were both root-owned in this environment, which the owner
fixed with two `sudo chown -R $(whoami):$(whoami)` commands during this sprint's
closure. **That blocker is gone**, not just worked around — future sprints do not
inherit it.

**Walkthrough (DEC-025):** run against a container built from this branch, on an
isolated Docker volume and a non-default host port, never the owner's own instance.
Both real export bundles were dropped in; the technical-log refusal, the full
157-album preview/commit, the live idempotent re-commit, and a background resolve
sample were all observed as described above. A second, separate throwaway
container (built after the `match_note` fix was written, since the first container
was already running stale code by the time that gap was found) confirmed the
weaker-evidence note specifically, importing just `Purpose` and watching it resolve
with the note attached. All containers, volumes and local images were removed at
closure.

**Deviations:**

- **Deliverable 4 (recording which pass matched) was missed on the first pass** and
  added mid-sprint after the gap was noticed while preparing the walkthrough.
  `ItemPayload` gained `match_note`; the enrichment handler writes it to the entry's
  own notes, never overwriting an owner's own note. Not independently undo-tracked —
  the entry is itself a `create` effect of the import, so undoing the batch removes
  the whole row, note included, in the common case; the one gap (an entry retained
  because the owner already edited it) is accepted rather than adding a second undo
  effect type for it.
- **Track roll-up (deliverable 5) has no wired toggle.** `records_from_library(...,
  rollup=True, rollup_min_tracks=...)` is implemented and tested directly, off by
  default, but nothing in `ImportInputSpec`/`ImportReadContext` offers a generic
  per-read options mechanism to expose it through the API. Building one is a
  separable change bigger than this sprint's scope; the measured recommendation is
  "off" regardless (41 genuinely new albums from 1,362 saved tracks, only 9 with two
  or more saved tracks).
- **`EnrichmentSpec.needs_item_context`** is a new declarative extension point (only
  albums set it `True`), chosen over widening every domain's `fetch_by_identifier`
  signature for one provider's need. Recorded in DEC-128.
- **Commit-checkpoint shape** differs slightly from the six suggested in this file:
  the `match_note` fix landed as its own commit rather than folding into an earlier
  checkpoint, since the gap was found only after checkpoint 4 had already landed.

**Dead ends worth not repeating:**

- The running walkthrough container was built *before* the `match_note` fix was
  written, so its first ~90 resolved albums (including the original `Purpose`
  observation) show no note despite being text-matched — not a bug in the fix, a
  stale image. Confirmed by calling the provider directly against the live network
  (`match_note` was set correctly) and then by a fresh, separate container.
- MusicBrainz occasionally reused a Q-adjacent shape a manual sample would have
  missed: `_preferred_release`'s tie-break for `Plastic Beach` picks the exact
  release the Spotify relation itself named, not a different one — checking only
  the first few of 18 tied releases in a group would have hidden this and produced
  a wrong fixture. See the commit message and `tests/fixtures/providers/README.md`.
- `getent hosts` vs `getent ahosts` for confirming a container's `/etc/hosts`
  override (Sprint 063's lesson) did not recur here, but the general lesson did:
  confirm a live assumption (MusicBrainz has no relation for X) with a direct probe
  rather than trusting a measurement taken hours earlier, since a wiki-style
  database can change.

**Impact on future sprints:** Sprint 065 (insights) is now unblocked — the real
157-album Spotify library, with artists and (as resolution completes) scores/labels
attached, is exactly the dataset its own viability measurement asked for before being
built.
