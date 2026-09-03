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

## Letterboxd export measurement

The owner's untracked ZIP was read in place with Python's CSV reader; nothing was extracted,
rewritten or copied into fixtures. Only structure and aggregates were printed. The archive has 16
CSV members and 1,022 uncompressed bytes in this small sample:

| Member | Header | Sample rows |
|---|---|---:|
| `profile.csv` | Date Joined, Username, Given Name, Family Name, Email Address, Location, Website, Bio, Pronoun, Favorite Films | 1 |
| `watched.csv` | Date, Name, Year, Letterboxd URI | 2 |
| `ratings.csv` | Date, Name, Year, Letterboxd URI, Rating | 2 |
| `diary.csv` | Date, Name, Year, Letterboxd URI, Rating, Rewatch, Tags, Watched Date | 0 |
| `reviews.csv` | diary fields plus Review | 0 |
| `watchlist.csv` | Date, Name, Year, Letterboxd URI | 0 |
| `comments.csv` | Date, Content, Comment | 0 |
| `deleted/{diary,reviews,comments}.csv` | Same headers as their live equivalents | 0 |
| `orphaned/{diary,reviews,comments}.csv` | Same headers as their live equivalents | 0 |
| `likes/films.csv` | Date, Name, Year, Letterboxd URI | 0 |
| `likes/{reviews,lists}.csv` | Date, Content | 0 |

The two watched identities were distinct and appeared exactly once in `watched.csv` and once in
`ratings.csv`; the cross-file overlap was complete. Every populated date matched `YYYY-MM-DD`.
Every film identity was an HTTPS `boxd.it` URL with one path segment. Ratings were populated,
within Letterboxd's documented 0.5–5 scale and on half-star boundaries. No title, user name, URI,
rating attached to a title, review or other personal value is reproduced here.

