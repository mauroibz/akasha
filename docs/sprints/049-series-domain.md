# Sprint 049 — Series: the fifth domain, with posters on day one

**Status:** ready
**Depends on:** 048
**Roadmap revision:** 27

## Objective

Television series become the fifth Akasha domain, on keyless Wikidata, with a working poster and a
working episode-progress control from the first commit. No migration, no new status, no new format,
no screen.

## Required context

- `docs/series-domain-viability.md` in full — the live measurements this sprint implements.
- `docs/guides/adding-a-domain.md` §2 (the registration table) and §3 (step by step). Follow it
  rather than reading how movies were built; Sprint 038 proved that works and Sprint 046 confirmed it.
- `docs/decisions.md`: DEC-077 (no entry hierarchy), DEC-092 (progress has a floor and no ceiling),
  DEC-098 and DEC-099 (the Wikidata adapter as built, and what its search actually costs),
  DEC-103 (posters from Stremio), and the new DEC-104.
- `backend/src/book_tracker/domains/movie/` in full. The Wikidata half of this sprint is the same
  API with a different filter, different claims and one structural difference in the search filter
  that DEC-104 records — read it, and read `posters.py`, which this sprint moves.
- `backend/src/book_tracker/domain/spec.py` — `ProgressSpec`, and the comment on `total_field`.
- `backend/src/book_tracker/infrastructure/covers.py` — the allowlist already contains the host this
  needs. Do not touch any bound.

## Current implementation baseline

Observed 2026-08-31. Four domains ship: `book`, `album`, `anime`, `movie`. `images.metahub.space` is
already in `ALLOWED_COVER_HOSTS`. `metahub_poster_url` lives in `domains/movie/posters.py`, and the
domain-package rule forbids `domains/series/` from importing it from there. `ProgressSpec` exists and
anime uses it. Every status this domain wants (`watching`, `completed`, `on_hold`, `dropped`,
`plan_to_watch`) and every format it wants (`streaming`, `digital`, `bluray`, `dvd`) is already
published in `EntryStatus` and `EntryFormat` and already mirrored in `frontend/src/api/library.ts`.

## Deliverables

### 1. `infrastructure/posters.py` — the poster builder, promoted

Move `metahub_poster_url` and its `METAHUB_POSTER` constant out of `domains/movie/posters.py` into
`infrastructure/posters.py`, unchanged. It builds a URL from an IMDb id; it names no domain and
performs no request, which is what makes it shared infrastructure rather than a movie detail.
`domains/movie/posters.py` keeps `TmdbPosters` and `poster_for` and imports the builder from its new
home. Two domains needing one keyless URL builder is not a reason to duplicate it, and a series
package importing a movie package is forbidden outright.

Existing movie poster tests must pass unchanged; if a test names the old import path, update the
path and nothing else.

### 2. `domains/series/__init__.py` — the declaration

