# Television series domain viability

**Status:** historical — measured 2026-08-31 during the planning session that produced Sprints
049–053. This is the evidence behind the series implementation plan, not a statement that series
already ship.

## Verdict

Television series are viable as a **flat** Akasha domain with **no schema change and no new
published vocabulary**. Two keyless providers were measured live and both passed:

- **Wikidata is primary**, for the same reasons it is primary for movies — CC0 structured data, no
  credential, official search, stable cross-catalogue identities — plus one it does not have for
  movies: every series entity measured carried a **number of episodes** claim, which is exactly the
  total the entry-progress control needs.
- **TVmaze is the fallback.** Keyless, no account, and the only measured source that supplies a real
  synopsis, an airing status and the Spanish-language shows Wikidata's title search files under an
  unusual class. Its data is CC BY-SA and requires crediting TVmaze as source.

Posters need no new source, no new host and no measurement of their own: Stremio's
`images.metahub.space`, already allowlisted and already keyed on the IMDb id for movies (DEC-103),
serves series posters from the identical URL shape. It answered 15 of 16 series.

The domain's cross-provider identity is the **IMDb id**. Wikidata publishes it as `P345` and TVmaze
publishes it as `externals.imdb`, so two candidates genuinely merge — and both planned importers
carry it as their primary key, so an import matches an existing item exactly rather than on a title.
This is the strongest identity position of any domain so far, stronger than anime's MyAnimeList id
and much stronger than movies' single-provider `wikidata:Q…`.

TMDB and TheTVDB are not selected. TheTVDB v4 requires a subscriber key. TMDB's terms remain what
Sprint 045 measured — mandatory attribution and a six-month cache limit against a store that keeps
provider metadata indefinitely — and DEC-103 already places Akasha knowingly outside them for the
~2% poster fallback. Widening that exposure to a whole domain's metadata is not something to do
without asking.

## Provider measurement

All calls below were made on 2026-08-31 with a descriptive Akasha User-Agent and **no credential of
any kind**. No response body is reproduced here beyond the aggregates.

### Wikidata — selected primary

Same two official Action API operations the movie adapter already uses: a `haswbstatement`-filtered
`list=search` for ids, then batched `wbgetentities`. One thing is different and it is load-bearing.

**A single `P31=Q5398426` filter — the movie adapter's shape, copied — is wrong for series.** A
television series is filed under at least five instance-of classes, and the single-class filter
missed five of fourteen representative titles outright:

| Title-search filter | Correct entity at rank 1 |
|---|---:|
| `haswbstatement:P31=Q5398426` (single class, movie-style) | 9 / 14 |
| `haswbstatement:P31=Q5398426\|P31=Q117467246\|P31=Q63952888\|P31=Q1259759\|P31=Q581714` | **14 / 14** |

The five it missed are not edge cases: `BoJack Horseman`, `Rick and Morty` and
`Avatar: The Last Airbender` are `animated television series` (`Q117467246`), `Chainsaw Man` is an
`anime television series` (`Q63952888`), and `Chernobyl` is a `miniseries` (`Q1259759`). Under the
single-class filter `Chainsaw Man` and `Rick and Morty` returned **nothing at all**, and
`BoJack Horseman` returned the fictional show-within-the-show instead. The unfiltered control was
worse than useless — `BoJack Horseman` unfiltered put the real series outside the top six.

**Resolution by IMDb id hit 13 of 13.** `haswbstatement:P345=<tconst>` returned the correct entity
at rank 1 for every title tried, including a series first aired in 2025. This is the operation both
importers depend on, and it is one bounded official search.

Field coverage across the thirteen fetched entities:

| Claim | Present | Note |
|---|---:|---|
| IMDb id `P345`, TMDB series `P4983`, TVDB `P4835` | 13/13 | all three, on every entity |
| number of episodes `P1113` | 13/13 | the progress total |
| number of seasons `P2437` | 11/13 | absent on the miniseries and the anime — **not** a completeness field |
| start time `P580` | 13/13 | the neutral `year` |
| genre `P136` | 13/13 | ≥1 each |
| original broadcaster `P449` | 12/13 | |
| creator `P170` | 10/13 | absent on two animated series and one long-running show |
| cast `P161` | 9/13 | **0 on every animated series measured** — not a completeness field |
| film/series poster `P3383` | **0/13** | Wikidata has no posters and structurally cannot |
| English and Spanish label | 13/13 | Spanish descriptions are full sentences |

