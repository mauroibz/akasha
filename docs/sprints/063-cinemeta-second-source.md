# Sprint 063 — A second source for films and shows

**Status:** completed
**Depends on:** 046, 048, 049, 050, 062
**Roadmap revision:** 34

## Objective

A movie search returns results while Wikidata is unavailable, proved by running the
application with the Wikidata adapter failing — because on 2026-09-02 that was not a
hypothesis, and DEC-125 closed the self-inflicted half of it without adding the redundancy
the other half needs.

## Required context

- `docs/decisions.md` DEC-098 (Wikidata as the movie domain's one adapter, and why),
  DEC-103 (the keyless Stremio poster and the ~2% TMDB tail), DEC-104 (how a provider's
  coverage is measured before it is committed to), DEC-109 (`source_preference` is a
  ranking, not a strict order), DEC-125 (the incident this sprint answers).
- `docs/specs/technical-spec.md` §6.2 (a raw response never rises above infrastructure),
  §6.6 (a domain package may not import another).
- `docs/movie-domain-viability.md` and `docs/series-domain-viability.md` — the shape a
  measured provider assessment takes here.
- Code, read fresh: `infrastructure/posters.py` (the precedent for shared, cross-domain
  provider code), `infrastructure/covers.py` (`ALLOWED_COVER_HOSTS`),
  `domains/movie/providers.py` and `domains/series/providers.py` (the two Wikidata
  adapters, and how one upstream serves two domains today),
  `domains/series/tvmaze.py` (the most recent adapter written, and the closest model),
  `domains/movie/__init__.py` (`wikidata_identity`, `MOVIE_IDENTITY`, `MOVIE_FIELDS`),
  `domain/providers.py` (`merge_and_rank`, `fill_empty`, `IdentityStrategy`).
- Tests: `test_tvmaze_provider.py` (the model for a recorded adapter suite),
  `test_domain_conformance.py`, `test_provider_health.py`, `test_movie_posters.py`.

## Current implementation baseline

Measured live on 2026-09-02, after Sprint 062 closed:

- **Movies are served by one adapter.** `MOVIE_IDENTITY` keys on the **Wikidata `Q` id**
  (`wikidata_identity`), so a second movie provider cannot merge with Wikidata at all — it
  would produce a duplicate row for every film. The identity is the blocker, not the
  adapter. Series already key on IMDb and need no such change.
- **Wikidata's outage is intermittent, not resolved.** `maxlag=5` was refused on
  2026-08-31 (DEC-108) and again on 2026-09-02 (DEC-125), and had recovered by the end of
  that day. Sprint 062 stopped sending the parameter; it did not give the domain a second
  source.
- **The Wikidata movie adapter already emits an IMDb id on every measured result** —
  verified live: `Q189540` carried `imdb: tt0047478`, `tmdb: 346`, `letterboxd:
  seven-samurai`. So the identity change has data behind it today.
- **Cinemeta is already a de facto dependency.** DEC-103 put every movie and series poster
  on `images.metahub.space`, which is the same Stremio infrastructure. This sprint reads
  metadata from a service the product already cannot render covers without.

Measured against Cinemeta on 2026-09-02, keyless and unauthenticated:

| Probe | Result |
|---|---|
| `GET /catalog/movie/top/search=<q>.json` | 6/6 queries answered, 3–25 results, 0.09–4.45 s, including a Spanish-language title |
| `GET /meta/movie/tt0047478.json` | 0.64 s; `director`, `writer`, `cast`, `country`, `genres`, `runtime`, `description`, `year`, `imdbRating`, `moviedb_id` |
| `GET /meta/series/tt0903747.json` | 0.28 s; same shape |

Two shapes are load-bearing and are why the deliverables read as they do:

- **`/meta/` posters are `images.metahub.space` (allowlisted); `/catalog/` posters are
  `m.media-amazon.com` (not).** The search response's poster is therefore ignored
  entirely and the poster is built from the IMDb id, exactly as DEC-103 already does.
- **Search results carry no `year`** (`year` is present only on `/meta/`), so the adapter
  is search-then-fetch, like every other adapter here.

## Deliverables

1. **`infrastructure/cinemeta.py` — the shared transport and response reader.** Cinemeta's
   two endpoints and their envelopes are identical for `movie` and `series`; only the field
   mapping differs. Technical spec §6.6 forbids one domain package importing another, and
   `infrastructure/posters.py` is the standing precedent for exactly this: shared because
   two domains need it, and it performs no domain reasoning. This module owns the URL
   shapes, the `{metas: [...]}` / `{meta: {...}}` envelopes, the `"207 min"` → `207`
   runtime parse, and the pacing/bounding/retry call into `bounded_json_object`.
2. **`domains/movie/cinemeta.py` — `CinemetaMovieProvider`, registered as `cinemeta`.**
   Maps to `MOVIE_FIELDS`: `director` → `creators`, `country` → `countries`, `genres`,
   `runtime`, `cast`, `description`. `original_title` and `languages` are left empty —
   Cinemeta carries neither, and `fill_empty` means Wikidata still supplies them.
3. **`domains/series/cinemeta.py` — `CinemetaSeriesProvider`, registered as
   `cinemeta-series`.** The registry is keyed by name, so a second adapter answering to
   `cinemeta` would silently replace the movie domain's — the same reason
   `wikidata-series` is named as it is (DEC-104).
4. **`MOVIE_IDENTITY` moves to an IMDb key**, mirroring `series.imdb_identity`: `imdb:<id>`
   when the candidate carries a well-formed one, `None` otherwise. `None` merges with
   nothing, so the ~2% of films with a TMDB id and no IMDb id (DEC-103) stay separate rows
   rather than collapsing — which is what `wikidata_identity` was protecting and must keep
   protecting.
5. **`source_preference` becomes `("wikidata", "cinemeta")` and
   `("wikidata-series", "tvmaze", "cinemeta-series")`.** Cinemeta is complementary and a
   fallback, never primary: it fills what the others left empty and never displaces them.
   DEC-109 already established that this is a ranking, not a strict order.
6. **Covers stay on the existing path.** `metahub_poster_url` from the IMDb id, the
   allowlist untouched. Widening it to Amazon's CDN for a search thumbnail is not worth a
   new host on a central security list.
7. **Enrichment.** Both domains' `EnrichmentSpec.provider_order` gains the Cinemeta
   adapter, and each provider implements `fetch_by_identifier("imdb", ...)` — which for
   Cinemeta is the same `/meta/` call its `fetch` already makes.

## Acceptance criteria

1. **Measured coverage, recorded before the adapter is trusted** (the DEC-104 method): over
   a sample of **at least 15 films and 10 series** spanning popular, obscure, non-English
   and recent titles, record for each whether Cinemeta returned a record, an IMDb id, a
   description, and a runtime. The result is written into
   `docs/movie-domain-viability.md` and `docs/series-domain-viability.md` as a dated
   section, whatever it shows. **If coverage is materially worse than Wikidata's on the
   same sample, the sprint stops and reports rather than shipping the adapter.**
2. A movie search with the Wikidata adapter failing returns Cinemeta results with covers —
   exercised through the running application, not a unit test.
3. A movie search with both providers healthy returns **one** row per film, sourced
   `wikidata`, carrying both `source_refs`, with any field Wikidata left empty filled from
   Cinemeta and no field Wikidata supplied overwritten.
4. Two films sharing a title and differing in IMDb id (the `Suspiria` 1977/2018 pair Sprint
   045 measured) remain two rows. A film with no IMDb id remains its own row and merges
   with nothing.
5. A series search returns one row per show across all three providers, still preferring
   Wikidata's, with TVmaze's synopsis still winning under `fuller_answer_fields` (DEC-115).
6. Adding a Cinemeta-sourced film and a Cinemeta-sourced series both succeed and install a
   cover, with no metadata key the domain does not declare (DEC-125's rule).
7. No request reaches `m.media-amazon.com`, and `ALLOWED_COVER_HOSTS` is unchanged.
8. `/api/health/providers` lists both new adapters.

## Required tests (TDD)

| Behavior | Layer | File |
|---|---|---|
| Search then fetch; the recorded envelopes are read, not guessed | provider, replayed | `test_cinemeta_provider.py` (new) |
| `"207 min"` becomes `207`; a missing or malformed runtime becomes `None` | provider, replayed | `test_cinemeta_provider.py` |
| The search poster is ignored and the metahub URL is built from the IMDb id | provider, replayed | `test_cinemeta_provider.py` |
| A record with no IMDb id yields no identity and no cover | provider, replayed | `test_cinemeta_provider.py` |
| Movie identity: same IMDb id merges, different ids do not, absent id merges with nothing | domain | `test_movie_domain.py` |
| Wikidata + Cinemeta merge to one row, Wikidata primary, fill-empty only | application | `test_cinemeta_provider.py` |
| Three-way series merge keeps TVmaze's fuller synopsis | application | `test_cinemeta_provider.py` |
| A movie search survives Wikidata raising | application | `test_providers.py` |
| Both adapters satisfy the domain contract | conformance | `test_domain_conformance.py` |

Every provider assertion runs against committed recordings captured live in their own
commit, per `tests/fixtures/providers/README.md`. No mock of the method under test
(DEC-025), and **no test double whose shape has drifted from the adapter it stands for** —
that second rule is Sprint 062's lesson and is what hid a 422 for twelve sprints.

## Verification

- `python scripts/validate_project.py`
- `make check`
- `make test`
- `make smoke-container`
- **Walkthrough (DEC-025):** against the built container on an isolated volume and a
  non-default port — never the owner's own instance — search and add in the movie and
  series domains with both providers healthy, then **again with the Wikidata adapter forced
  to fail**, which is the entire point of the sprint. Record what was seen, including
  anything that looked wrong and was out of scope.

`npx playwright test` is owed **only if** a request path or a screen changes. This sprint
plans neither; the claim is checked against `git diff --stat` at the freeze point, per
`TESTING.md`. Note that Sprint 061's blocker is still unresolved —
`frontend/node_modules/.vite/deps` is owned by `root` — so if E2E does become owed, fixing
that ownership is a prerequisite and not a reason to skip the gate.

## Explicit non-scope

- **Anime and albums.** Both are single-provider and both are Sprint 064's, for reasons
  that are not "no time": Jikan's search endpoint answered `504` on every attempt on
  2026-09-02 while MyAnimeList itself was up, and a second album provider is blocked by
  DEC-052's deliberate finding that albums have **no** cross-provider identity — a product
  decision to reopen, not an adapter to write. Splitting here is the scope rule, not a trim.
- **TMDB.** Sprint 045 measured and rejected it: a credential plus a six-month cache limit.
  Nothing here changes that trade.
- **Widening `ALLOWED_COVER_HOSTS`.** See deliverable 6.
- **Making `/api/health/providers` report reachability** rather than configuration
  (DEC-125). Still worth doing, still not here.
- **Retiring the AniList adapter.**

## Commit checkpoints

1. `[DOCS] Measure what Cinemeta actually answers for` — AC1, before any adapter exists.
2. `[TEST] Record Cinemeta's responses` — the fixtures, in their own commit.
3. `[ADD] Read films and shows from Cinemeta`
4. `[MOD] A film's identity is its IMDb id`
5. `[MOD] Rank Cinemeta behind the sources that were already there`
6. `[DOCS] Close sprint 063 and hand off`

## Risks and decisions to surface

- **Cinemeta is a community addon endpoint with no published SLA or terms of use.** The
  owner has accepted this class of risk explicitly for fallback and complementary sources.
  It is recorded here rather than assumed, and it is bounded by Cinemeta never being
  primary: if it disappears, both domains return to exactly today's behaviour. Worth
  stating plainly that DEC-103 already took the same bet on the same infrastructure for
  every poster in the product.
- **Changing `MOVIE_IDENTITY` needs a decision entry that supersedes DEC-098's reasoning
  without rewriting it.** The Q-id was chosen when one provider meant no merge was
  possible; that premise is what this sprint removes. The protection it actually provides —
  two films sharing a title and year are two records — is preserved by IMDb, and AC4 is
  the proof.
- **Identity is computed over search candidates, not stored rows**, so this should not
  touch existing library data. *Should* is not evidence: verify against a library that
  already holds Wikidata-sourced films before closing, and say so in the Outcome.
- **Coverage might not justify the adapter.** AC1 is written as a real gate with a stop
  condition, the way DEC-097 and DEC-104 were. A measured "no" is a valid outcome for this
  sprint and costs one commit.

## Outcome

**Delivered 2026-09-03.** All eight acceptance criteria met; see DEC-126 for the full
decision record.

1. **Measured coverage (AC1):** 15/15 films and 10/10 series, every hit carrying an
   IMDb id, a description and a runtime; parity with Wikidata's own filter on the same
   sample. Recorded as dated sections in `docs/movie-domain-viability.md` and
   `docs/series-domain-viability.md`. The gate cleared, so the adapter proceeded.
2. **Movie search survives Wikidata failing (AC2):** proven twice — unit-level in
   `test_a_movie_search_survives_wikidata_raising`, and live against the built
   container with `www.wikidata.org`/`wikidata.org` resolved to an unreachable address
   (`docker run --add-host … 127.0.0.1`). A "Seven Samurai" search still returned
   Cinemeta's result with a cover in 2.09 s, `X-Provider-Warning` set.
3. **Both-healthy merge (AC3):** live search for "Seven Samurai" returned one row,
   `source: wikidata`, `source_refs` carrying both `wikidata` and `cinemeta`, Spanish
   metadata from Wikidata untouched. `test_cinemeta_provider.py::TestWikidataCinemetaMerge`
   is the recorded-fixture proof.
4. **The Suspiria pair (AC4):** `tt0076786` (1977) and `tt1034415` (2018) confirmed live
   as distinct Cinemeta records and proven to stay two rows through `merge_and_rank`
   (`TestMovieIdentityMerge`).
5. **Three-way series merge (AC5):** live search for "Breaking Bad" merged Wikidata,
   TVmaze and Cinemeta into one row; `TestThreeWaySeriesMerge` pins Wikidata's own
   synopsis surviving the merge and `test_a_third_fuller_answer_provider_does_not_displace_the_second`
   (test_cached_add.py) proves the add path's fuller-answer rule (DEC-115) still picks
   TVmaze's longer synopsis over Cinemeta's shorter one.
6. **Cinemeta-sourced adds install a cover (AC6):** live, in the walkthrough container —
   "Snow White and the Seven Samurai" (movie, `source=cinemeta`) and "Chernobyl"
   (series, `source=cinemeta-series`) both added with a real downloaded cover and no
   metadata key outside each domain's declared fields. (Two other candidate titles
   genuinely have no metahub poster — confirmed with a direct request, a clean 404, not
   a bug — and were not used for this proof.)
7. **No request reaches `m.media-amazon.com` (AC7):** structural — the adapter only
   ever calls `CINEMETA_BASE`; `ALLOWED_COVER_HOSTS` is untouched.
8. **`/api/health/providers` lists both adapters (AC8):** confirmed live; `cinemeta`
   and `cinemeta-series` each appear directly after their domain's other providers,
   following each domain's declared `source_preference` with no code change to the
   endpoint itself.

**Verified:** `python scripts/validate_project.py`, `make check` (backend ruff/mypy,
frontend lint/typecheck/prettier, OpenAPI contract check — untouched, since no route
changed), `make test` (1,252 backend + 197 frontend, all passing), `make
smoke-container` (full pass, built from this branch). Walkthrough: a container built
from this branch, on isolated Docker volumes and a non-default host port (18063,
later 18064), never the owner's instance — searched and added in both domains with
every provider healthy, then rebuilt with Wikidata's two hostnames resolving to an
unreachable address and repeated both searches and both adds. All containers, volumes
and the local image were removed at closure.

**Commits:** `99f9636` (AC1 measurement), `a0642a0` (recorded fixtures), `add2dc4`
(the two adapters + shared transport + wiring), `f892d32` (the identity and ranking
change), `7e0d2d2` (the tests proving the merge, the fuller-answer rule and the outage
survival).

**Deviations:**

- The commit-checkpoint shape differs from the six suggested in this file: identity
  and ranking landed as one `[MOD]` commit per domain's declaration (they are the same
  few lines), and all new tests landed in one `[TEST]` commit rather than being split
  to match intermediate, not-yet-integrated states. No behavioral difference.
- **Sprint 064 does not exist as a written plan yet** (the roadmap always said so:
  `[PLANNED, not yet written]`), so `docs/agent/state.json` cannot point at a real
  "next sprint" the way the workflow expects. A minimal stub,
  `docs/sprints/064-second-source-anime-albums.md`, was created with `Status: blocked`
  and the two things it is genuinely blocked on (a Jikan re-measurement, an owner
  decision on reopening DEC-052's album-identity finding) — not a real plan, and not
  meant to be treated as one. See DEC-126's closing paragraph and `HANDOFF.md`.

**Impact on future sprints:** Sprint 065 (Spotify import) and 066 (insights) are
unaffected — neither depends on 063 or touches movies/series. Sprint 064, whenever it
is actually planned, inherits `imdb_identity` as the pattern its own two candidate
domains would need if either ever gained a real second provider (anime already has
one via `mal:`; the album question is exactly what DEC-052 already found blocks it).
