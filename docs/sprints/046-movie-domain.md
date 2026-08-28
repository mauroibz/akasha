# Sprint 046 — Movies: the fourth domain on Wikidata

**Status:** completed
**Depends on:** 045
**Roadmap revision:** 25

## Objective

Ship movies as a complete fourth domain using the provider Sprint 045 actually exercised:
Wikidata's official API. Search, add, URL recognition, Spanish labels, structured metadata,
Letterboxd-keyed enrichment and every existing library surface work without a migration or a
movie-specific screen. TMDB and OMDb do not ship in this sprint.

## Required context

- `docs/movie-domain-viability.md` in full; its live observations are the contract, not suggestions.
- `docs/guides/adding-a-domain.md` and technical spec 6.6 in full.
- `docs/decisions.md`: DEC-052, DEC-067, DEC-088 through DEC-094, DEC-097 and DEC-098.
- `docs/agent/TESTING.md`, especially recorded-real-response and walkthrough rules.
- Existing shortest declaration/provider: `domains/album/`; existing enrichment provider:
  `domains/anime/`; actual shared contracts in `domain/spec.py`, `domain/providers.py` and
  `tests/test_domain_conformance.py`.
- Registration points: `domain/registry.py`, `main.py`, `frontend/src/api/library.ts` and their
  existing contract tests. Inspect them; do not infer their current shape from this plan.

## Deliverables

### 1. A movie declaration, complete on construction

Create `domains/movie/`. Declare:

- item type `movie`, label Movie;
- fields for directors (`creators`), original title, countries, languages, genres, runtime, cast
  and description, using neutral `year` for release year;
- `unsorted`, `watchlist` and `watched`, with default `watchlist` and unique hotkeys;
- streaming, digital, Blu-ray and DVD formats;
- `date_finished` labelled Watched and `reread_count` labelled Rewatches; no start date or progress;
- no cover chooser and no provider-derived cover in this slice; and
- enrichment keyed on `letterboxd`, answered by Wikidata, so the following importer can fill an
  export's skeletal title/year record without another shared capability.

Add the declared public values to the existing typed backend/frontend unions and regenerate the API
contract. No schema change: the Sprint 044 head guard proves the vocabulary remains application
owned.

### 2. A measured Wikidata movie provider

Implement one adapter using the official Action API through the shared bounded HTTP behavior. It:

- searches with `action=query&list=search` and `haswbstatement:P31=Q11424`, preserving provider
  relevance, then batch-fetches entities and linked labels;
- fetches a `Q` id and maps only best-ranked, correctly typed claims;
- uses Spanish labels/descriptions with English fallback and records original title separately;
- maps director, country, original language, genre, runtime and a bounded cast list;
- emits Wikidata, IMDb (`P345`), TMDB movie (`P4947`) and Letterboxd slug (`P6127`) identities when
  valid, never treating title/year as exact identity; and
- returns no cover URL. `P18` is a general image and the measured record was not poster art.

Every parser behavior is proved against committed, bounded real response fixtures recorded during
this sprint. Include the four Sprint 045 query classes: Argentine/Spanish-language, old, recent and
same-title remakes. Fixtures contain public provider data only and say when/how they were recorded.

### 3. Exact external-identity and URL resolution

The provider resolves Wikidata `Q` ids directly and exact IMDb, TMDB movie and Letterboxd slug
claims through `haswbstatement`. URL recognition may route official Wikidata entity, IMDb title,
TMDB movie and Letterboxd film URLs to that one adapter. A `boxd.it` short URI is followed with a
HEAD request only, through a small redirect bound, and accepted only when it ends at HTTPS
`letterboxd.com/film/<slug>/`; no HTML body is fetched or parsed.

`fetch_by_identifier("letterboxd", value)` accepts the normalized short URI the importer will
store, resolves the slug and returns the same payload. Zero or multiple exact claim matches are a
typed provider miss, not a title guess. Recorded transport fixtures use a publicly documented
Letterboxd example, never the owner's export URI.

### 4. Ordinary registration, health and safety

Register the domain and construct the provider in the lifespan. Use the existing contact-bearing
User-Agent configuration; there is no credential or new secret. Respect Wikimedia `maxlag`, 429 and
`Retry-After`, bounded response size, result count and linked-label batch size. No new cover host is
allowlisted. The Sprint 044 APP checks must see the provider, recognizer routes and enrichment
wiring without adding movie-specific conformance logic.

## Acceptance criteria

1. Movie search returns film-only, relevance-preserving candidates with localized structured fields
   for all representative recorded responses; unrelated entities and television series are absent.
2. Fetch by Q id, IMDb id, TMDB movie id, Letterboxd slug and safe short URI resolves the same movie;
   malformed values, ambiguous claims and hostile redirects are refused with typed errors.
