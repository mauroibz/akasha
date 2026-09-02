# Sprint 062 — Search and add survive a provider having a bad day

**Status:** in_progress
**Depends on:** 046, 049, 050
**Roadmap revision:** 33

## Objective

Every domain's search returns results and every search result can be added, while three
external providers are simultaneously degraded — because that is the state they were
observed in on 2026-09-02, not a hypothetical.

## Required context

- `docs/decisions.md` DEC-098 (Wikidata as the movie domain's one adapter), DEC-103
  (the keyless Stremio poster), DEC-104 (the measured series providers), DEC-108 (the
  2026-08-31 maxlag incident and the walkthrough substitution it forced), DEC-115
  (fuller answers on the add path), DEC-025 (a mock of the unit under test does not
  prove a boundary).
- `docs/agent/TESTING.md` — the ladder, and "Gate scope by what changed".
- Code, read fresh: `backend/src/book_tracker/domains/movie/providers.py` (`_read`),
  `domains/series/providers.py` (`_read`, `_candidate`), `domains/series/tvmaze.py`
  (`_candidate`), `domains/album/providers.py` (`_json`),
  `application/add.py` (`_build`'s language fold), `api/library.py` (`refresh_item`'s
  identical fold), `application/providers.py` (`search_providers`'s timeout),
  `infrastructure/posters.py`, `infrastructure/providers.py` (the attempt budgets),
  `domain/spec.py` (`validate_metadata_patch`).
- Tests: `backend/tests/test_wikidata_provider.py`,
  `test_wikidata_series_provider.py`, `test_tvmaze_provider.py`,
  `test_musicbrainz_provider.py`, `test_cached_add.py`.

## Current implementation baseline

Observed live on 2026-09-02 against the running `ghcr.io/mauroibz/akasha:1.5.6`
container and confirmed against this worktree:

- **Wikidata refuses every read.** The query-service replica pool is chronically
  lagged (`wdqs1013` 16.6 s, then `wdqs1011` 15.7 s, `queryserviceLag` 944), and both
  adapters send a contractual `maxlag=5`. Wikimedia answers **HTTP 200 with an error
  object**, `_read` translates it to `ProviderPayloadError`, and movie search — a
  single-adapter domain — returns **503 `providers_unavailable`**. The identical query
  with `maxlag` removed returns results. This is DEC-108's incident recurring three
  days later, which makes it a chronic condition rather than an outage to wait out.
- **Series adds are refused, deterministically.** `tvmaze.py` hardcodes
  `language="en"`; `add.py` folds `payload.language` into the metadata patch for every
  domain; the series domain declares `languages` (many), not `language`. Live result:
  `POST /api/entries` → **422 `invalid_metadata`**, "Series metadata has no field named
  'language'". It has been latent since Sprint 050 because `wikidata-series` outranks
  `tvmaze` in `SERIES_IDENTITY` and its payload sets `language=None`, so the TVmaze
  branch is only reached when Wikidata is down — which is now. `test_cached_add.py`'s
  TVmaze double sets `language=None` while the real adapter sets `"en"`, which is
  exactly the DEC-025 failure mode; `test_tvmaze_provider.py` never asserts `language`.
- **A TVmaze-only series has no cover.** `tvmaze.py` sets `cover_url=None` reasoning
  that Stremio supplies the right variant, but only `series/providers.py` ever calls
  `metahub_poster_url`. TVmaze holds the IMDb id at that point and the builder is
  keyless and issues no request.
- **MusicBrainz throttling can fail an add.** MusicBrainz signals throttling with
  `503` (already recorded in `tests/fixtures/providers/README.md`), the album adapter
  makes two sequential paced reads per add, and `_json` spends only
  `INTERACTIVE_ATTEMPTS` (2). Observed: 5 `503`s in 47 requests, and one live
  `POST /api/entries` → **502 `provider_failure`**.
- **Kitsu times out inside its own budget.** `search_providers` bounds each provider at
  5 s. Five live Kitsu searches measured 3.5 s, 5.8 s, 5.4 s, 3.5 s, 4.4 s — two of five
  over budget. With AniList answering **403** ("The AniList API has been temporarily
  disabled due to severe stability issues"), Kitsu is the anime domain's only remaining
  provider, so a Kitsu timeout is an empty anime search.

## Deliverables

1. **Neither Wikidata adapter sends `maxlag`.** Both `_read` methods drop the
   parameter; `MAXLAG_SECONDS` goes with it. The error-block branch stays — Wikimedia
   can answer `200` with an error for other reasons, and that is still an outage.
2. **`SearchCandidate.language` reaches metadata only where the domain declares it.**
   `application/add.py` and `api/library.py` consult the domain's field spec before
   folding. This is the root defect: any provider setting `language` for a domain
   without that field breaks add the same way.
3. **TVmaze reports the language it actually observed.** `language="en"` is dropped;
   TVmaze's own `language` lands in `metadata["languages"]` as the domain's `many`
   field. Two recorded Argentine series and one French one prove the old value wrong.
4. **A TVmaze candidate carries the Stremio poster.** `_candidate` builds it from the
   IMDb id it already extracted; a show without one keeps `cover_url=None`.
5. **MusicBrainz reads get `PROVIDER_ATTEMPTS`.** A source that throttles by design,
   answers `503`, and sends `Retry-After` earns the full budget.
6. **The interactive search budget matches measured provider latency.**
   `search_providers`' default rises from 5 s to the `CANDIDATE_TIMEOUT_SECONDS` (10 s)
   the resolve path already uses, rather than a new constant.

## Acceptance criteria

1. Neither Wikidata adapter's request URL contains `maxlag`, and a recorded lag error
   body is still refused as an outage.
2. `POST /api/entries` for a TVmaze-sourced series succeeds and stores no `language`
   key; a book and an album still store theirs.
3. A recorded Spanish TVmaze series yields `metadata["languages"] == ["Spanish"]`; the
   English one yields `["English"]`.
4. A recorded TVmaze candidate with an IMDb id carries the `images.metahub.space`
   poster; the recorded one without an IMDb id carries `cover_url is None`.
5. A MusicBrainz read that answers `503` twice before succeeding returns a payload
   rather than raising.
6. `search_providers`' default budget is 10 s, and a provider slower than 5 s but
   faster than 10 s is included in the results rather than dropped.
7. Live proof, against the real providers, that movie search, anime search, album add
   and series add all work — the walkthrough gate, not the suite.

## Required tests (TDD)

| Behavior | Layer | File |
|---|---|---|
| No `maxlag` on a movie read; lag error still an outage | provider, replayed | `test_wikidata_provider.py` |
| No `maxlag` on a series read | provider, replayed | `test_wikidata_series_provider.py` |
| Spanish/English `languages` from a recording | provider, replayed | `test_tvmaze_provider.py` |
| Stremio poster with an IMDb id, `None` without | provider, replayed | `test_tvmaze_provider.py` |
| Series add from a TVmaze-shaped payload carrying `language` | application | `test_cached_add.py` |
| Book/album adds still store `language` | application | `test_cached_add.py` |
| MusicBrainz survives two `503`s | provider, replayed | `test_musicbrainz_provider.py` |
| A 6-second provider is not dropped from a search | application | `test_provider_search.py` |

Every provider assertion runs against a committed recording (DEC-025). The TVmaze
double in `test_cached_add.py` is corrected to match the real adapter, since its
divergence is what hid this defect.

## Verification

- `python scripts/validate_project.py`
- `make check`
- `make test`
- `make smoke-container`
- **Walkthrough (DEC-025):** against the running container and the live providers,
  search and add in all five domains; record what was seen, including anything that
  looked wrong and was out of scope.

`npx playwright test` is **not owed**: the diff touches no `frontend/src/` file, no
request path, and no screen. This is a claim about the diff and is checked against
`git diff --stat` at the freeze point, per `TESTING.md`.

## Explicit non-scope

- **A second movie provider.** Movie search is single-adapter by DEC-098, so a Wikidata
  outage is still a total outage for that domain. Removing `maxlag` removes the
  self-inflicted half of it; real redundancy is a sprint, not a fix.
- **Removing or replacing the AniList adapter.** Its API is disabled upstream with no
  stated end date. It fails fast, costs one wasted request, and Kitsu covers the
  domain. Re-check before building anything on it.
- **Making `/api/health/providers` reflect reachability.** It reports configuration, not
  liveness, and said `available: true` for AniList throughout. Worth fixing; not here.
- **Re-recording any existing fixture.**

## Commit checkpoints

1. `fix: stop sending maxlag on Wikidata reads`
2. `fix: fold a candidate language only where the domain declares one`
3. `fix: report TVmaze's own language and poster`
4. `fix: give MusicBrainz and slow providers room to answer`
5. `docs: close sprint 062 and hand off`

## Risks and decisions to surface

- **Dropping `maxlag` is a deviation from the contract Sprints 046 and 049 declared.**
  It needs a decision entry that supersedes rather than rewrites them. The argument:
  every call these adapters make is a read, Wikimedia's guidance aims `maxlag` at
  writes and bulk automated jobs, the lag being reported is the query service rather
  than the API serving the request, and the courtesy obligations are already met by the
  per-adapter pacing, the byte bound and the descriptive User-Agent.
- **Raising the search budget lengthens a hung provider's stall** from 5 s to 10 s. The
  providers run concurrently, and a dead provider observed here fails fast (AniList's
  403 lands in ~0.1 s); the bound only binds on a slow answer, which is the case it is
  being raised for.

## Outcome

_Not started._
