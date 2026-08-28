# Sprint 047 — Letterboxd import for movies

**Status:** completed
**Depends on:** 046
**Roadmap revision:** 25

## Objective

Import a Letterboxd data-export ZIP into the completed movie domain with exact score/status/date
semantics, safe archive handling, provider enrichment and ordinary Import → Triage behavior. Use
the owner's root archive only as private walkthrough input; tests use synthetic fixtures.

## Required context

- `docs/movie-domain-viability.md`, especially the measured archive topology and importer mapping.
- `docs/guides/adding-a-domain.md` importer section and technical spec 6.1, 6.5 and 6.6.
- `docs/decisions.md`: DEC-076, DEC-078 through DEC-083, DEC-087, DEC-093, DEC-097 and DEC-098.
- Sprint 046 Outcome and actual `domains/movie/` provider/declaration code.
- Existing importers: Goodreads for CSV/near matches, MyAnimeList for a recent upload/enrichment
  path, and current `ImportMatcher`/`ImportRepository` behavior. Inspect, do not copy blindly.
- The untracked archive named in `docs/agent/HANDOFF.md`, read-only and never a fixture.

## Deliverables

### 1. A bounded multi-CSV ZIP reader

Add `domains/movie/letterboxd.py` and register it as `letterboxd`. It accepts an uploaded ZIP and
reads only `watched.csv`, `ratings.csv`, `diary.csv`, `reviews.csv` and `watchlist.csv` in memory,
without extraction. It refuses encrypted/duplicate/unknown/traversing members, malformed UTF-8 or
CSV, missing required headers, oversized members and excessive total expansion. Connector guidance
links to Letterboxd's official export page and says imports are snapshots whose owner data is never
overwritten.

Aggregate one normalized record per strict HTTPS `boxd.it`/Letterboxd film URI. Repeated diary and
review rows are ordered events, not duplicate items. Conflicting title/year values become row
errors; a malformed file raises a declared actionable reader error. Ignore profile, comments,
likes/lists, deleted and orphaned material explicitly.

### 2. Faithful personal-data mapping

Implement the measured mappings exactly:

- watched evidence suggests `watched`; watchlist-only suggests `watchlist`; persistence is
  `unsorted` until Triage approval;
- current rating wins, otherwise latest event rating; 0.5–5 multiplies exactly to Akasha 1–10;
- earliest source Date is `date_added`; latest Watched Date is Watched/`date_finished`;
- truthy Rewatch events count into Rewatches/`reread_count`;
- latest nonblank review seeds plain-text notes, stripping markup as text rather than trusting HTML;
- live tags union into safe shelves, with empty/punctuation-only tags ignored; and
- title/year plus exact Letterboxd URI form the skeletal item that Wikidata enrichment fills.

Current-state duplicates choose the latest valid source Date deterministically and retain source
provenance in the staged record. Blank is absence; zero/out-of-range rating, impossible dates and an
unusable URI are visible row errors. One bad row never aborts valid rows.

### 3. A neutral title/year ambiguity seam

**Scope the suggestion to the target domain.** `DomainRepository.match`
(`infrastructure/repositories.py`) scans every item row with no `items.type` filter. That is
tolerable for title+author, where a shared title *and* a shared creator is genuinely rare; it is
wrong for title+year with no creator, because a novel and its film adaptation routinely share both.
The optional year path must therefore also take the item type it is matching within, and a test must
prove a book named `Dune` published in 2021 is never offered as a candidate for the 2021 film.

Extend `ImportMatcher.match` with optional year. When no exact identity matches and no creator is
available, normalized title + exact year may return existing item ids as **ambiguous suggestions**.
It never auto-merges, and every importer not passing year behaves identically. Update technical
spec 6.1 and add repository/matcher tests proving same-title remakes remain separate and an explicit
choice attaches the incoming Letterboxd identity to the selected item.

This lets an export recognize a movie previously added through Wikidata even though one side holds
a short URI and the other a Letterboxd slug. Creating new remains an explicit preview choice.

### 4. Provider enrichment and lifecycle

**Already built in Sprint 046, and not to be rebuilt here:** `fetch_by_identifier("letterboxd", …)`
accepts a bare `P6127` slug, a full `letterboxd.com/film/<slug>/` URL and a `boxd.it` short URI
alike, resolving the last with HEAD requests only through a three-hop bound (DEC-100). Store the
export's URI as it comes; do not add a normalization pass that spends a request per row.