3. Spanish is preferred with English fallback. Missing/unknown claims remain absent; ranks,
   quantities and time precision are parsed deliberately rather than taking the first JSON value.
4. No arbitrary Wikidata image becomes a cover. Manual cover upload continues to work unchanged.
5. The complete domain declaration reaches item types, filters, add, Triage, detail, metadata edit,
   statuses, formats and OpenAPI through declarations—no `if movie` above the registry.
6. `letterboxd` enrichment wiring is live and conformance-covered, while a movie fetched through
   search needs no redundant background job.
7. No migration and no shared screen change. Every edit outside `domains/movie/` is one of the
   documented registration/type/fixture/doc points or is recorded as a contract defect.

## Required tests (TDD)

- New provider tests replay each recorded search/entity/linked-label/identity/HEAD response and
  first fail against the unimplemented adapter.
- Parser tests cover claim ranks, missing values, precision, quantities, label fallback, cast bound,
  film filtering, malformed payloads and typed HTTP/provider failures.
- Domain tests cover status/format/field/progress declarations and every URL shape, including
  malformed authorities and redirect-host attacks.
- Existing conformance runs unchanged over the fourth domain at registry, core and application
  tiers. Add malformed fixtures only for a genuinely new general rule.
- Registry/OpenAPI/frontend contract tests prove every new public value reaches both clients.
- Enrichment tests use the real recorded Wikidata boundary and prove fill-empty-only behavior from
  a `letterboxd` key plus typed miss/failure outcomes.

## Verification

```bash
cd backend && uv run pytest tests/test_movie_domain.py tests/test_wikidata_provider.py \
  tests/test_domain_conformance.py tests/test_enrichment_pipeline.py -q
make openapi
make check
make test
cd frontend && npm run test:e2e
```

### Walkthrough gate

Run a disposable app with no live library data. Through the real UI, search and add at least the
Argentine film, the old film and one of the same-title remakes; verify Spanish labels, directors,
runtime/genres, default Watchlist, status/format editing, Library filtering, Triage and Detail.
Paste one public external URL through the add box and exercise a provider miss. Record provider
health and browser/console errors. Do not use or mutate the private Letterboxd ZIP in this sprint.

## Explicit non-scope

- TMDB/OMDb adapters, API keys, provider-content expiry/provenance, automatic poster selection.
- Letterboxd ZIP parsing or importer registration; Sprint 047 owns it.
- Television, seasons, episodes, progress or child entries.
- Recommendations, cast-person pages, trailers, streaming availability or theatrical schedules.
- Any container/build work unless runtime packaging actually changes.

## Commit checkpoints

1. `feat(sprint-046): declare the movie domain`
2. `feat(sprint-046): add the recorded Wikidata movie provider`
3. `feat(sprint-046): resolve exact movie identities and enrichment`
4. `docs(sprint-046): close sprint and hand off`

## Risks and decisions to surface

- Wikidata claims have ranks, qualifiers and time precision. A thin first-value parser can return a
  deprecated or country-specific fact as global truth; fixtures must force the choice.
- The public query API is keyless, not unlimited. Search is sequential/batched and observes
  `maxlag`/429 rather than issuing one lookup per linked entity.
- The selected provider is intentionally less visual than TMDB. Do not smuggle TMDB terms into the
  sprint to make the walkthrough prettier.

## Outcome

Delivered as planned, with one measured deviation from the search shape this plan assumed and two
defects observed and recorded rather than repaired.

### What ships

`domains/movie/` is the fourth domain: eight declared fields, three statuses (`unsorted`,
`watchlist` default, `watched`), four formats, `date_finished` labelled Watched and `reread_count`
labelled Rewatches with no start date and no progress, identity on the Wikidata `Q` id, and
enrichment keyed on `letterboxd`. `WikidataMovieProvider` is its one adapter: film-filtered search,
fetch by `Q` id, exact IMDb/TMDB/Letterboxd claim resolution, HEAD-only `boxd.it` resolution, Spanish
labels with English fallback, and no cover URL under any circumstance.

Shared edits are the documented registration points and nothing else: `domain/registry.py` (import,
`DOMAINS`, empty importer tuple, `EntryStatus.WATCHLIST/WATCHED`, `EntryFormat.DVD`,
`ItemTypeName.MOVIE`), `main.py` lifespan, `frontend/src/api/library.ts`, the regenerated
`frontend/openapi.json`, one `PROVIDER_LABELS` row, and the fixtures with their README. One shared
test helper changed: `tests/recordings.py:replay` gained an optional `key` callable, because Wikidata
answers search, entity and label reads at one path and a path is therefore not a route. No existing
caller changed. No migration, no screen change, no credential.

### Deviation: a search is six candidates in bounded batches, not twenty in one read

