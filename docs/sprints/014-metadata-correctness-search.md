# Sprint 014 — Metadata correctness and search relevance

**Status:** completed
**Depends on:** 013
**Roadmap revision:** 6

## Objective

Searching for a book finds it, and every added or imported book acquires its real metadata and
cover, verified against live providers rather than mocks.

## Required context

1. `AGENTS.md`, including the walkthrough gate in section 3
2. `docs/assessment.md` sections 2 and 4 (verified defects and why tests missed them)
3. `docs/specs/product-spec.md` sections 4.2 (providers), 4.3 (search flow), 4.5 (cache-on-add), and 5.3 (shared import pipeline)
4. `docs/specs/technical-spec.md` sections 6.2 (provider boundary) and 10 (testing and quality gates)
5. `docs/decisions.md` DEC-024, DEC-025, and DEC-026
6. Sprint 013 Outcome and `docs/agent/WORKFLOW.md`
7. `backend/src/book_tracker/infrastructure/providers.py`, `backend/src/book_tracker/domain/providers.py`, `backend/src/book_tracker/application/enrichment.py`, `backend/src/book_tracker/application/providers.py`, and `backend/src/book_tracker/main.py`
8. `backend/tests/test_jobs.py`, `backend/tests/test_providers.py`, and `backend/tests/test_provider_api.py`

## Diagnosed defects and current implementation baseline

Four defects were confirmed by reading the code and querying live systems on 2026-08-08.

1. **Background enrichment always fails.** `OpenLibraryProvider.fetch_by_isbn` delegates to
   `self.fetch(isbn)`, which requests `https://openlibrary.org/books/{isbn}.json`. That endpoint
   takes an OLID, not an ISBN. Measured: `/books/9780441013593.json` returns **404**;
   `/isbn/9780441013593.json` returns **302**. Product spec section 4.2 already specifies the
   `/isbn/` form. The exception is swallowed by a bare `except Exception` in
   `application/enrichment.py`, recorded as an opaque failure string, and never retried against
   another provider. Every enrichment job for every imported book has failed since Sprint 011.
   The shared `httpx.AsyncClient` in `main.py` does not set `follow_redirects`, so correcting the
   URL alone is insufficient — a 302 would pass `raise_for_status` and then fail JSON parsing.
2. **Search ranking discards provider relevance.** `merge_and_rank` in `domain/providers.py`
   sorts merged candidates by `(title != query, language not in {es,en}, cover is None,
   normalize_text(title), source, source_id)`. The fourth key is alphabetical, so results are
   re-ordered A–Z and the provider's relevance ordering is destroyed. Product spec section 4.3
   calls the ranking "deliberately dumb", which means do not over-engineer it — not discard the
   ordering the providers already computed.
3. **Google Books is never registered.** `main.py` appends the provider only when
   `google.enabled`, which requires a non-empty `GOOGLE_BOOKS_API_KEY`. There is no `.env`, so
   search runs on Open Library alone with no warning and no UI signal. Product spec section 2
   selected Google Books specifically for Spanish-language coverage.
4. **Edition years are missing from most search results.** The work-resolution loop in
   `OpenLibraryProvider.search` is gated on `and not enriched`, which is true only on the first
   iteration, so results 2..20 keep `year=None`.

Additionally, `frontend/src/pages/HomePage.tsx` builds its shelf filter from
`entries.flatMap(entry => entry.shelves)` — only the pages loaded so far — while
`GET /api/shelves` exists and is already used by `ShelvesPage`, `DetailPage`, and `AddPage`.

All 122 backend tests pass today. `backend/tests/test_jobs.py` replaces `fetch_by_isbn` with an
`AsyncMock` in all five places it appears, which is precisely why defect 1 survived thirteen
sprints of green gates.

## Deliverables

- Correct Open Library ISBN lookup: `/isbn/{isbn}.json` plus `follow_redirects=True` on the
  shared provider client in `main.py`.