Fields, measured rather than guessed (see the viability document's coverage table):

| Field | Label | Type | Source |
|---|---|---|---|
| `creators` | Creators | many | `P170`, falling back to `P58` screenwriter when absent |
| `original_title` | Original title | text | `P1476` |
| `countries` | Countries | many | `P495` |
| `languages` | Original languages | many | `P364` |
| `genres` | Genres | many | `P136` |
| `episodes` | Episodes | number, 1–100 000 | `P1113` |
| `seasons` | Seasons | number, 1–1 000 | `P2437` |
| `episode_minutes` | Episode length | number, 1–1 000 | `P2047` |
| `network` | Network | text | `P449` |
| `airing_status` | Airing | text | derived from `P582`; TVmaze replaces it in Sprint 050 |
| `cast` | Cast | many | `P161`, bounded as the movie adapter bounds it |
| `synopsis` | Synopsis | long_text | Wikidata's localized description in this sprint |

`creators` holds the creator rather than the director, because that is the name a series is filed
under and `P57` was present on a minority of measured entities. A creator is a person and inverts,
so `creator_sort` is left unset and the DEC-051 heuristic runs, exactly as for movies.

`synopsis` is named honestly: in this sprint it holds Wikidata's one-line identification sentence,
which is what movies call `description`. It is called `synopsis` because Sprint 050 fills it with a
real one from TVmaze and renaming a published field later is worse than naming it for its purpose
now. Say so in the module docstring.

Statuses are anime's five plus `unsorted`, with the same hotkeys. Formats are the movie four.
Neither adds a value to `EntryStatus` or `EntryFormat`.

Entry: `PASSAGE_FIELDS`, `entry_field_labels={"reread_count": "Rewatches"}`, entry panel
"Your watch data", default status `plan_to_watch`.

Progress: `ProgressSpec("Episodes watched", "episode", total_field="episodes")`.

Identity: `imdb_identity` returning `imdb:tt…` from `candidate.identifiers["imdb"]`, `None` for a
candidate with none. `IdentityStrategy(imdb_identity, ("wikidata", "tvmaze"))` — the provider order
is declared now so Sprint 050 adds an adapter and not a declaration.

Enrichment: `EnrichmentSpec(identity_kind="imdb", provider_order=("wikidata",),
completeness_fields=("creators", "genres", "synopsis"))`. **`seasons` and `cast` must not appear**:
they were absent on 2/13 and 4/13 of measured entities respectively, and naming a legitimately empty
field re-queues its row on every backfill for ever.

`chooses_covers=False`.

### 3. The recognizer

Wikidata entity URLs route directly. IMDb `/title/tt…`, TMDB `/tv/<id>`, TVDB `/series/<slug>` and
TVmaze `/shows/<id>` URLs route to the Wikidata adapter behind a prefix, resolved through the exact
`P345`, `P4983` or `P4835` claim. TMDB's `/movie/` path is a film and must stay the movie domain's;
a series recognizer that claimed it would break add-by-URL for films.

Parse through `split_url`, never `urlsplit` — a recognizer that raises denies every domain
registered after it its turn.

### 4. `domains/series/providers.py` — `WikidataSeriesProvider`

Structurally the movie adapter, with one difference that is the whole reason this is not a copy: the
search filter is **five instance-of classes, not one**.

```text
haswbstatement:P31=Q5398426|P31=Q117467246|P31=Q63952888|P31=Q1259759|P31=Q581714
```

A single `P31=Q5398426` filter — the movie shape — returned the right series at rank 1 for only 9 of
14 measured titles and returned *nothing at all* for two of them. The class list is a named module
constant with the measurement in its docstring, because the next person to read this will otherwise
assume it was copied carelessly from the movie adapter.

Everything DEC-099 established carries over unchanged: bounded search then bounded entity batches,
`maxlag`, `429`/`Retry-After`, a descriptive User-Agent, and re-checking a claim on the fetched
entity rather than trusting a `haswbstatement` hit. Series entities are **larger** than films —
thirteen measured 1.37 MB, one of them 105 KB alone — so the batch size must be no larger than the
movie adapter's and the response bound must not be raised.

`fetch_by_identifier("imdb", value)` resolves through `haswbstatement:P345=<tconst>`, which hit 13
of 13. This is the operation both importers depend on; it is not optional.

`cover_url` is `metahub_poster_url(identifiers.get("imdb"))`. No request, no key, no new host.

### 5. Registration

`domain/registry.py`: one import, one `DOMAINS` tuple entry, one `IMPORTERS_BY_DOMAIN` entry of `()`,
and `ItemTypeName.SERIES = "series"`. `main.py` lifespan constructs the adapter into the provider
catalog. `backend/tests/fixtures/providers/` gains recorded responses.

That is the entire shared surface. Registration points 4 and 5 of the guide — new statuses, new
formats and their frontend mirror — **do not apply**, because this domain introduces neither.

## Acceptance criteria

1. `GET /api/item-types` publishes `series` with its statuses, formats, fields, entry labels and its
   progress declaration, and the Library tab strip, Triage hotkeys and Detail layout render from it
   with **no frontend change**.
2. A series search returns candidates whose identity is `imdb:tt…`, against recorded responses.
3. The five-class search filter is exercised by a test that fails under a single-class filter: an
   animated series, an anime series and a miniseries each resolve at rank 1.
4. `fetch_by_identifier("imdb", "tt…")` returns the series, and a `haswbstatement` hit whose fetched
   entity does not actually carry that claim is refused.
5. A series carrying an IMDb id emits a Stremio poster URL with no extra request, and the cover
   pipeline installs it with no bound, host or redirect rule changed.
6. An entry records episodes watched; the control reads `20 / 170 episodes`; a count above the stored
   total is stored and displayed rather than refused (DEC-092).
7. `EntryStatus` and `EntryFormat` are **unchanged**. `ItemTypeName` gains exactly one member.
8. No migration, no new route, no screen change. `make openapi` diffs only the item-type enum.
9. `test_domain_conformance.py` passes with the new domain registered, unmodified.

## Required tests (TDD)

- Domain declaration: statuses, formats, progress spec, entry labels, enrichment spec, and a test
  asserting `seasons` and `cast` are **not** completeness fields, with the measurement as the reason.
- Recognizer: all five URL shapes, plus TMDB `/movie/` returning `None`, plus a malformed authority
  returning `None` rather than raising.
- Provider against recorded responses: search, the five-class filter, entity parsing including an
  entity with no `P2437` and one with no `P161`, identity resolution by IMDb id, and claim re-check.
- Poster URL construction for a series with an IMDb id and one without; a recorded 404 through
  `prepare_cover` leaving the item coverless and failing nothing.
- Progress: store, render, and a value above the total.
- Movie poster suite passes after the module move, with only the import path changed.

## Verification

```bash
cd backend && uv run pytest tests/test_series_domain.py tests/test_wikidata_series_provider.py \
  tests/test_domain_conformance.py tests/test_movie_posters.py tests/test_covers.py -q
make check
make test
make openapi   # expect only the ItemTypeName addition
```

Then the walkthrough gate. Run the application on a disposable data directory and **look at the
screens**: add a series by search, add one by IMDb URL, confirm the poster is that series' actual
poster art, set an episode count and see it render, and open the Library tab for series. Sprint 046
passed a green gate while producing a wall of blank tiles; a populated field is not the standard.

## Explicit non-scope

- **TVmaze.** Sprint 050. This sprint ships one provider and a `synopsis` field holding Wikidata's
  short description, which is exactly the quality movies ship at today.
- **Any importer.** Sprints 051–053.
- Seasons or episodes as entities, in any form. DEC-077 settled this and this sprint is its evidence.
- Per-season or per-episode scores, ratings or notes.
- Changing any cover bound, the allowlist mechanism or the redirect policy.

## Commit checkpoints

1. `[REF] Promote the poster URL builder to shared infrastructure`
2. `[ADD] Declare the series domain`
3. `[ADD] Read series from Wikidata on a five-class filter`
4. `[DOCS] Close sprint 049 and hand off`

## Risks and decisions to surface

- **The five-class filter is a live measurement with a shelf life.** Wikidata's class hierarchy
  changes. If a later series is missed, the fix is to add a measured class to the constant, not to
  widen the filter speculatively.
- **`synopsis` is under-filled until Sprint 050.** If the owner sees the one-line description and
  wants it filled before the importers land, 050 moves ahead of 051; the dependency runs that way
  already.
- Stremio's metahub is undocumented infrastructure (DEC-103's accepted risk), now load-bearing for
  two domains rather than one. Unchanged in kind, larger in blast radius.

## Outcome

_Not started._
