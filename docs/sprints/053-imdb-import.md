# Sprint 053 — The IMDb import

**Status:** completed
**Depends on:** 049, 052

**Roadmap revision:** 28

## Objective

An IMDb export — a ratings CSV or any list CSV, the Watchlist included — becomes films in the Movies
library and shows in the Series library, in one import, keyed on the IMDb id both domains already
use.

## Required context

- `docs/series-domain-viability.md`, the "IMDb — two CSV shapes, not one" section: the two headers,
  the `Title Type` routing table and the mappings, all measured on the owner's real files.
- Sprint 052's Outcome — the multi-domain contract as built.
- `docs/guides/adding-a-domain.md`, "Optional step — Add an importer", and in particular its list of
  five ways a reader takes a whole file down with one row.
- `docs/decisions.md`: DEC-080, DEC-093 (the seven defects the owner's own export did not exercise),
  DEC-101 (title plus exact year is a scoped offer, never a match), DEC-106.
- `backend/src/book_tracker/domains/movie/letterboxd.py` — the closest existing reader, and the one
  whose CSV bounding this should follow rather than reinvent.

## Current implementation baseline

Sprint 052 delivered the seam; observed at its closure, 2026-08-31:

- `Importer.item_types` is an ordered tuple and `NormalizedImportRecord.item_type` names the row's
  own domain, `None` meaning the first declared. A type the connector did not declare is refused at
  the boundary with `invalid_import_record`.
- The shared service resolves the domain per record at validation, at commit and in the enrichment
  guard. `IMPORTERS_BY_DOMAIN` is derived from declarations, so registration is one entry in
  `REGISTERED_IMPORTERS` and nothing else.
- **The skip channel this sprint's `Title Type` table needs already exists**:
  `ImportSnapshot.skipped` is a tuple of `ImportSkip(reason, count)`, where `reason` is the source's
  own word — so `Title Type` maps straight onto it, `"TV Episode"` and all. It reaches the preview
  summary as `skipped_unsupported` and `skipped_reasons`, never as row errors (DEC-112).
- The target selector ships and renders from `item_types`; unticked rows are dropped by the service
  and counted as `skipped_not_requested`. The chosen set folds into the fingerprint on a strict
  subset, so the same export previewed as films and then as shows is two imports.
- Both domains resolve an `imdb` identity through their providers.

**One thing this sprint has to answer, found while building 052:** `movie.enrichment.identity_kind`
is `letterboxd`, while `series` is `imdb`. An IMDb export carries no Letterboxd id, so post-commit
enrichment will queue the series rows and **not** the films unless something changes — either the
movie domain learns to enrich on `imdb` (which its Wikidata provider already resolves), or AC9 is
narrowed with the reason recorded. Decide it explicitly; do not let it pass as a silent gap.

## Deliverables

### 1. The reader

One connector, `imdb`, declaring `item_types = ("movie", "series")`. It lives in the package of its
first declared domain and is registered under both.

**Two shapes, detected from the header, never from column position:**

| Shape | Distinguishing columns |
|---|---|
| Ratings export | begins `Const, Your Rating, Date Rated, …` |
| List export (Watchlist is one) | begins `Position, Const, Created, Modified, Description, …` |

Both carry `Const`, `Title`, `Original Title`, `URL`, `Title Type`, `IMDb Rating`,
`Runtime (mins)`, `Year`, `Genres`, `Num Votes`, `Release Date`, `Directors`. A list export's
`Your Rating` and `Date Rated` sit at the end and are routinely blank. A header that is neither shape
is a file-level error with a code the connector declares and one imperative sentence saying what to
do.

**Routing, as a declared table with an explicit default of skip:**

| `Title Type` | Target |
|---|---|
| `Movie`, `TV Movie`, `Video` | `movie` |
| `TV Series`, `TV Mini Series` | `series` |
| everything else, including a value IMDb has not published yet | skipped and counted |

The default is *skip and count*, not *guess* and not *error*. A new IMDb title type must show up as a
number on the preview screen, never as a failed import.

**Mappings:**

- **Identity** — `Const`, the `tt` id, as an exact `imdb` identifier. Both target domains resolve it,
  so re-import matches with no provider traffic, and a film already in the library from a Letterboxd
  import matches exactly once Wikidata enrichment has added its `imdb` identifier.
- **Score** — `Your Rating`, IMDb's 1–10 integer, mapped **1:1**. There is no doubling here; that was
  Letterboxd's half-star scale. Blank is unscored. A value outside 1–10 is a row error.
- **Status** — a scored row suggests `watched` (movie) / `completed` (series); an unscored list row
  suggests `watchlist` (movie) / `plan_to_watch` (series). Persistence stays `unsorted` until Triage.
- **Dates** — `Date Rated` on a ratings export and `Created` on a list export become `date_added`.
  Neither is relabelled as a viewing date: IMDb does not record when you watched anything.
- **Metadata** — `Title` is the title and `Original Title` the original title when they differ;
  `Year` is the neutral year; `Genres` splits on commas; `Directors` becomes `creators` for a film
  and is usually blank for a series. `Runtime (mins)` is `runtime` for a film and `episode_minutes`
  for a series — the same column means two different things, and the routing table is where that is
  written down.
- **Not imported** — `IMDb Rating`, `Num Votes`, `Position`, `Modified`, `Description`, `Release
  Date`, `URL`. The first two are the crowd's opinion, not the owner's; `URL` is `Const` with
  decoration.

### 2. The declaration the screen renders

A guide in ordered steps naming both exports by where they actually live (Your Ratings → Export; Your
Watchlist → Export), an empty state, an `https` help link, the closed error vocabulary, and the two
target checkboxes Sprint 052 renders from `item_types`. No change to `ImportPage.tsx`.

### 3. Row-level failure, not file-level

Every trap the guide lists, checked against a file the owner did not write: a blank title, a
zero-valued numeric metadata field with a declared minimum, an out-of-range score, a repeated
`Const`, a tag with no letters or digits. Prefer a row error to a fatal one; reserve raising for a
file that is the wrong file.

The reader is bounded independently on rows and on bytes. The upload cap is on compressed bytes and
`ImportInputSpec.max_bytes` is not enforced for `kind="upload"` — bound the stream in the reader.

## Acceptance criteria

1. A ratings export and a list export are both read, detected from their headers, with the same
   mappings applied to each.
2. A file containing films and series produces records of both types in one preview, and commit
   creates items in both libraries.
3. `Title Type` routing follows the declared table; an unrecognised value is counted as skipped and
   is not an error.
4. Re-importing the same export matches every row on `imdb:` with no provider traffic and reports
   them as unchanged.
5. A film already present from a Letterboxd import, whose Wikidata enrichment has added its `imdb`
   identifier, matches **exactly** — no ambiguity, no duplicate.
6. Ratings map 1:1; a blank rating is unscored; `0` and `11` are row errors.
7. Unticking Movies leaves only series rows, and the excluded count is shown.
8. One bad row costs a row. The five documented traps are each proved with a synthetic fixture.
9. Post-commit enrichment fills both domains' records and installs posters for both — see the
   baseline note on `movie.enrichment.identity_kind`, which must be settled before this can pass.
10. **No change to `application/imports.py`, `api/imports.py`, `ImportPage.tsx` or `TriagePage.tsx`.**
    If this criterion cannot be met, the finding is the deliverable and Sprint 052 was incomplete.

## Required tests (TDD)

- Header detection for both shapes, and a refusal for a third.
- The routing table, one case per row including an invented future type.
- Every mapping, including the `Runtime (mins)` divergence between the two targets.
- Row-level errors for each documented trap; a file-level error only for the wrong file.
- Identity match against an existing Letterboxd-imported, Wikidata-enriched film.
- A generic route round-trip: preview, target selection, commit, undo.
- Every fixture is **synthetic**. The owner's files are walkthrough input and never a fixture.

## Verification

```bash
cd backend && uv run pytest tests/test_imdb_import.py tests/test_generic_imports.py \
  tests/test_multi_domain_imports.py tests/test_domain_conformance.py -q
cd frontend && npm run test
make check
make test
```

Then the walkthrough gate, on a disposable data directory, against the owner's **real** exports in
`exports/`: preview both files, check the routing counts, commit, approve rows of both types in
Triage, confirm posters and metadata arrive for both domains, and undo one batch. Sprint 047 closed
without this gate by owner direction (DEC-102) and left the Import and Triage screens unexercised for
movies; this is where that debt is paid.

## Explicit non-scope

- Trakt. Sprint 054.
- IMDb's `TV Episode` rows, in any form.
- Anything from an IMDb list beyond the columns named above — no list name, no list description, no
  ordering imported as a shelf.
- Scraping any IMDb page. `Const` is an identity; `URL` is decoration.

## Commit checkpoints

1. `[ADD] Read both IMDb export shapes`
2. `[ADD] Route IMDb rows to movies and series`
3. `[DOCS] Close sprint 053 and hand off`

## Risks and decisions to surface

- **`Title Type` is IMDb's vocabulary and it changes.** The default-to-skip rule is what stops that
  from being an outage. Do not replace it with a best-effort guess.
- The owner's real files are three rows in total. They exercise almost none of the failure paths,
  which is precisely DEC-093's lesson — the synthetic fixtures are the real test, and passing the
  owner's file is not evidence.
- An IMDb list export carries a `Description` per row that this deliberately drops. If the owner uses
  it as a note, say so in the Outcome rather than adding it quietly.

## Outcome

**Completed 2026-08-31.** Every acceptance criterion is implemented and verified, including the
walkthrough gate against the owner's real exports that Sprint 047 was excused from (DEC-102).

### The result that matters

**AC10 holds.** The whole connector is **one new module and one line in the registry**:

```text
backend/src/book_tracker/domains/movie/imdb.py   new
backend/src/book_tracker/domain/registry.py      +1 line in REGISTERED_IMPORTERS
```

`application/imports.py`, `api/imports.py`, `ImportPage.tsx` and `TriagePage.tsx` were **not touched
at all**, and neither was the frontend. The Import screen rendered a connector it had never heard of
— its guide, its help link, its drop zone, and a target checkbox per declared library — and Triage
rendered a mixed batch with each row's own vocabulary. Sprint 052's seam held for a connector it was
not built for, which is the only test of it that counts (DEC-093).

The one thing that did not hold was **enrichment**, and Sprint 052 had already found it: see below.

### Acceptance criteria

| # | Criterion | How it was proved |
|---|---|---|
| 1 | Both shapes read, detected from the header | `TestTwoShapes`; the same row maps identically through either, and a third header is refused whole |
| 2 | Films and series from one file, committed to both | `test_one_export_lands_in_both_libraries`; and live, on the owner's own ratings export |
| 3 | `Title Type` routes by the declared table, unknown counted | `TestRouting`, including an invented future type; skips are a tally by reason, not a row each |
| 4 | Re-import matches on `imdb:` and reports unchanged | `test_re_importing_the_same_export_reports_every_row_unchanged` — 0 created, 2 unchanged, no provider asked anything |
| 5 | A Letterboxd film with a Wikidata-added `imdb` id matches exactly | `test_a_letterboxd_film_that_wikidata_gave_an_imdb_id_matches_exactly` |
| 6 | Ratings 1:1; blank unscored; `0`/`11` row errors | `TestMappings`; and live — an 8 and a 10 rendered as 8 and 10 in Triage, unmarked |
| 7 | Unticking Movies leaves series and shows the count | `test_unticking_movies_leaves_only_series_and_counts_what_it_left` |
| 8 | One bad row costs a row | `TestRowErrorsNotFileErrors`, plus the same through the whole pipeline |
| 9 | Enrichment fills both domains and installs posters | Live, in about 6 seconds — see the measurement below. **Required DEC-113.** |
| 10 | No change to the four shared files | `git diff` over the sprint: none of them appear |
| — | No migration | None added |

### The open question the sprint was told to settle: settled, not narrowed

`movie.enrichment.identity_kind` was `letterboxd` and an IMDb export carries no Letterboxd URI, so
every film imported from IMDb would have been permanently unenriched — no poster, no genres, no
runtime — with nothing failing anywhere. **DEC-113** records the decision and the two alternatives
that were rejected. `EnrichmentSpec.identity_kinds` is now an ordered tuple; movies declare
`("letterboxd", "imdb")`; the backfill runs one statement per key and queues an item once, under the
first key it has; Wikidata's movie adapter accepts either, since it already resolved `P6127` and
`P345` exactly. Every other domain declares a one-element tuple and changes in no other way.

A pre-existing test asserted the defect as intended behaviour — *"a movie with no Letterboxd film is
never queued"* — and was rewritten to the new truth, keeping the negative that still holds: a film
with neither key is still never queued.

### Measured live, 2026-08-31, on the owner's real ratings export

Committed and enriched in about six seconds against the live boundary:

- the film → `creators: ["Christopher Nolan"]`, three genres, `runtime: 172`, a description, a poster;
- the show → its creator, three genres, `episode_minutes: 25`, a synopsis, `network: Netflix`,
  `airing_status: Ended`, `episodes: 77`, `seasons: 6`, a poster.

`runtime: 172` and `episode_minutes: 25` both came from IMDb's single `Runtime (mins)` column — the
divergence the routing table exists to write down, visible in real data.

### Commits

- `60b7a1a [ADD] Read both IMDb export shapes`
- `3d464e6 [ADD] Route IMDb rows to movies and series`

### Verification

- Focused: `tests/test_imdb_import.py` (75), plus `test_generic_imports.py`,
  `test_multi_domain_imports.py` and `test_domain_conformance.py`.
- `make test` — **1090 backend + 194 frontend**, one pre-existing Letterboxd zipfile warning.
- `make check` green; `make openapi` no diff (this sprint publishes no new API shape).
- Playwright, serial — 106 passed, 2 skipped.
- **Walkthrough gate**, live backend on a disposable data directory, the owner's two real exports as
  input: the IMDb tab with both target checkboxes; the ratings export previewing 2 rows, 0 errors;
  commit; Triage showing the film with `Watchlist`/`Watched` and the show with
  `Watching`/`Completed`/`On hold`/`Dropped`/`Plan to watch`, scores 8 and 10; **both rows approved
  through the UI**; the list export as a second batch; undo taking it back and leaving the first
  alone. **This pays Sprint 047's debt (DEC-102)**: a film has now been previewed, approved in
  Triage and undone through the real screens.

### Deviations

1. **The sprint's Verification block named `tests/test_imports.py`, which does not exist** — the
   same stale name Sprint 052 corrected. Fixed above.
2. **The fifth documented trap does not apply to this source.** DEC-093's list ends with
   `shelf_slug` raising on a tag of pure punctuation; an IMDb export has no tags and this connector
   creates no shelves by design. A malformed `Year` and a structurally short row are proved in its
   place, both real IMDb failure shapes.
3. **A structurally short row is a row error, not a skip.** Not specified either way. Counting file
   damage as "a kind this does not track" would hide it inside a number nobody reads twice, so the
   three cases are kept apart: a known type routes, an unknown type is counted under its own word,
   and a truncated row is a visible error.
4. **DEC-113 changed a shared contract**, which is more than a connector was supposed to cost. The
   sprint's baseline explicitly required this to be settled and not left silent, and the two cheaper
   options were rejected on the record.
5. **A rounding of the guide's anime/series merge argument.** It rested on `identity_kind` being one
   string per domain, which is no longer true. The verdict is unchanged and now rests on the
   load-bearing half: no single `provider_order` can answer both `mal` and `imdb`. Updated in place.

### Also observed, out of scope, recorded for the owner

- **The show's synopsis is Wikidata's one-line description, not TVmaze's real synopsis.** Live, the
  series came back with `synopsis: "serie de televisión animada"`. That is the designed rule working
  — `wikidata-series` is first in `provider_order` and the merge fills only empty fields, so TVmaze's
  fuller text never gets a turn (DEC-110, Sprint 050). It is nonetheless a poor synopsis on a real
  record, and worth a scoped decision: prefer the longer text, or reorder for that field.
- **An IMDb list export carries a `Description` per row, which this deliberately drops.** The owner's
  own list row has it blank. If it is used as a note, say so and it can be mapped.
- The two Sprint 046 defects (DEC-100) are still open and still not domain-specific.