- Google Books fallback in `application/enrichment.py` when Open Library returns nothing or
  fails, using the existing `GoogleBooksProvider.fetch_by_isbn`.
- Typed enrichment failure handling replacing the bare `except Exception`, persisting a
  structured reason on the job row and exposing it through `GET /api/import/jobs/{id}`.
- Relevance-preserving `merge_and_rank`: retain each candidate's provider-returned position,
  interleave providers fairly, and demote the existing signals to tie-breakers only.
- Removal of the `not enriched` gate so every search result resolves an edition year, with the
  additional lookups bounded and concurrent rather than truncated to the first row.
- Provider health on the existing health endpoint plus a startup warning when
  `GOOGLE_BOOKS_API_KEY` is absent, so Sprint 015 can render a degraded-search state.
- A backfill path that re-enqueues enrichment for items already persisted with empty fields.
- `.env` created from `.env.example` with the owner-supplied Google Books key.

## Acceptance criteria

1. `OpenLibraryProvider.fetch_by_isbn` returns a populated `ItemPayload` for a real ISBN, proven
   by a test that replays a recorded Open Library response including the 302 redirect. No test
   for this method may use a bare `AsyncMock` substitute.
2. An enrichment job whose Open Library lookup fails or returns no usable data falls back to
   Google Books and fills the item; a job that fails on both records a typed, human-readable
   reason retrievable through `GET /api/import/jobs/{id}`.
3. For a query matching a known title, the intended edition appears in the first three merged
   results and is not displaced by an alphabetically earlier unrelated title. A regression test
   pins this with a fixture where the correct answer sorts late alphabetically.
4. Every result returned by `GET /api/search` carries an edition year where the provider exposes
   one, not only the first result.
5. Starting the backend without `GOOGLE_BOOKS_API_KEY` logs an explicit warning and reports the
   provider as unavailable on the health endpoint; starting it with a key reports both providers
   available. Search never fails outright while at least one provider answers.
6. Re-running enrichment backfill over items with empty metadata fills them without touching any
   populated field or any `entries` row, preserving the fill-empty-only invariant.
7. The `/` shelf filter lists every shelf from `GET /api/shelves` regardless of how many library
   pages have loaded.

## Required tests (TDD)

- Provider: recorded-response test for `/isbn/` lookup including redirect following; malformed
  and 404 responses raise `ProviderPayloadError` rather than leaking `httpx` errors.
- Ranking: a fixture where the relevant result is alphabetically last proves it still ranks
  first; a fixture with duplicate ISBN13 across providers proves merge keeps one card and both
  source refs.
- Enrichment: Open Library miss falls back to Google Books; both-miss records a typed reason;
  a populated field is never overwritten; a cancelled batch still cancels the job.
- Search: every candidate carries a year when the provider exposes one.
- Config/health: missing key warns and degrades; present key reports healthy.
- Frontend: `HomePage` renders shelves from the shelves endpoint, asserted with a fixture whose
  shelf set is absent from the loaded entries.

## Verification

Run and record:

```bash
python scripts/validate_project.py
make format
make check
make test
cd frontend && npm run test:e2e -- --project=chromium
cd .. && make build
git diff --check
```

Then perform the mandatory walkthrough required by `AGENTS.md` section 3 and record it in the
worklog. Start the backend with a real `GOOGLE_BOOKS_API_KEY`, then:

1. Search a Spanish-language title (for example `Rayuela Cortázar`) and confirm the intended
   edition appears near the top with a cover and a year.
2. Add it, and confirm the detail page shows real metadata and a locally cached cover.
3. Import the synthetic Calibre fixture, wait for enrichment, and confirm previously blank rows
   acquire covers and metadata.
4. Stop the network, reload the library, and confirm every page still renders from cache.

Record what was searched, what ranked where, and what filled. Command output alone cannot
complete this sprint.