The plan said "batch-fetches entities and linked labels" without a size. Measured live before
building: one entity is ~113 KB, five up to 1.15 MB and ten **1.9 MB**, against `MAX_PROVIDER_BYTES`
of 2 MiB. A twenty-result search cannot be read at all, and a ten-result one would sit on the limit.
Search is therefore capped at six candidates and reads entities three at a time, plus one label
batch. Measured end to end through the running app: 1.6 s for a one-result query, 2.8 s for the
six-result `Metropolis` query, inside the shared five-second interactive budget. DEC-099.

### Acceptance criteria

1. **Film-only, relevance-preserving, localized.** `Metropolis` returns six films with Fritz Lang's
   1927 one first and `Metrópolis` as its title; `Suspiria` returns exactly the 1977 and 2018 films.
   Proved against four recorded query classes and confirmed live in the walkthrough.
2. **Every identity resolves, and the wrong ones are refused.** `Q` id, IMDb, TMDB and Letterboxd
   slug each reach `Q546900`; a short URI reaches it through HEAD only. Zero hits are
   `record_not_found`, two are `identity_ambiguous`, a redirect off Letterboxd, a downgrade to
   plaintext, a loop and a non-film destination are `unsafe_redirect`, and nine malformed identity
   shapes never reach the network at all. A search hit is additionally re-checked against the fetched
   entity's claim, because `haswbstatement:P345=tt0000000` returns a real film.
3. **Ranks, snaktypes, precision and units are read deliberately.** The preferred-rank `P364`, the
   deprecated `P495`, the `somevalue` language, thirty mixed-precision `P577` statements and a
   unit-bearing `P2047` each have a test that fails against a first-value parser.
4. **No arbitrary image becomes a cover.** `cover_url` is `None` for every path, `P18` is never read,
   and the walkthrough's three added films all have `cover_url: null`. Manual upload is untouched.
5. **The declaration reaches every surface.** Item types, filters, add, detail, metadata edit,
   statuses, formats and OpenAPI, with no `if movie` anywhere above the registry.
6. **Enrichment is live and needs no redundant job.** A movie carrying a `letterboxd` identity queues
   with that kind; one carrying only an `imdb` id queues nothing; the handler fills empty fields only
   from the recorded Wikidata boundary and leaves the owner's title and description intact. Adding
   through search enqueues nothing, because only an import commit or the explicit backfill route
   does.
7. **No migration and no shared screen change.** Every edit outside `domains/movie/` is a documented
   registration point, the test-helper extension above, or a fixture.

### Verification

- Focused suite: **239 passed** (`test_movie_domain.py` 30, `test_wikidata_provider.py` 59,
  `test_domain_conformance.py`, `test_enrichment_pipeline.py`).
- `make openapi` then `make check`: passed, including `openapi-check` and the frontend type check.
- `make test`: **818 backend**, **189 frontend**.
- `npm run test:e2e`: **106 passed, 2 intentional skips**.
- Walkthrough: `frontend/e2e/scratchpad/movie-walkthrough.spec.ts`, **12 passed** against a
  disposable `BOOK_TRACKER_DATA_DIR` and the **live** Wikidata API at 390×844. Added the Argentine
  film, the 1927 film and Suspiria 1977 through the real add box; verified Spanish labels, director,
  runtime, countries, genres, cast, `Your viewing data`, Rewatches with no Started, no Rereads, the
  three exact identities on Detail, default Watchlist, a status change to Watched, the four declared
  formats with `dvd` applied independently of status, status filtering, and a pasted IMDb link
  resolving to Suspiria 1977. Final disposable library: three films, facets
  `{watched: 1, watchlist: 2}` and `{dvd: 1}`, all three with `cover_url: null`. No 500s, no
  unexplained console or page errors.

### Observed, out of scope, recorded (DEC-100)

- **A coverless domain is permanently backfillable.** `_backfillable_items` counts a null
  `cover_path` as incomplete in every domain regardless of `completeness_fields`, so the explicit
  `POST /api/enrichment/backfill` route will re-queue every movie on every call, each job asking
  Wikidata for a cover it will never return. Harmless today; it needs a way for a domain to say a
  cover is not something it has.
- **A miss is reported as an outage.** `GET /api/search/resolve` maps every exception from
  `resolve_input` to HTTP 502 `provider_failure`, so pasting a Letterboxd URL for a film that does
  not exist tells the reader the provider failed. Predates this sprint and affects every domain.
- **Triage could not be exercised for movies.** A film added by hand lands in Watchlist, never in
  the inbox, and the domain chooser is absent from Triage entirely while the inbox is empty. The
  only producer of unsorted movies is Sprint 047's importer.

### Commits

`6e53952` declare the movie domain · `1cd443e` add the recorded Wikidata movie provider ·
`20fda58` resolve exact movie identities and enrichment · plus this closure commit.
