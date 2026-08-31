# Sprint 053 — The IMDb import

**Status:** planned
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

To be observed at activation. Expected: `Importer.item_types` exists, records carry an `item_type`,
the target selector ships, and both the movie and series domains resolve an `imdb` identity through
their providers.

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
9. Post-commit enrichment fills both domains' records and installs posters for both.
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
cd backend && uv run pytest tests/test_imdb_import.py tests/test_imports.py \
  tests/test_domain_conformance.py -q
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

_Not started._