## Explicit non-scope

- No component library, design token, or visual work (Sprint 015).
- No animation or microinteraction work (Sprint 016).
- No performance benchmarking, axe audit, or security limits (Sprint 017).
- No container, backup, or release work (Sprint 018).
- Do not redesign the search results UI; only its ordering and completeness change here.

## Commit checkpoints

1. `test: reproduce dead Open Library ISBN enrichment`
2. `fix: correct Open Library ISBN lookup and follow redirects`
3. `feat: fall back to Google Books during enrichment`
4. `test: pin provider relevance ordering`
5. `fix: preserve provider relevance in merged search results`
6. `feat: report provider health and warn on missing API key`
7. `feat: backfill enrichment for items with empty metadata`
8. `fix: source library shelf filter from the shelves endpoint`
9. final `docs(sprint-014): close sprint and hand off`

## Risks and decisions to surface

- Recorded-response fixtures must be committed and stable. Decide where they live
  (`backend/tests/fixtures/providers/`) and never re-record them silently.
- Open Library redirects `/isbn/` to `/books/{olid}`; confirm the redirect target is an edition
  and not a work before trusting `items.year`.
- Interleaving two providers fairly when one returns far more results needs an explicit rule;
  record whichever is chosen.
- Removing the `not enriched` gate multiplies Open Library calls per search. Bound concurrency
  and respect the existing rate limiter, and record the measured added latency.
- The owner must supply the Google Books API key before this sprint can be verified.

## Outcome

**Status:** completed 2026-08-09.

### Delivered behavior, per acceptance criterion

1. **Open Library ISBN lookup works.** `fetch_by_isbn` requests `/isbn/{isbn}.json`, reads the
   edition key from the redirect target, and rejects a target that is not an edition. The shared
   client is built by one factory with `follow_redirects=True` that the application and the tests
   both use. Proven by `tests/test_provider_recordings.py` replaying the captured 302 and edition
   record; 404, unreachable, malformed, and titleless responses raise `ProviderPayloadError` with
   a stable `code`. No test of this method uses an `AsyncMock`. Commits `97a7fd1`, `706a1aa`.
2. **Google Books fallback and typed failures.** Enrichment walks Open Library then Google Books,
   treating a payload with no year, cover, or metadata as a miss. The bare `except Exception` is
   gone; each attempt contributes a sentence, and migration `0006` adds `jobs.error_code`, which
   `GET /api/import/jobs/{id}` returns beside `error`. `tests/test_enrichment.py` proves the
   fallback, the typed reason, and the unconfigured-provider wording against recordings.
   Commit `3437647`.
3. **Relevance preserved.** `merge_and_rank` keeps each candidate's provider-returned position,
   takes the better position for merged duplicates, interleaves providers, and demotes
   title/language/cover to tie-breakers. The normalized title is no longer a sort key.
   `tests/test_search_ranking.py` replays a real "Rayuela Cortázar" search where the intended
   edition sorts fifth alphabetically and first by relevance. Commits `91118c5`, `31c5b8e`.
4. **Every result carries a year.** The `not enriched` gate is removed; undated results resolve
   concurrently behind a semaphore of 5. Candidates are paired with their work at construction,
   which also fixed a latent misalignment when a row yields no candidate. `_year` now finds a year
   anywhere in the value, so Open Library's `"Mar 09, 2005"` dates parse. Commit `394926b`.
5. **Provider health.** Startup warns when `GOOGLE_BOOKS_API_KEY` is absent;
   `GET /api/health/providers` reports per-provider availability and a `degraded` flag; readiness
   stays about the database. Commit `4f838df`.
6. **Backfill.** `POST /api/enrichment/backfill` queues items with an ISBN and an empty cover,
   year, publisher, page count, or description, skipping those already pending. Filling never
   touches a populated field or any `entries` row. Commits `4e3d825`, `4dcd8c2`.
