# Sprint 054 — The Trakt import

**Status:** completed
**Depends on:** 049, 052, 053

**Roadmap revision:** 28

## Objective

A Trakt data archive becomes films in the Movies library and shows in the Series library, with each
show's watched episodes rolled up into the entry-progress count Sprint 040 built for exactly this.

## Required context

- `docs/series-domain-viability.md`, "Trakt — an archive of raw API responses": the member table, the
  identity blocks, the roll-up measurement and the list of members that must never be read.
- Sprints 052 and 053 Outcomes.
- `docs/decisions.md`: DEC-077 and DEC-092 (progress is one number with a floor and no ceiling),
  DEC-093, DEC-106.
- `backend/src/book_tracker/domains/movie/letterboxd.py` — the existing bounded-ZIP reader. Its
  refusals are the contract to follow: encrypted members, duplicate names, unknown paths, traversal,
  malformed UTF-8, missing required members, excessive expanded size.
- `backend/src/book_tracker/domains/anime/myanimelist.py` — the only existing reader that produces a
  progress count.

## Current implementation baseline

Observed at Sprint 053's closure, 2026-08-31: a multi-domain connector **is** a solved problem, and
IMDb proved it once. That connector is one module plus one line in `REGISTERED_IMPORTERS`, with no
change to `application/imports.py`, `api/imports.py`, `ImportPage.tsx` or `TriagePage.tsx`. Read
`backend/src/book_tracker/domains/movie/imdb.py` as the worked example; it is the nearest shape to
this one.

Three things it established that this sprint inherits rather than rebuilds:

- **Rows a reader cannot target are an `ImportSnapshot.skipped` tally by reason**, in the source's own
  word, reaching the preview as a count and never as a row error (DEC-112). Trakt's season and episode
  ratings map onto it the way IMDb's `Title Type` did.
- **A row names its own domain** through `NormalizedImportRecord.item_type`, and `match` should pass
  that row's type — not the connector's first — so a near-match offer is scoped correctly.
- **A domain enriches on every key its sources supply** (DEC-113). Both target domains resolve
  `imdb`, and a Trakt archive carries IMDb ids, so nothing further is owed here — but check it rather
  than assume it, which is what Sprint 053 had to do.

## Deliverables

### 1. The archive reader

One connector, `trakt`, declaring `item_types = ("movie", "series")`, over a ZIP of JSON members.

**Read, and nothing else:**

| Member | Produces |
|---|---|
| `watched-movies.json` | a movie per entry, watched |
| `ratings-movies.json` | the score for a movie |
| `watched-shows.json` | a series per entry, with `aired_episodes` as the episode total |
| `ratings-shows.json` | the score for a series |
| `watched-history.json` | the episode roll-up, and a watched movie the other members missed |
| `lists-watchlist.json` | a movie or series on the watchlist, **when present** |