Letterboxd's official [export page](https://letterboxd.com/user/exportdata/) confirms that the ZIP
contains CSVs for profile, films, reviews, lists and more, including deleted content and reviews of
deleted titles. Its official [import-format documentation](https://letterboxd.com/about/importing-data/)
provides the semantics the export page does not spell out: UTF-8 CSV; Letterboxd URI, TMDB id, IMDb
id, title/year/directors as identity alternatives; rating 0.5–5; `Rating10` 1–10; `WatchedDate` as
the diary date; a boolean rewatch flag; tags; and review text/HTML. The observed export uses spaced
headers (`Letterboxd URI`, `Watched Date`) rather than the import template's compact names.

One supplied short URI was probed without logging either the URI or its film slug. Both GET and
HEAD followed exactly one redirect and ended at HTTPS `letterboxd.com/film/<slug>/` with status
200. This is identity resolution, not page scraping: the provider needs only the redirect target,
then searches Wikidata's `P6127` claim for that exact slug. The implementation must refuse any
redirect outside the two named hosts and must never read or parse the Letterboxd HTML body.

### Initial importer contract

The reader consumes `watched.csv`, `ratings.csv`, `diary.csv`, `reviews.csv` and `watchlist.csv` and
aggregates them into one record per normalized Letterboxd URI. It deliberately ignores profile,
comments, likes, lists, deleted and orphaned content. Those are separate product choices; silently
restoring deleted material or manufacturing a `Liked` shelf is not import fidelity.

The mappings are:

- **Identity:** exact `letterboxd` identifier holding the normalized HTTPS `boxd.it` URI. Re-import
  therefore matches without provider traffic. The Wikidata provider's enrichment lookup follows a
  HEAD redirect to the film slug, searches exact `P6127`, and refuses zero or multiple matches.
- **Status:** any live watched/rating/diary/review evidence suggests `watched`; a film present only
  in watchlist suggests `watchlist`. Persistence remains `unsorted` until Triage approval.
- **Score:** current `ratings.csv` wins; otherwise the most recent diary/review rating. A populated
  0.5–5 value is multiplied by two into Akasha's exact 1–10 integer scale. Blank means unscored;
  zero and out-of-range values are row errors, not absence.
- **Dates:** the earliest source `Date` becomes `date_added`. Only `Watched Date` may become the
  entry's Watched (`date_finished`) value, choosing the latest event. `watched.csv.Date` is not
  relabelled as a viewing date.
- **Rewatches:** the count of truthy `Rewatch` diary/review events becomes `reread_count`, rendered
  by the movie domain as Rewatches. Repeated diary rows are events, not duplicate items.
- **Review:** the most recently dated nonblank review seeds plain-text notes on a newly created
  entry. HTML is parsed to text and never rendered as source markup. Re-import never overwrites an
  existing note.
- **Tags:** the union of live diary/review tags becomes shelves through the existing safe slug
  normalizer. Empty or punctuation-only tags are ignored rather than aborting the file.
- **Metadata:** title and year come from the export; Wikidata background enrichment fills the empty
  declared fields and optional cover only under the ordinary fill-empty rule.

Files and rows are bounded independently. The ZIP reader refuses encrypted members, duplicate
member names, unknown paths, path traversal, malformed UTF-8/CSV, missing required headers and an
excessive total expanded size. It reads the five allowed live members without extracting them.
Disagreement on title/year for one URI is a visible row error. Duplicate current-state rows resolve
by latest source `Date` with a recorded warning; diary/review rows remain ordered events.

### The one shared importer seam

An item added through Wikidata carries the Letterboxd slug, while an export carries the short URI.
Before enrichment those values cannot be exact matches. `ImportMatcher` therefore gains an optional
neutral `year` input and may offer normalized title + year as an **ambiguous suggestion only** when
no exact identifier matches. It never auto-merges. Selecting the existing item makes import commit
attach the exact short URI, after which the ordinary `letterboxd` enrichment key works. This is a
domain-neutral extension of technical spec 6.1, not an `if movie` branch.

If the owner creates a genuinely distinct film with the same title and year, the preview displays
the candidates and permits Create new. If no candidate exists, the importer creates the skeletal
movie and its post-commit enrichment resolves the short URI. A provider miss leaves the valid
title/year/entry intact with a typed job error; it never sends the importer to scrape a film page.

## Cinemeta — second source, measured 2026-09-03 for Sprint 063

Sprint 062 (DEC-125) removed the self-inflicted half of the movie domain's single-adapter outage
risk; it did not add redundancy. This section is Sprint 063's AC1 gate: coverage measured before
the adapter is trusted, over the sample below, compared against Wikidata's own production filter
(`haswbstatement:P31=Q11424`) on the same fifteen titles.

| Film | Note | Cinemeta: found | IMDb id | Description | Runtime | Wikidata: found |
|---|---|---|---|---|---|---|
| Inception | popular, English | yes | tt1375666 | yes | yes | yes |
| The Godfather | popular, English, classic | yes | tt0068646 | yes | yes | yes |
| Parasite | popular, Korean | yes | tt6751668 | yes | yes | yes |
| Seven Samurai | classic, Japanese | yes | tt0047478 | yes | yes | yes |
| City of God | popular, Portuguese | yes | tt0317248 | yes | yes | yes |
| Amélie | popular, French | yes | tt0211915 | yes | yes | yes |
| Come and See | obscure, Russian/Belarusian | yes | tt0091251 | yes | yes | yes |
| Tokyo Story | arthouse, Japanese | yes | tt0046438 | yes | yes | yes |
| The Handmaiden | Korean | yes | tt4016934 | yes | yes | yes |
| Relatos Salvajes | Argentine, Spanish | yes | tt3011894 | yes | yes | yes |
| El Secreto de Sus Ojos | Argentine, Spanish | yes | tt1305806 | yes | yes | yes |
| Dune: Part Two | recent (2024), popular | yes | tt15239678 | yes | yes | yes |
| Oppenheimer | recent (2023), popular | yes | tt15398776 | yes | yes | yes |
| Aftersun | recent (2022), obscure | yes | tt19770238 | yes | yes | yes |
| La Ciénaga | obscure, Argentine, Spanish | yes | tt0240419 | yes | yes | yes |

**15/15 found, 15/15 with an IMDb id, a description and a runtime.** Wikidata's own production
filter matched all fifteen on the same sample, so Cinemeta's coverage here is not worse — it is
equal. Latency across the run was 0.04–6.16 s (`GET /catalog/movie/top/search=`), with one 6.16 s
outlier on `The Handmaiden`; every `/meta/movie/` fetch after the first request in a burst answered
in under 0.5 s, consistent with the endpoint's own `cacheMaxAge`.

Two shapes confirmed live, matching what the sprint's baseline measurement found on 2026-09-02:

- `/meta/movie/<id>.json` occasionally answers **307** to `cinemeta-live.strem.io` rather than
  serving from `v3-cinemeta.strem.io` directly (observed on `Okupas`' series request and on the
  2018 `Suspiria` fetch below). The shared provider client already follows redirects
  (`create_provider_client`'s `follow_redirects=True`), so this needs no adapter-side handling —
  recorded here because an implementation using a bare non-redirecting client would silently
  break.
- The catalog search response's `poster` field is `m.media-amazon.com`, never allowlisted; the
  `/meta/` response's own `poster` is `images.metahub.space` at the `small` size. Neither is used —
  the adapter builds the medium-size metahub URL from the IMDb id, exactly as the existing
  `metahub_poster_url` helper already does for Wikidata and TVmaze.

**Identity pair, confirmed live:** searching `Suspiria` returns both `tt0076786` (Argento, 1977) and
`tt1034415` (Guadagnino, 2018) as distinct records, each with its own full `/meta/` response — the
AC4 case.

**Verdict: coverage clears the gate.** Cinemeta answers this sample at parity with Wikidata's own
filter and with complete field coverage on every hit. The adapter proceeds as planned.