On commit, the existing domain enrichment uses the stored Letterboxd URI. The Wikidata adapter
performs HEAD-only short-URI resolution, exact `P6127` lookup and normal fetch. It fills empty movie
metadata only and leaves title, year, score, notes, statuses and edits intact. Provider miss/failure
is a visible typed job outcome and never rolls back the import.

Fingerprint replay, staged-source archival, Triage targets, row check approval, undo and re-import
all use the generic pipeline unchanged. No Letterboxd branch belongs in `api/imports.py`,
`application/imports.py`, `ImportPage.tsx` or `TriagePage.tsx`; the neutral matcher extension is the
only shared behavior change.

## Acceptance criteria

1. The supplied sample previews the measured unique-film count, with exact doubled scores and
   Watched suggestions, without its titles or values entering commits, fixtures or logs.
2. Synthetic fixtures prove watched/watchlist precedence, rating fallback/range, multiple diary
   events, rewatch count, watched date, review-to-plain-text, tag union and cross-file conflicts.
3. Archive attacks and malformed inputs produce declared actionable errors; row-local bad values do
   not discard valid films.
4. Exact Letterboxd identity replays/reimports without duplicates. Title+year only offers an
   ambiguity and never merges automatically; explicit use-existing attaches the source identity.
5. A new skeletal item enriches through recorded real HEAD/Wikidata responses. A miss retains the
   valid import and reports why; existing non-empty item and entry values are never overwritten.
6. Import, preview, commit, Triage row approval, undo and job progress work through existing generic
   API/screens with no connector-specific screen or route branch.
7. The private ZIP remains byte-for-byte unmodified and untracked. Synthetic fixtures contain no
   owner identity, films, ratings, reviews or paths.
8. No migration and no new API route. OpenAPI changes only if the registered importer declaration
   already makes a generated vocabulary change unavoidable.

## Required tests (TDD)

- `tests/test_letterboxd_import.py`: synthetic ZIP reader, mapping matrix, aggregation, replay,
  commit, enrichment, undo, row errors and every archive/error boundary. Each behavior gets an
  expected failing test before implementation.
- `tests/test_repositories.py` and generic importer tests: optional title/year ambiguity, remakes,
  explicit resolution and unchanged behavior for existing connectors.
- `tests/test_domain_conformance.py`: the new connector satisfies existing generic checks without a
  Letterboxd special case.
- Provider tests replay a public documented short-URI HEAD response and exact Wikidata `P6127`
  response; no normal test contacts Letterboxd or Wikidata.
- Frontend importer/Triage tests assert the declaration renders and a suggested movie target uses
  the ordinary row-only flow; add no movie branch to shared components.

## Verification

```bash
cd backend && uv run pytest tests/test_letterboxd_import.py tests/test_generic_imports.py \
  tests/test_repositories.py tests/test_domain_conformance.py tests/test_enrichment_pipeline.py -q
make openapi
make check
make test
cd frontend && npm run test:e2e
```

### Walkthrough gate

Against a disposable data directory, upload the owner's unmodified root ZIP through the real Import
screen. Verify measured preview counts without recording titles; commit; observe Wikidata jobs reach
terminal outcomes; approve each row target from Triage; inspect one Detail record; replay the same
ZIP; then import and undo a fresh disposable batch. Record only counts, status/score correctness,
job outcomes and UI/browser errors. Never open the live application database for writing.

## Explicit non-scope

- Sync/write-back to Letterboxd, OAuth, scraping film/review pages or importing Letterboxd lists.
- Deleted/orphaned content, comments, likes/favorites, profile fields or historical review display.
- A viewing-history entity, multiple dated reviews in the UI, recommendations or social data.
- TMDB/OMDb, automatic posters or provider provenance/expiry.
- Container/build work unless packaging actually changes.

## Commit checkpoints

1. `feat(sprint-047): read a bounded Letterboxd export`
2. `feat(sprint-047): map Letterboxd films into movie entries`
3. `feat(sprint-047): suggest title-year import matches`
4. `feat(sprint-047): enrich and verify the Letterboxd flow`
5. `docs(sprint-047): close sprint and hand off`

## Risks and decisions to surface

- The owner sample has two current ratings and no diary/review/watchlist rows. Official format docs
  and adversarial synthetic fixtures must cover those shapes; do not generalize two rows into a
  file-format claim.
- ZIP compressed size is not an expansion bound. Total/member ceilings are independently enforced.
- Title/year is weak identity even for films. It is a prompt, never an automatic match.
- Following a short URI is permitted only as bounded identity resolution. Parsing the destination
  HTML for metadata would cross the provider and terms boundary this plan deliberately avoids.

## Outcome