Entity payloads are large: thirteen entities came back as **1.37 MB**, averaging ~105 KB each, with
`House of the Dragon` alone carrying 100 cast statements. DEC-099's bounded-batch rule therefore
applies unchanged and is if anything more necessary here than for films.

### TVmaze — selected fallback

The [official API](https://www.tvmaze.com/api) states it plainly: *"API calls are rate limited to
allow at least 20 calls every 10 seconds per IP address. If you exceed this rate, you might receive
an HTTP 429 error."* and *"Use of the TVmaze API is licensed by CC BY-SA. This means the data can
freely be used for any purpose, as long as TVmaze is properly credited as source."* No key, no
account, no registration. Images may be cached indefinitely.

Live results:

- **`/lookup/shows?imdb=<tconst>` answered 13 of 13** of the same series Wikidata resolved, each
  carrying `externals.imdb` and `externals.thetvdb` — so the IMDb id is a genuine merge key across
  both providers.
- **A synopsis on every hit**, 230–1045 characters, where Wikidata offers a one-line identification
  sentence and nothing more.
- **An airing status on every hit** (`Running` / `Ended`), which Wikidata expresses only as the
  presence or absence of an end-time claim.
- **Genres, network or streamer, average runtime and premiere date on every hit.**
- **It covers what Wikidata's title search does not.** `Los Simuladores` and `Okupas`, both
  Argentine, were found by name with the right premiere year and full Spanish-language records.
- **English only.** TVmaze has no locale parameter; its summaries are English regardless of the
  show's language. Wikidata remains the source of Spanish labels and descriptions.
- **Its images are the wrong sizes for the cover pipeline.** `medium_portrait` measured 210×295 —
  under the 600px target, so installing it would upscale — and `original_untouched` measured
  2000×3000 at 1.3 MB. Stremio's 500×750 is the right variant, so TVmaze is not a cover source here
  even though it has covers.

### Posters — no new work, no new host

`images.metahub.space/poster/medium/<imdb id>/img`, the deterministic keyless URL Sprint 048 built
for films, serves series from the same shape. Measured over sixteen series ids:

- **15 of 16 returned a poster**; the sixteenth was a clean `404`, which the cover pipeline already
  survives.
- All were **500×750 JPEG or WebP**, inside `MIN_PROVIDER_COVER_EDGE` and `MAX_COVER_EDGE`, except
  two legitimately different aspect ratios (500×739 and 500×667) that clear `MAX_COVER_ASPECT_RATIO`
  comfortably.
- The host is **already in `ALLOWED_COVER_HOSTS`**. No allowlist change, no new bound, no new
  measurement.

### What was rejected, and why

| Source | Key | Terms | Why not |
|---|---|---|---|
| **TMDB** | required | attribution + six-month cache limit | Same clash Sprint 045 measured. DEC-103 already accepts it knowingly for ~2% of *film posters*; extending it to a whole domain's metadata is a different decision and belongs to the owner, not to a sprint. |
| **TheTVDB v4** | required (subscriber PIN) | licensed per-application | Fails the no-setup requirement outright. |
| **OMDb** | required | CC BY-NC, personal use only, poster API patron-only | Adds a credential and no localization. Rejected for movies for the same reasons. |
| **Trakt API** | required (client id) | — | Would only re-fetch what the export already carries, at the cost of an OAuth handshake. |
| **Wikipedia REST summaries** | none | CC BY-SA | Genuinely good: `es`/`en` extracts existed for 9 of 9 series through Wikidata sitelinks, 97–796 characters, in Spanish. Not selected because TVmaze supplies a synopsis in one request already keyed on the identity the domain uses, and adding a third source to fill one field is cost without a gap. Worth revisiting only if Spanish synopses become a requirement. |

## Series domain contract

The domain is **flat**: one series is one item and one personal entry. Seasons and episodes are not
entities. DEC-077 priced that hierarchy across nine shared surfaces and rejected it, choosing a
per-domain `progress` field instead; Sprint 040 built it; anime has used it since Sprint 041. Series
is the case it was designed for and it needs nothing new.

| Seam | Series answer |
|---|---|
| Package | `domains/series/`, with no import of another domain |
| Providers | `WikidataSeriesProvider` primary, `TvmazeSeriesProvider` fallback; both keyless |
| Identity | `imdb:tt…`, published by **both** providers — a real cross-provider merge |
| Recognizer | Wikidata, IMDb, TMDB (`/tv/`), TVDB and TVmaze series URLs, all resolved through exact claims or exact lookups; no consumer-page scrape |
| Metadata | creators, original title, countries, languages, genres, episodes, seasons, network, episode length, airing status, cast, synopsis |
| Status | `unsorted`, `watching`, `completed`, `on_hold`, `dropped`, `plan_to_watch` — **every one already published** |
| Entry | the three passage fields, with `reread_count` labelled Rewatches |
| Progress | `ProgressSpec("Episodes watched", "episode", total_field="episodes")` |
| Format | streaming, digital, Blu-ray, DVD — **every one already published** |
| Cover | Stremio, keyed on the IMDb id, host already allowlisted |
| Enrichment | key `imdb`, order `("wikidata", "tvmaze")`, completeness `("creators", "genres", "synopsis")` |
| Shared changes | provider construction in `main.py`, one registry import and tuple entry, `ItemTypeName`. **No migration, no new status, no new format, no screen.** |

Because every status and format the domain wants is already published, registration points 4 and 5
of `docs/guides/adding-a-domain.md` — the backend enums and their frontend mirror — do not apply.
`ItemTypeName` is the single published-vocabulary change.

### The one thing the totals prove

Episode totals **disagree between sources and move over time**, and this is not a defect to
reconcile:

| Series | Wikidata `P1113` | TVmaze regular episodes |
|---|---:|---:|
| BoJack Horseman | 77 | 76 |
| Ted Lasso | 38 | 44 |
| House of the Dragon | 26 | 26 |
| Breaking Bad | 62 | 62 |
| Seinfeld | 180 | 180 |

The second row is the instructive one, and a Trakt archive makes it sharper still: an export records
a watched count against the total **that had aired on the day it was written**, and a season airing
since then raises the total underneath it. A count that was correct when stored is not wrong because
the show kept going. DEC-092 already settled the rule this needs — `total_field` is **for display only and never a bound**, `validate_progress` has a floor of
zero and no ceiling — precisely so a refresh cannot invalidate a count that was correct when it was
written. Series exercises that decision rather than revisiting it.

## Import measurement

Both archives are the owner's own, read in place. Nothing was extracted, copied into fixtures or
reproduced below beyond structure and aggregates; no title, rating, username, email address or
identifier belonging to the owner appears in this document.

### The shape both sources share, and the problem it creates

**A television tracker tracks films too.** Both measured exports carry movies and series in one
file, and `Importer.item_type` is a single string: a connector targets exactly one domain, and the
shared service resolves `DOMAINS[importer.item_type]` once for the whole batch. Neither source can
be read correctly under that contract. Sprint 051 exists for this and nothing else.

### IMDb — two CSV shapes, not one

The owner supplied two CSVs, and they are **different exports with different headers**:

| Export | Columns |
|---|---|
| Ratings | `Const, Your Rating, Date Rated, Title, Original Title, URL, Title Type, IMDb Rating, Runtime (mins), Year, Genres, Num Votes, Release Date, Directors` |
| List (this is what a Watchlist export is) | `Position, Const, Created, Modified, Description, Title, Original Title, URL, Title Type, IMDb Rating, Runtime (mins), Year, Genres, Num Votes, Release Date, Directors, Your Rating, Date Rated` |

Both carry `Const` — the IMDb `tt` id — on every row, which is the exact identity both target
domains want. The list shape adds `Position`, `Created`, `Modified` and `Description` at the front
and moves `Your Rating`/`Date Rated` to the end, where they may be blank. A reader must therefore
detect the shape from the header rather than from column position, and must accept a list export
whose rating columns are entirely empty.

`Title Type` is what routes a row to a domain. Observed values in the owner's files were
`TV Series` and `Movie`. IMDb's published vocabulary is wider, so the mapping is a declared table
with an explicit default of *skip*, not a guess:

| `Title Type` | Target |
|---|---|
| `Movie`, `TV Movie`, `Video` | movie |
| `TV Series`, `TV Mini Series` | series |
| `TV Episode`, `Short`, `TV Short`, `TV Special`, `Video Game`, `Podcast Series`, `Podcast Episode`, `Music Video` | skipped, counted and reported — never a row error |
| anything unrecognized | skipped and counted, so a new IMDb type is a number on a screen rather than a failed import |

Other mappings: `Your Rating` is IMDb's 1–10 integer and maps **1:1** to Akasha's score with no
doubling (unlike Letterboxd's half-stars); a blank is unscored. `Date Rated` is the arrival date on
a ratings export; `Created` is the arrival date on a list export. `Year` is the neutral year,
`Genres` splits on commas, `Directors` becomes `creators` for a film and is usually empty for a
series. A ratings row suggests `watched`/`completed`; a list row with no rating suggests
`watchlist`/`plan_to_watch`. `Runtime (mins)` is the film runtime for a movie and the *episode*
length for a series, which is a genuine semantic difference between the two targets.

The export carries **no watched-episode count**, so an imported series row has a status and a score
but no progress. That is correct and not a gap: IMDb does not track episodes.

### Trakt — an archive of raw API responses

The archive is a ZIP of 43 JSON members, each one a verbatim `/sync/*` or `/users/*` response. 26 of
them were the two bytes `[]` in the owner's export. The members that matter:

| Member | Holds | Owner's export |
|---|---|---:|
| `ratings-movies.json` | `rated_at`, `rating` 1–10, `movie.ids` | 1 |
| `ratings-shows.json` | `rated_at`, `rating` 1–10, `show.ids`, `aired_episodes` | 2 |
| `watched-movies.json` | `last_watched_at`, `plays`, `movie.ids` | 1 |
| `watched-shows.json` | `last_watched_at`, `plays`, `reset_at`, `show.ids`, `aired_episodes` | 2 |
| `watched-history.json` | one event per watch: `id`, `watched_at`, `action`, `type`, and the typed object | 115 |
| `lists-watchlist.json` | watchlist entries by type | empty |
| `collection-*`, `notes-*`, `comments-*`, `likes-*`, `network-*`, `hidden-*` | — | empty |
| `user-settings.json`, `user-profile.json` | account identity, **including an email address** | 1 each |

Every identity object is the Trakt `ids` block: `trakt`, `slug`, `imdb`, `tmdb`, `tvdb` for shows
and `trakt`, `slug`, `imdb`, `tmdb` for movies, plus a `plex` sub-object. **`imdb` was present on
every movie, show and episode object in the archive**, which is the identity both target domains
use. `tvdb` is present on shows and absent on movies, exactly as expected.

`watched-history.json` is the only member holding episode-level detail: 114 of its 115 events were
`type: "episode"`, each carrying both the `episode` (with `season` and `number`) and its parent
`show`. Rolling those up by distinct `(show, season, number)`, excluding season 0, produced 76
episodes for one show and 38 for the other — matching each show's `plays` exactly in this archive,
though `plays` counts rewatches in general and distinct episodes is the number `progress` means.
`aired_episodes` on the show object is the total **at export time**, which is what seeds the
`episodes` metadata field until enrichment refreshes it.

Deliberately not imported, and each an explicit product choice rather than an oversight:
`ratings-seasons.json` and `ratings-episodes.json` (a series holds one score — DEC-077's line),
collection, comments, notes, likes, follower graph, hidden items, playback progress, and everything
under `user-settings.json`/`user-profile.json`. The archive contains the owner's **email address**;
no reader reads that member, and no fixture may be cut from it.

`lists-watchlist.json` is empty in the owner's archive, so its populated shape is **declared from
Trakt's published API and not measured**. The reader must treat it as optional and must not fail an
archive that omits it.

### The anime question, evaluated and answered

Both sources will produce anime rows — the owner's archive contains one — and Akasha already has an
anime domain with its own MyAnimeList identity. The owner asked whether a row should switch to the
anime domain when the television providers cannot serve it, and asked for the idea to be measured
rather than assumed.

**Measured over fourteen anime series**, chosen to span the popular and the obscure and to include sequel seasons, which are where a catalogue is thinnest:

| Source | Coverage |
|---|---:|
| Stremio poster | 14 / 14 |
| Wikidata entity, with an episode count | 14 / 14 |
| TVmaze record with a synopsis | 13 / 14 |

The one gap — a sequel season absent from TVmaze — still had a Wikidata entity and a poster. The condition the switch would trigger on — television providers cannot serve this, the
anime provider can — did not occur once in fourteen tries, and would have fired partially in one.

**Verdict: not viable, and dropped.** An anime row from IMDb or Trakt becomes a series item. If the
owner wants that show in the Anime library instead, the existing anime search adds it there in one
step, which is a better answer than a heuristic that would fire on roughly one row in fourteen and
would need a cross-domain library lookup the importer contract deliberately scopes away.

The consequence is accepted and stated: a show may exist as both an anime item and a series item.
They share no identity — anime items are keyed on `mal:` and series items on `imdb:` — so nothing
merges them silently, and the duplicate is visible rather than hidden.