**Never read, and each an explicit choice:** `user-settings.json` and `user-profile.json` (they carry
the owner's **email address**; no fixture may be cut from them), `ratings-seasons.json` and
`ratings-episodes.json` (a series holds one score — DEC-077's line, restated), collection, comments,
notes, likes, the follower graph, hidden items, playback progress and saved filters. Each of these is
a count in the report, not a silent omission.

The archive is a ZIP and the upload cap is on compressed bytes, so bound the decompressed stream
incrementally, per member and in total. A member that is absent is absent — the owner's own archive
has 26 empty members and no watchlist — and the reader must never require one it does not need.

### 2. The episode roll-up

`watched-history.json` is the only member with episode detail. Roll it up per show:

- Count **distinct `(show, season, number)`** with `action == "watch"`, not events: a rewatch is a
  second event for the same episode and progress means episodes, not plays.
- **Exclude season 0.** Specials are not part of the run, and counting them puts progress above the
  total for no reason a person would recognise.
- `progress` is that count. `episodes` metadata is the show's `aired_episodes` at export time.
- If `watched-history.json` is absent or holds no episodes for a show that `watched-shows.json`
  names, fall back to that show's `plays` and **record a warning on the row**. `plays` counts
  rewatches, so it is an upper bound rather than the same number, and a row that used it should say
  so rather than look identical to one that did not.

In the owner's archive the two agree exactly — 76 and 38 — which is precisely why the fallback needs
its own synthetic fixture: the real file will not exercise it.

### 3. Status, score and dates

- **Status** — a show whose distinct watched count is below its `aired_episodes` suggests `watching`;
  equal or above suggests `completed`; a watchlist-only entry suggests `plan_to_watch`. A movie
  suggests `watched`, or `watchlist` from the watchlist member. The reader cannot know whether a
  series has ended — that is a provider fact, not an export fact — so it does not guess; Triage is
  where a person decides, and enrichment brings `airing_status` afterwards.
- **Score** — `rating`, Trakt's 1–10 integer, mapped **1:1**. `rated_at` is available but the score
  is the score; a blank is unscored.
- **Dates** — the earliest of `last_watched_at` / `rated_at` / `listed_at` for that title becomes
  `date_added`. `last_watched_at` becomes the entry's finished date for a movie. For a series the
  latest `watched_at` across its episodes becomes the finished date only when every aired episode has
  been watched; a partially-watched show has progress, not a finish date.
- **Identity** — `ids.imdb`, present on every movie, show and episode object measured. `ids.trakt`
  and `ids.tmdb` are recorded as non-authoritative identifiers where the domain accepts them; the
  `plex` sub-object is not read.

### 4. The declaration

A guide in ordered steps — Trakt exports are a VIP feature and the steps must say so plainly rather
than sending a reader to a settings page they cannot use — an empty state, an `https` help link, the
closed error vocabulary, and the two target checkboxes.

## Acceptance criteria

1. An archive containing films and shows produces records of both types in one preview, and commit
   creates items in both libraries.
2. A show's progress is its **distinct** watched episodes, excluding season 0, and its `episodes`
   total is `aired_episodes` at export.
3. A rewatched episode does not inflate progress; a synthetic fixture with duplicate events proves it.
4. With `watched-history.json` absent, `plays` is used and the row carries a visible warning.
5. Progress above the stored total is stored and displayed rather than refused (DEC-092), proved with
   a fixture whose watched count exceeds `aired_episodes`.
6. Season and episode ratings are counted as not-imported and reported; they change no score.
7. `user-settings.json` and `user-profile.json` are never opened. A test asserts it.
8. An archive with 26 empty members and no watchlist imports cleanly — that is the owner's real shape.
9. Every archive refusal the Letterboxd reader makes, this one makes too.
10. Re-import matches on `imdb:` with no provider traffic; a film already imported from Letterboxd or
    IMDb matches exactly rather than duplicating.
11. **No change to `application/imports.py`, `api/imports.py`, `ImportPage.tsx` or `TriagePage.tsx`.**

## Required tests (TDD)

- The roll-up: distinct episodes, rewatches, season 0, a show in history but not in `watched-shows`,
  and the `plays` fallback with its warning.
- Status suggestion at partial, exact and above-total watch counts.
- Every archive refusal, one test each.
- The never-read members, asserted by an archive whose `user-settings.json` is deliberately malformed:
  if the import succeeds, nothing read it.
- Identity match against an existing Letterboxd-imported and IMDb-imported film.
- A generic route round-trip: preview, target selection, commit, undo.
- Every fixture **synthetic and invented**. The owner's archive contains their email address and is
  walkthrough input only.

## Verification

```bash
cd backend && uv run pytest tests/test_trakt_import.py tests/test_imports.py \
  tests/test_domain_conformance.py -q
cd frontend && npm run test
make check
make test
```

Then the walkthrough gate against the owner's real archive in `exports/`: preview, confirm the two
shows arrive with 76 and 38 episodes watched against their totals, commit, approve in Triage, see the
progress control render on the series detail page, and undo. Then re-import the IMDb export from
Sprint 053 and confirm the overlapping titles match rather than duplicate — the two sources describe
the same library and that is the interesting case, not the happy path.

## Explicit non-scope

- Seasons or episodes as entities, per-episode dates, or a calendar. The roll-up is one integer.
- Trakt's API, OAuth, or any live sync. This is an archive reader; a Trakt connector that talks to
  Trakt is a different thing and is not planned.
- Collection, comments, notes, likes, the follower graph, playback progress, hidden items.
- Anything from `user-settings.json` or `user-profile.json`, including the avatar.

## Commit checkpoints

1. `[ADD] Read a Trakt archive into movie and series records`
2. `[ADD] Roll watched episodes up into entry progress`
3. `[DOCS] Close sprint 054 and release`

## Risks and decisions to surface

- **`lists-watchlist.json` is empty in the owner's archive**, so its populated shape is taken from
  Trakt's published API and is **not measured**. Treat a mismatch as expected rather than surprising,
  and record the real shape in the Outcome once a populated one is seen.
- **`watched-history.json` may be truncated.** Trakt's history endpoint is paginated and an export of
  a large account may not carry every event. The `plays` fallback exists for that; a very large
  archive is where it will first matter.
- This is the last planned sprint. Closing it means the release decision — `v1.5.0`, release notes,
  and whether the movie line's v1.4.0 is tagged and pushed first — reaches the owner. Sprint 018's
  procedure is unchanged; nothing is pushed without being asked.

## Outcome

**Delivered 2026-08-31, commits `45fd3c4` and `a5f79d0`.** One connector, `trakt`, in
`backend/src/book_tracker/domains/movie/trakt.py` plus one import and one tuple entry in
`backend/src/book_tracker/domain/registry.py`. Nothing else changed: `application/imports.py`,
`api/imports.py`, `ImportPage.tsx` and `TriagePage.tsx` are untouched (AC11, verified by diff
against `7200758`), and neither is any other frontend or shared file.

**The reader.** Six members consumed; 31 counted-not-read members tallied by the source's own
word (`season rating`, `episode rating`, `collection entry`, `comment`, `note`, `like`, follower
graph, hidden items, playback progress); four never opened (`user-settings.json`,
`user-profile.json`, `user-last-activities.json`, `user-stats.json`). Every Letterboxd refusal
made, plus a not-a-list-of-objects refusal JSON needed. Bounded per member and in total, declared
sizes checked before decompression and re-checked mid-read. Scores map 1:1 with nothing
provisional; `rated_at` is not a viewing date; the `plex` sub-object is never read; `trakt`/`slug`/
`tmdb`/`tvdb` do not become authoritative identities.

**The roll-up.** Progress is distinct `(show, season, number)` with `action == "watch"`,
excluding season 0; `episodes` metadata is `aired_episodes` at export. The `plays` fallback fires
when history is absent or holds nothing for a show, is never clamped to the total (DEC-092), and
a row that used it carries the fact in its entry notes — a row *error* would block a healthy
commit, and the shared entry-value allowlist (`validate_entry_values`) owns what `values` may
hold, so the marker rides `source_fields["plays_used"]` instead.

**Tests.** `tests/test_trakt_import.py`: 80 tests, every fixture synthetic and invented — the
malformed-`user-settings.json` archive proves nothing reads the private members (AC7), the
26-empty-members shape imports cleanly (AC8), a rewatched episode does not inflate progress (AC3),
progress above the total is kept (AC5), season/episode ratings are counted not scored (AC6), and
the Letterboxd/IMDb identity matches are exact (AC10).

**Verification.** `make check` green (ruff format + lint, mypy, frontend types, OpenAPI, validator).
`make test` 1172 backend + 194 frontend, all green — the backend delta is exactly this sprint's 80
tests (1092 + 80). Serial Playwright 106 passed + 2 skipped (the parallel split remains never-green
until Sprint 055). The Verification block's `tests/test_imports.py` does not exist; the focused
suites run were `test_trakt_import.py`, `test_domain_conformance.py`,
`test_multi_domain_imports.py`, `test_generic_imports.py`, `test_imdb_import.py` and
`test_letterboxd_import.py` — 439 tests across the six files.

**Walkthrough gate, on the owner's real archive, live boundary, fresh backend per attempt.**
Two flows, both green:

- `scripts/walkthrough_trakt_054.py` (API, 27 checks): preview 3 rows 0 errors; BoJack 76/76 and
  Ted Lasso 38/38 with no `plays` fallback; both `completed`, film `watched` score 7, shows 10 and
  8; commit 3; inbox 3; stored progress 76/38; detail payloads carry progress and total; the IMDb
  ratings export previews its 2 overlapping rows as `reuse_item` and commits 0 items 0 entries
  (AC10's interesting case); undo takes back exactly the Trakt rows.
- `frontend/e2e/scratchpad/sprint54-walkthrough.spec.ts` (browser, 8.9 s): the Trakt tab renders
  both target checkboxes and the VIP note; the real archive previews 3 ready 0 errors; suggested
  statuses on the preview rows; commit; **all three rows approved through the Triage UI** with
  per-domain vocabulary; the progress control reads **"76 / 76 episodes"** on BoJack's detail
  page; the IMDb overlap commits without duplicating; both titles appear exactly once in their
  libraries.

**Deviations.** (1) The Verification block's `tests/test_imports.py` corrected as above — the same
miss Sprint 053 recorded. (2) AC4's "visible warning" is the row's `entry.notes` (rendered on the
Detail page and carried through the API) rather than a preview-screen element: a row error would
refuse a healthy commit and AC11 forbids a UI change, so notes are the one surface the sprint left
available. (3) The watchlist member's populated shape remains declared-not-measured; no populated
archive was available to measure against. (4) Two fixture-side test errors (colliding synthetic
titles, a wrong `plays` expectation) were corrected against the designed rules, not by weakening
any assertion.

**Observed, out of scope.** The owner's real archive's `user-last-activities.json` and
`user-stats.json` carry account telemetry this reader ignores like the two email members — a
deliberate extension of the never-opened list beyond the sprint's two, recorded here because the
sprint named only the pair. The Library's `?type=` scoping and the Import preview's non-rendering
of entry values are pre-existing screens this sprint did not touch.