7. **Shelf filter.** `/` reads `GET /api/shelves` instead of deriving the list from loaded pages.
   Commit `bbf2371`.

### Deviations and prerequisite repair

- **The enrichment queue had neither a producer nor a consumer** (DEC-027). Nothing in production
  code called `enqueue`, and nothing called `tick`. The broken ISBN URL was never even reached.
  Repaired inside this sprint because AC2, AC6, and the walkthrough are unverifiable without it:
  importers now enqueue on commit, the lifespan drives the runner, and enrichment installs a
  missing cover after its transaction commits.
- Two endpoints were added that the product spec's API list did not name
  (`POST /api/enrichment/backfill`, `GET /api/health/providers`). Both are now listed there.
- Product spec 4.3's ranking rule was reconciled with the relevance-preserving behavior; "dumb"
  means not over-engineering the ranking, not discarding provider relevance.
- `scripts/validate_project.py` exempts `backend/tests/fixtures/providers/` from text hygiene:
  recordings are byte-faithful captures and reformatting them would change what tests assert.
- Sprint 013's `AsyncMock` enrichment tests were replaced rather than kept alongside; the four
  behaviors they covered are now proven against recordings.

### Verification

| Command | Result |
|---|---|
| `python scripts/validate_project.py` | passed |
| `make format` | applied, no residual diff |
| `make check` | passed (ruff, prettier, eslint, mypy, tsc, OpenAPI export/type check, validator) |
| `make test` | backend **154 passed**, frontend **39 passed** |
| `npm run test:e2e -- --project=chromium` | **33 passed, 2 skipped** (the two live-provider specs) |
| `make build` | backend wheel + `dist/` built |
| `git diff --check` | clean |

### Walkthrough (mandatory gate, AGENTS.md section 3)

Run against a copy of the real `data/` directory with the owner's `GOOGLE_BOOKS_API_KEY`.
Full narrative in `docs/agent/worklog.md`. Summary:

- `GET /api/health/providers` reported both providers available with the key, and
  `degraded: true` with a reason for Google Books when the key was removed.
- Live search: `Rayuela Cortázar` returned the intended edition first with a cover and year;
  `Don Quijote de la Mancha`, `Cien años de soledad`, `El túnel Sabato`, and
  `Los detectives salvajes Bolaño` each ranked the intended title first. **20/20 results carried
  an edition year** in every query. Latency 1.2–1.3 s with no year resolution needed, 2.6–3.6 s
  when several works had to be resolved.
- Added three Spanish titles through the UI; each landed with real metadata and a locally cached
  cover on disk.
- Imported a synthetic 4-book Calibre library whose rows had an ISBN and nothing else. All four
  acquired year, publisher, description, language, page count, and a cached cover in about six
  seconds. No `entries` row changed.
- Backfill over the pre-existing library queued 5 items and filled a cover and metadata that had
  been empty since Sprint 011, with a byte-identical `entries` table before and after.
- With both providers unreachable, every library and detail page still rendered from cache with
  **zero provider calls**, and search returned a typed `providers_unavailable` 503.

Two defects were found by running the application and fixed in `4dcd8c2`: a four-row import
queued seven enrichment jobs and attributed them all to that batch, and `live-metadata.spec.ts`
asserted a post-add navigation no build has ever performed.

### Observed but out of scope

- `100 años de Soledad` (ISBN 9781516909629) still has no cover: Open Library returns an edition
  but every cover URL 404s, and the fallback does not run because the edition data is otherwise
  usable. Enrichment consults the second provider only when the first returns nothing usable, not
  to complete individual empty fields.
- The add flow leaves `score` empty and the detail page shows the score control unset; the
  library still renders those entries fine, but it reads oddly next to imported rows.
- `/api/shelves` is requested repeatedly on the library page (seven times during one browse),
  since each navigation refetches it. Harmless locally, worth a `staleTime` in Sprint 015.