Delivered, and **verified at a reduced level at the owner's explicit direction.** What that means in
practice is stated under Verification below; read it before treating any gate here as equivalent to
Sprint 046's.

### What ships

`domains/movie/letterboxd.py` reads a Letterboxd export ZIP and is registered as the `letterboxd`
connector on the movie domain. It aggregates the five live tables — `watched`, `ratings`, `diary`,
`reviews`, `watchlist` — into one record per Letterboxd URI, mapping status, score, dates, rewatches,
review text and tags exactly as the Sprint 045 measurement specified. Deleted, orphaned, likes,
lists, comments and the profile are read past deliberately.

The archive is checked before it is opened: encrypted members, names that escape the root, a member
named twice, non-UTF-8 members, missing columns and declared sizes over the expansion ceiling are
each refused with a `user_message` and an `action`. Compressed size is never treated as a bound.

The one shared behaviour change is matching rule 5, now in technical spec 6.1: **normalized title
plus exact year, scoped to one item type**, as an ambiguous suggestion only, and only when the source
carries no creator. `DomainRepository.match` gained optional `year` and `item_type`; every existing
connector passes neither and gets the identical query it had.

### Acceptance criteria

1. **The owner's real archive previews as measured.** Two unique films, both suggesting `watched`,
   scores doubled exactly from their half-star ratings, zero row errors. No title, URI, rating or
   review from it appears in this repository, its fixtures or its logs.
2. **The mapping matrix is proved on synthetic archives.** Watched/watchlist precedence, current
   rating over event rating, latest event rating as fallback, the full half-star scale, blank as
   unrated, out-of-range as a row error, multiple diary events as rewatches, earliest source date as
   `date_added`, latest `Watched Date` as Watched, review markup read as text, and tags unioned into
   shelves across events.
3. **Archive attacks and malformed inputs are refused; bad rows stay local.** An unusable URI in one
   row leaves the valid film in the next row untouched and intact.
4. **Exact identity matches; title and year only offer.** A film held under the export's own URI is
   an exact match; one held under Wikidata's slug is offered as an ambiguity and never merged; a
   1977 film is not offered for a 2018 remake; and a *book* named `Dune` from 2021 is never offered
   as a candidate for the 2021 film.
5. **Enrichment resolves the stored short URI end to end.** Both jobs from the real archive reached
   `succeeded`: each `boxd.it` URI was resolved by HEAD, looked up by exact `P6127`, and filled
   directors, runtime and Spanish genres into an otherwise empty record. No covers, as designed.
6. **The generic pipeline carries it unchanged.** Preview, commit, Triage and fingerprint replay all
   work with no connector-specific branch. Re-uploading the same archive returned `state: committed`
   rather than duplicating anything, and both films appear as ordinary unsorted Triage rows — which
   is the first time any movie has reached Triage at all.
7. **The private archive is unmodified and untracked.** 2,908 bytes, unchanged; every committed
   fixture is invented in `tests/test_letterboxd_import.py`.
8. **No migration and no new API route.** `make openapi` produced no diff, so the registered
   connector changed no generated vocabulary.

### Verification — reduced, and here is exactly how

The owner directed this sprint to skip the in-depth testing pass. What was run:

- `tests/test_letterboxd_import.py`: **61 passed** — the mapping matrix, every archive-safety
  boundary, and the matcher seam including the cross-domain case.
- Conformance and every other importer suite (`test_domain_conformance.py`, `test_generic_imports.py`,
  `test_repositories.py`, `test_goodreads_import.py`, `test_myanimelist_import.py`,
  `test_calibre_import.py`): **239 passed**, so the three connectors this sprint did not touch are
  provably unchanged by the matcher extension.
- `make check`: passed. `make openapi`: no diff.
- Full unit suites: **880 backend**, **189 frontend**.
- A real end-to-end pass on the owner's archive through the running application: preview → commit →
  enrichment → Triage → replay, against live Wikidata.

**What was not run, and is therefore not evidence:**

- **The Playwright suite.** No frontend code changed and the Import screen renders connectors from
  their declaration, but that reasoning is an argument, not a test result.
- **The walkthrough gate.** The Import → Triage flow was exercised through the **API**, not through
  the real screens. Nobody has seen the Letterboxd connector rendered on the Import page, approved a
  movie row from the Triage UI, or undone a movie batch from a browser. Undo in particular has no
  coverage in this sprint at any level.
- **Frontend importer/Triage tests** for the new declaration were not added.

### Commits

`a076f0c` read a Letterboxd export into movie records · plus this closure commit.
