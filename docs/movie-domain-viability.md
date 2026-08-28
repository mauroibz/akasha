# Movie domain viability

**Status:** historical — measured 2026-08-27 for Sprint 045. This is the evidence behind the movie
implementation plan, not a statement that movies already ship.

## Verdict

Movies are viable as a flat Akasha domain without a schema or screen change. **Wikidata is the
provider to build first:** it is keyless, its structured data is CC0, its official search can be
restricted to films, and live responses supplied stable Wikidata, IMDb, TMDB and Letterboxd
identities plus localized structured metadata for the representative set. It is a deliberately
modest launch provider: it does not supply a useful synopsis and only one of five measured films had
an image—and that image was a set photograph, not a poster.

TMDB would produce the richer experience the historical domain survey described, but it is **not a
valid Akasha provider under the current storage contract**. No credential is configured, so its
records could not be live-tested. More importantly, its current API terms require cached TMDB
content to be removed or refreshed within six months, while Akasha stores provider metadata
indefinitely in the same fields a person can edit and permits overwrite only through explicit
refresh. Attribution is also mandatory. Selecting TMDB now would silently accept terms for the
owner and create a provenance/expiry feature disguised as a movie adapter.

OMDb is not selected. It also requires a key, its content is CC BY-NC 4.0/personal non-commercial,
its dedicated poster API is patron-only, and its API has no first-class localized-title or
localized-description contract. It improves neither the current credential situation nor the
Spanish-language requirement enough to justify a second launch adapter.

## Provider measurement

### Wikidata — selected launch provider

The official [data-access guidance](https://www.wikidata.org/wiki/Help:Data_access) says structured
Wikidata is CC0, asks clients to send a descriptive User-Agent, respect `429`/`Retry-After`, use
`maxlag`, and use search for text rather than abusing the query service. The documented
[`haswbstatement`](https://www.mediawiki.org/wiki/Help:Extension:WikibaseCirrusSearch#haswbstatement)
filter lets the Action API search only instances of film (`P31=Q11424`). Entity data is then fetched
in batches with `wbgetentities`, whose anonymous limit is 50 ids per request.

Live calls used a descriptive Akasha User-Agent and no credential:

```text
GET www.wikidata.org/w/api.php
  action=query&list=search&srsearch=<title> haswbstatement:P31=Q11424
GET www.wikidata.org/w/api.php
  action=wbgetentities&ids=<bounded batch>&props=labels|descriptions|aliases|claims|sitelinks
```

The representative set covered an Argentine Spanish-language film, a 1927 film, a 2024 film and
both the 1977 and 2018 films sharing one title. Film-filtered search returned the expected item for
all four queries and both remakes for the ambiguous query. The unfiltered control showed why the
filter is load-bearing: the 1927 film was tenth behind a record label, novel, games and other uses
of the title.

All five fetched film entities carried instance, release date, director, genre, IMDb id, TMDB movie
id, runtime, country, original language, screenwriter and cast claims. Every one had an English and
Spanish label/description. All 41 distinct linked directors/genres/countries/languages in those
claims had both English and Spanish labels. The descriptions were short identification sentences,
not synopses. Four of five had no `P18` image; the remaining image was not poster art. The adapter
therefore must not mislabel `P18` as a cover in the first movie sprint.

What that proves:

- `Q` ids are stable primary source ids; IMDb (`P345`), TMDB movie (`P4947`) and Letterboxd film
  slug (`P6127`) are useful exact identities when present.
- Spanish display labels and structured values are practical. English fallback remains necessary.
- Search is two bounded official API operations: film-filtered ids, then batched entities/labels.
- A rich overview and poster are absent capabilities, not adapter bugs. Manual metadata and cover
  upload remain available, and a later provider can fill empty fields only.

### TMDB — rich capability, rejected for this storage contract

TMDB's official [movie search](https://developer.themoviedb.org/reference/search-movie) searches
original, translated and alternative titles and accepts language/region. Its image documentation
and append-to-response path cover localized posters and extra detail, and its published rate limit
is roughly 40 requests per second with `429` respected. Application authentication requires an API
key or bearer token. None is configured in the environment or local `.env`; the live unauthenticated
search returned HTTP 401, TMDB status code 7 (`Invalid API key`). No TMDB record response is claimed
as tested.

The decisive issue is the [API terms](https://www.themoviedb.org/api-terms-of-use): non-commercial
use requires TMDB logo/notice attribution, TMDB content may not be cached longer than six months,
and termination requires purging cached TMDB content. Akasha has no per-field provider provenance,
expiry or safe purge boundary. Adding that would reach persistence, refresh, import enrichment,
manual edits, offline rendering and operations. It is a future gated capability, not part of the
movie domain sprint. The owner action, if revisited, is to accept the current terms personally and
provide a read token only after that architecture is designed.

### OMDb — credentialed fallback, not selected

The official [OMDb API](https://www.omdbapi.com/) supports movie search and fetch by IMDb id, but
requires an API key; a live request without one returned HTTP 401 and `No API key provided`. Its
published content license is CC BY-NC 4.0 and its terms restrict use to personal/non-commercial
purposes. The dedicated Poster API is patron-only. It exposes no locale parameter comparable to
TMDB's language/region behavior. No OMDb record response is claimed as tested.

## Movie domain contract

The domain is flat: one film is one item and one personal entry. Television seasons/episodes remain
the separate hierarchy question DEC-077 rejected without live evidence.

| Seam | Movie answer |
|---|---|
| Package | `domains/movie/`, with no import of another domain |
| Provider | One `WikidataMovieProvider`; official Action API; bounded search and entity batches; descriptive User-Agent, `maxlag`, retry/429 behavior |
| Identity | Primary source `wikidata:Q…`; identifiers `wikidata`, `imdb`, `tmdb`, `letterboxd` when claims exist; one provider means no cross-provider merge |
| Recognizer | Wikidata entity URLs route directly. IMDb/TMDB URLs may resolve through a film-filtered external-id query only if the recorded fixture proves it; no consumer-page scrape |
| Metadata | Directors as `creators`; original title, countries, languages, genres, runtime, cast and description as opaque declared fields; neutral `year` remains the release year |
| Status | `unsorted`, `watchlist`, `watched`; default `watchlist` |
| Entry | `date_finished` labelled Watched and `reread_count` labelled Rewatches; no start date and no progress |
| Format | streaming, digital, Blu-ray and DVD; independent of watch status |
| Cover | No provider cover in the launch contract. Do not turn arbitrary `P18` photography into a poster. Manual upload remains available |
| Enrichment | None for hand-added records: fetch returns the structured record in one path. Letterboxd resolution belongs to its importer sprint |
| Shared changes | Published backend/frontend vocabularies and provider construction are the documented registration points. No schema, API model, screen or migration |

The one new problem belongs to the later connector rather than the domain: current Letterboxd
exports identify films with short `boxd.it` URIs, while Wikidata's `P6127` holds the Letterboxd film
slug. The importer plan must resolve that relationship at an external boundary or keep it as an
explicit ambiguity; it must never scrape metadata or silently merge on title/year.
