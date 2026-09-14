# Sprint 083 — A list you wrote yourself

**Status:** completed
**Depends on:** 082
**Roadmap revision:** 41

## Objective

Import a spreadsheet the owner wrote by hand — `exports/Libros.csv`, 104 rows of Spanish-
and English-language books with title and author columns and **no identifiers at all** — by
searching the domain's providers row by row in the background and proposing the best result
per row, so the owner confirms or discards each proposal in Triage before anything is
committed. Every existing importer reads an export another platform produced, whose IDs made
bulk import trivial; this one is the first source with no identity to trust, and the product
answer to it is a search-then-confirm flow, not a bigger heuristic.

The owner's three recorded product decisions (2026-09-13):

1. **The provider matching runs as a background job while the preview screen stays open**,
   polled for progress; **commit stays blocked until the queue for the batch has drained**.
   Not raw-rows-first with matching after commit, and not synchronous in the preview request.
2. **A confirmed proposal fills the item from the provider's full payload** — cover, ISBNs,
   synopsis, publisher, page count, language, year — the same `ItemPayload` the add path
   fetches, not a minimal cover-plus-ISBN stub.
3. **Only title and author are read for search.** The CSV's other columns (Editorial, Idioma,
   Formato, Estado, Precio, Comentarios) are deliberately **not mapped** to any domain field
   in this sprint — the owner's own answer was "matchearlo no está en scope, solo importa
   para la búsqueda. Queda a futuro", and mapping any of them is future work for whatever
   domain and whatever spreadsheet a future user brings.

## Required context

- `docs/specs/product-spec.md` §4.3 (the search flow and `merge_and_rank`'s deliberately
  dumb tie-breakers), §5.3 (the shared import pipeline: parse → normalized records → match →
  dry-run preview → one bounded transaction → enrichment), §6, §7 Screens (Import, Triage).
- `docs/specs/technical-spec.md` §6 (the import boundary), §6.6 (the domain contract; this
  sprint must not branch on which domain it is holding).
- `docs/decisions.md` DEC-045 (search is recorded but never blocked by the daily quota —
  this sprint's per-row searches are **enrichment-shaped**, not interactive-shaped, so they
  *are* budgeted; the distinction is recorded below), DEC-080 (a connector declares its own
  guide, empty state, help link and error vocabulary — the shared screen renders a
  declaration), DEC-082 (planning by identity; a source with no durable identity should not
  guess), DEC-025 (a mock of the unit under test does not prove a boundary — provider
  behavior must be proven against recorded real responses), DEC-108 (the live-boundary-down
  walkthrough substitution), DEC-146 (plan-revision shapes), DEC-155 (FINAL_SPRINT and the
  completed-plan invariants this revision moves).
- Code, read fresh:
  - `backend/src/book_tracker/domain/importers.py` — the `Importer` protocol (`read`,
    `stage`, `match`, `identity_kinds`, `error_codes`, `item_types`), `ImportInputSpec`
    (kind `upload`), `ImportSnapshot`, `NormalizedImportRecord`, and the `ImportReadError`
    user_message/action shape.
  - `backend/src/book_tracker/application/imports.py` — `ImportService.preview` (fingerprint
    idempotency, per-row `planned_action` staging, the `_validate` refusals), `get_preview`,
    `commit` (ambiguity choices, `create_item`/`reuse_item` actions).
  - `backend/src/book_tracker/infrastructure/repositories.py` —
    `ImportRepository.commit`'s per-row domain resolution and the ambiguity-choice guard.
  - `backend/src/book_tracker/application/providers.py` — `search_providers`
    (concurrent, bounded by `CANDIDATE_TIMEOUT_SECONDS`), `merge_and_rank` usage.
  - `backend/src/book_tracker/domain/providers.py` — `SearchCandidate`, `ItemPayload`,
    the `Provider`/`EnrichingProvider` protocols, `merge_and_rank`.
  - `backend/src/book_tracker/application/add.py` — `_provider_payload` (the full-payload
    fetch plus `source_refs` cross-fill and `_prefer_fuller_answers`), the cached-add path.
  - `backend/src/book_tracker/domains/book/providers.py` — `OpenLibraryProvider.search`
    (the `search.json` request shape, `fields=`, edition pairing, year resolution),
    `GoogleBooksProvider` (`enabled` keyed on `GOOGLE_BOOKS_API_KEY`), `fetch_by_isbn`.
  - `backend/src/book_tracker/domains/book/goodreads.py` — the shape of a CSV reader:
    `REQUIRED_COLUMNS`, `parse_goodreads`, `GoodreadsImporter.read/stage/match`,
    `identity_kinds = frozenset({"isbn"})`, declared `error_codes`.
  - `backend/src/book_tracker/domains/album/spotify.py` — the closest precedent for a row
    with a weak identity: identity resolution deferred to the enrichment layer, and
    `match_note` recording how a weak match was made.
  - `backend/src/book_tracker/infrastructure/jobs.py` — `JobRepository` (claim/lease/progress/
    retry backoff, `user_id` on jobs), `JobRunner` (in-lifespan cooperative poller,
    `rate_limiter`), `RateLimiter` (min-interval gate).
  - `backend/src/book_tracker/application/enrichment.py` — `EnrichmentHandler` as the model
    for a rate-limited per-item provider handler: quota consult, cover install, ledger
    effects, late-undo guard.
  - `backend/src/book_tracker/infrastructure/quota.py` — `ProviderQuota.record/allows`.
  - `backend/src/book_tracker/api/imports.py` — the preview/commit/undo routes,
    `_published_input`, the `JobProgressResponse` route, `_targets`.
  - `backend/src/book_tracker/infrastructure/models.py` — `ImportBatchRow` (`state`,
    `preview_summary`, `counters`), `ImportRecordRow` (`planned_action`, `match_kind`,
    `conflicts`, `matched_item_id`, `ambiguity_resolution`), `JobRow`.
  - `backend/src/book_tracker/main.py` — handler registration
    (`{"enrich_item": enrichment_handler}`), `RateLimiter(0.5)` wiring, lifespan.
  - `backend/src/book_tracker/domain/matching.py` — `MatchKind`, `decide_match`.
  - `backend/src/book_tracker/domain/normalization.py` — `normalize_text`, `shelf_slug`.
- Frontend, read fresh:
  - `frontend/src/pages/ImportPage.tsx` — the importer catalog, input rendering from
    `ImportInputResponse`, target checkboxes, preview records list, ambiguous-row choice
    selects, the commit gate (`ready + ambiguous` needing every ambiguity resolved).
  - `frontend/src/pages/TriagePage.tsx` — the inbox queue, status selects, one-decision-
    per-row, selection model, `acceptSuggestedStatuses`.
  - `frontend/src/api/imports.ts` — `previewImport`, `commitImport`, `getJobProgress`,
    the `ImportPreview`/`ImportRecord` types, `JobProgress`.
  - `frontend/src/features/library/labels.ts` — `statusesFor`/`statusLabelFor`.
- Tests, read fresh: `backend/tests/test_goodreads_import.py`,
  `backend/tests/test_generic_imports.py`, `backend/tests/test_domain_conformance.py`
  (the importer contract suite: error vocabulary closed, `read`/`stage`/`match` present,
  target/index agreement), `backend/tests/test_spotify_import.py` (weak-identity reader),
  `backend/tests/test_cached_add.py` (provider doubles + recorded fixtures),
  provider tests under `backend/tests/test_openlibrary_provider.py` /
  `test_google_books_provider.py` (whichever exist; check the fixtures directory),
  `backend/tests/fixtures/providers/` (recorded-response capture conventions and README).
- `docs/guides/adding-a-domain.md` — not to add a domain, but because its §6/§8 explain the
  import seam this sprint extends on the connector side without domain branching.
- `docs/agent/TESTING.md` — the ladder, walkthrough reuse, fresh-data-dir rule,
  `--replay` transport seam, current UI idioms (radiogroup domain chooser, native Triage
  selects, `Inbox N unsorted` heading).
- `docs/agent/WORKFLOW.md` — TDD loop, deviation policy, commit rules.

## Current implementation baseline

Measured in this worktree on 2026-09-13, not from any prior summary:

- **The import boundary is strictly connector-shaped and identity-trusting.** A connector
  declares `identity_kinds` (books: `isbn` only), and `ImportService._validate` **refuses
  the whole batch** (422 `invalid_import_record`) when a record carries an identifier kind
  the connector did not declare. `Importer.match` receives the record plus an
  `ImportMatcher` that is a **narrow library view** (exact-identity and title/author
  similarity against existing `items`) — it has no provider access at all. `preview` is
  synchronous, fully CPU/local-DB bound, and the summary counts
  `create_item`/`reuse_item`/`ambiguous`/`error`/`identity_conflict` per row.
- **The provider search seam already exists, domain-keyed.** `search_providers(query,
  providers, domain=...)` runs the domain's enabled providers concurrently, each bounded
  by a 10 s `CANDIDATE_TIMEOUT_SECONDS`, and merges through `merge_and_rank` with the
  domain's `IdentityStrategy` (books group on ISBN; undated Open Library works get their
  year resolved through a semaphore-bounded fan-out). Books have Open Library always
  (keyless) and Google Books when `GOOGLE_BOOKS_API_KEY` is set (it is, in this checkout's
  `.env`).
- **The durable job queue is general, not enrichment-only.** `JobRow` carries `kind`,
  `user_id`, `batch_id`, `state`, `progress`, `payload`, lease/backoff columns;
  `JobRunner` polls in the FastAPI lifespan, registers handlers by `kind`
  (`{"enrich_item": enrichment_handler}` in `main.py`), consults a `RateLimiter`
  (min interval 0.5 s) and the persistent `ProviderQuota` (per-provider daily limits via
  `AKASHA_PROVIDER_DAILY_LIMITS`, recorded-never-blocked for interactive search, blocking
  for background work — DEC-045's split). `GET /api/import/jobs/{job_id}` already exists
  and is user-scoped. `EnrichmentHandler` is the template for a rate-limited, cover-
  installing, ledger-recording handler.
- **Triage is one-decision-per-row over committed `unsorted` entries.** Commit creates
  entries as `unsorted`; Triage (`TriagePage.tsx`, virtualized, native status selects per
  DEC-086) lists them and offers bulk status decisions. Import-preview rows have their own
  in-screen resolution UI for `ambiguous` rows (a select among candidate item ids), but no
  row today proposes an **external** candidate.
- **`import_batches.state` is free text** (`sa.Text`, no CHECK on `state`; migration 0016
  added a CHECK only on `kind`). The lifecycle today is `previewed → committed` plus
  undo/reclaim states written by the ledger; nothing constrains new intermediate states.
- **The CSV itself.** `exports/Libros.csv`: 104 rows + header, UTF-8 with BOM, CRLF,
  columns `Título del libro`, `Autor`, `Editorial ` (trailing space in the header),
  `Idioma`, `Estado`, `Formato`, `Precio`, `Comentarios adicionales`,
  `Fotos_libros_en_venta`; two quoted fields (`"Will Grayson, Will Grayson"`,
  `"Todo oscuro, sin estrellas"`); one row with author/title transposed (`Homero,Iliada` —
  title in the author column); one multi-author cell (`"Analia Aucia, et al"`);
  collection-volume suffixes (`La cúpula 1`, `Maze runner #2: Prueba de fuego`, `Duma key
  2`), plain-text typos (`Trutles alls the way down`), non-book rows (two dictionaries,
  a psychology essay collection), and 81/22/1 Castellano/Inglés/Francés split. No ISBNs,
  no IDs, no dates, no ratings. The file lives in the git-ignored `exports/` (never
  committed); a **sanitized synthetic fixture** derived from its shape (not its rows) is
  what tests use.
- **Version surfaces** all read `2.0.0` and are gated by the validator; this sprint adds no
  release and does not bump them.

## Deliverables

### D1 — The connector: a generic delimited-text reader with column selection

A new importer in the book domain's package, `backend/src/book_tracker/domains/book/list.py`
(working name `list`, label "A list you wrote", `item_types=("book",)`), reading a
UTF-8 CSV/TXT upload (`.csv,.txt,.tsv`, `text/csv` family; BOM tolerated; CRLF and bare-LF
both accepted; comma/semicolon/tab sniffed by counting occurrences in the first data line).

1. `ImportInputSpec(kind="upload", ...)` with a guide written for a person who wrote the
   file themselves (no platform to re-export from; the empty state and refusal copy say so).
2. **Column selection is a connector-declared option, not a screen patch.** The catalog
   response gains, per importer, an optional declaration of a configurable field (for this
   connector: which columns hold title and author, plus an optional author column). The
   preview request carries the chosen mapping as form fields. Defaults: if the client sends
   nothing, the connector **auto-detects** by header name — Spanish and English title/author
   words (`título`, `titulo`, `title`, `nombre`, `libro`, `book name` / `autor`, `author`,
   `autora`, `escritor`) — and, when no header matches, falls back to the **first two
   columns** (title, then author), which is what the owner's CSV needs. Auto-detection is
   tested with the real header set above (including the trailing-space `Editorial ` header
   proving headers are trimmed before matching).
3. `read` produces one `NormalizedImportRecord` per non-empty row: `item.title` and
   `metadata.creators=[author]` from the chosen columns, `identifiers={}` (none — this is
   the point), `entry.score=None`, `notes=None`, `suggested_status=None` (Triage decides),
   `values={}`, `shelves=()`, `errors` carrying per-row parse problems (empty title, a
   row shorter than the chosen columns). Rows whose chosen title column is empty are row
   `errors`, not skips. The original cell values stay in `source_fields` (the existing
   neutral channel for row-level facts) so triage can show what the spreadsheet said.
4. `identity_kinds = frozenset()` (empty — the connector trusts no identity, and the
   boundary's empty-set case is proven here), `error_codes` closed:
   `invalid_csv` (decode/parse), `missing_columns` (fewer than 2 columns), plus the new
   `column_not_mapped` family published through the standard envelope.
5. `stage` stores the uploaded file as `source.csv` in the batch directory exactly the way
   the Goodreads reader does (byte-identical replay for fingerprint idempotency).
6. `match` returns `MatchDecision(MatchKind.NEW)` for every row: with no identities and no
   trusted text key, the connector **never** resolves a library match itself — the proposal
   step (D3) is the only matcher. This keeps `_validate`'s identity gate trivially
   satisfied and keeps `planned_action` honest (`create_item` for every healthy row, since
   provider-proposed candidates arrive only in the proposal store).
7. Fingerprint: `sha256(bytes)` composed with the chosen column mapping (the same
   DEC-106-derived rule the target selector uses — re-previewing the same file with a
   different mapping is a different import, not a stale replay).

### D2 — The proposal store and its schema

A proposal is one provider result offered for one row, the thing Triage confirms or
discards. It needs to be durable across the background job's lifetime and user sessions.

1. **Migration 0022** (`backend/alembic/versions/0022_import_proposals.py`): new table
   `import_proposals` — `id` (PK), `batch_id` (FK `import_batches.id`), `user_id`,
   `record_id` (FK `import_records.id`), `source` (provider name), `source_id` (provider
   record id), `payload_json` (the full `SearchCandidate`/`ItemPayload` fields the
   confirmation will need: title, subtitle, creators, year, language, identifiers,
   metadata, cover_url, cover_fallback_urls), `score` (the proposal's confidence ranking
   value within the row, from `merge_and_rank` position), `chosen` (NULL, `true`, `false`),
   `created_at`. Indexes: `(batch_id, record_id)`, `(user_id)`. One row may hold **several**
   proposals (the top N, default 3) so the owner can pick a different result than the
   first — the triage UI lists them ranked.
2. `ImportRepository` gains the proposal CRUD (create/list per record/set chosen/delete).
3. The preview response's per-record payload gains `proposals: [...]` and the batch summary
   gains proposal counts (`rows_with_proposals`, `proposals_total`, `searched`, `failed`),
   all defaulting to zero/empty for every other connector (the response model already
   allows extra fields; the shared screens ignore what a connector does not declare).

### D3 — The background search job (`search_import_rows`)

1. `commit` is unchanged for every existing connector. For this connector, `preview`
   **stages the batch in a new state `matching`** (free-text `state` column, no migration
   needed on `import_batches` itself) and enqueues **one** job per preview:
   `kind="search_import_rows"`, `payload={batch_id, importer, mapping}`, `user_id` from the
   service, so the existing claim/lease/heartbeat/progress machinery runs it. The job is
   registered in `main.py`'s handler table beside `enrich_item`.
2. The handler (`backend/src/book_tracker/application/import_search.py`): claims the batch's
   rows in `row_number` order; for each row builds the query from the record's stored
   title/author (`"<title> <author>"` — both, because the CSV's Spanish titles often need
   the author to disambiguate from translations); calls `search_providers` (concurrent,
   10 s bound) **through the quota the same way enrichment does** — `ProviderQuota.allows`
   first, skip-and-retry-later on a blocked provider (the job records a `provider_wait`
   marker and the row is retried on the next pass), `ProviderQuota.record` on every spend,
   and the `RateLimiter` min-interval between rows (sequential 1×1 as the owner specified:
   **no concurrency across rows**, one provider call set per row, respecting public-API
   rate limits); takes the merged top-N (3) as proposals (D2), persists them, updates the
   job's `progress` (`{"searched": n, "total": m, "state": "searching"|"drained"}`).
3. **Failure containment**: a row whose searches all fail is marked `search_failed` in the
   row's proposal state (proposals empty, a reason recorded in the job progress) and stays
   confirmable-by-discard in triage; the job never dead-letters for per-row provider
   errors, only for systemic ones (DB failure). A provider that returns nothing renders
   "no results" for the row — an answer, not an error.
4. When every row has been searched (or terminally failed), the job flips the batch
   `matching → previewed` and writes the final summary counts. **`commit` refuses a batch
   whose state is `matching`** (409 `import_batch_not_committable`), and the preview GET
   reports the live counts so the screen can poll.
5. **Late-crash recovery is the existing reclaim path**: an abandoned `matching` batch is
   reclaimed by `reclaim_import_batches` (extend its state set) the way abandoned
   previews already are; the job's lease/backoff machinery already survives a restart.
6. **The walkthrough-gate rule (DEC-025) applies**: the handler is tested against
   **recorded real provider responses** (captured fixtures of Open Library `search.json`
   for representative Spanish/English title+author queries), plus synthetic fixtures for
   the miss/empty case; never against an invented mock of the provider contract in the
   correctness suite.

### D4 — Confirm-in-triage

1. A new API surface on the import router (the same `/{importer_name}/batches/{batch_id}`
   namespace): `GET` proposals for a batch (paginated by record), and
   `POST .../records/{record_id}/proposal` with `{proposal_id | discard}` to set `chosen`.
   A record with a chosen proposal re-stages its `normalized_payload` item half from the
   proposal's payload (title, creators, identifiers, metadata, year) — the same
   `_stored_record` shape, so **commit needs no new code path**: the record's
   `planned_action` recomputes (exact identity now possible → `reuse_item`; else
   `create_item` with real metadata), and the existing per-row domain validation applies.
   `discard` marks `chosen=false` on all of the record's proposals and the row remains
   importable **as typed** (title/author from the CSV, no provider data) — the owner's
   explicit discard means "none of these is the book; keep my row anyway".
2. The preview screen (ImportPage) for this connector renders, per row, the proposal list
   (cover, title, authors, year, language, provider) with Confirm / Try another / Discard
   controls, disabled while the batch is `matching`, plus the batch-level progress bar
   fed by the job progress route and a summary line ("42 of 104 rows searched"). Rows
   whose search failed show the failure row. The commit button stays gated on
   `state == previewed` and the existing ambiguity rule.
3. No TriagePage change: entries still land `unsorted` after commit and are triaged with
   one-decision-per-row as today. The confirm flow lives on the import preview surface,
   where every other per-row decision already lives (DEC-086's split stands).

### D5 — Conformance, docs and fixtures

1. The importer conformance suite (`test_domain_conformance.py`) gains the contract
   assertions for the new optional surfaces (empty `identity_kinds`, the configurable
   column mapping declaration, the new error codes) and continues to hold for every
   existing connector unchanged.
2. Canonical docs updated: `docs/specs/product-spec.md` §5 gains "5.4 A list you wrote"
   (the flow, the three owner decisions, the search-then-confirm contract, the
   deliberate non-mapping of extra columns); `docs/specs/technical-spec.md` §6 gains the
   proposal store, the `matching` state, the job kind and the confirm route; the OpenAPI
   examples; `docs/README.md` doc map unchanged (no new doc);
   `frontend/openapi.json` regenerated if the schema moved (it will).
3. Sanitized fixtures: a synthetic 12-row CSV shaped like the owner's (a Spanish title, an
   English title, a transposed row, a collection volume, a typo, a dictionary row, an
   author with `et al`, a quoted-comma title, a semicolon-delimited variant) — committed
   under `backend/tests/fixtures/imports/`; recorded Open Library search fixtures for
   3–5 representative queries committed under `backend/tests/fixtures/providers/` with the
   provenance README updated. **The owner's real CSV is never committed.**

## Acceptance criteria

1. **Upload and mapping.** `POST /api/import/list/preview` with the sanitized fixture CSV
   and no mapping returns a 201 preview whose records carry title/author from the
   auto-detected columns; with an explicit mapping (different columns chosen) the same
   file previews with the other columns read. A file with fewer than 2 columns is refused
   422 `missing_columns` with an actionable `action` sentence. CRLF, BOM and
   semicolon/tab delimiters all parse. (tests: `test_list_import.py` + route tests)
2. **Auto-detection.** Headers matching the real CSV's (`Título del libro`, `Autor`, the
   trailing-space `Editorial `) auto-map correctly; unknown headers fall back to columns
   1/2; the header row itself is never imported as a row. (tests: `test_list_import.py`)
3. **Rows are honest.** Every non-empty row appears in the preview with its original cells
   in `source_fields`; an empty-title row is an `error` row with `field: title,
   code: required`; a row shorter than the mapping is an `error` row; the summary counts
   are consistent with the record list. (tests: `test_list_import.py`)
4. **The batch stages `matching` and a job exists.** Preview response `state == "matching"`
   for this connector; a `search_import_rows` job row exists with the batch's id and the
   owner's `user_id`; `GET /api/import/jobs/{id}` returns progress with `searched/total`.
   The job respects the per-row rate limiter and the provider quota: when the daily limit
   is configured low, rows wait (progress shows a wait marker) instead of being silently
   dropped, and resume when the window allows. (tests: `test_import_search_job.py`)
5. **Proposals are real.** Running the handler against recorded Open Library fixtures
   produces, for a representative row, a stored proposal whose title/creators/year/
   identifiers match the fixture's payload; the row's top-N proposals are ranked with
   `merge_and_rank`'s order preserved; a provider returning zero docs yields "no results"
   for that row, not an error; all-providers-failed yields `search_failed` with the reason
   recorded, and the batch still drains to `previewed`. (tests: `test_import_search_job.py`
   against fixtures; synthetic-mock tests only for the failure paths, per DEC-025 the
   correctness claims replay real responses)
6. **Commit is gated.** `POST /api/import/list/commit` on a `matching` batch returns 409;
   after the job drains to `previewed`, commit succeeds. Existing connectors' commit
   paths are byte-for-byte unchanged (no `state` values they produce change meaning).
   (tests: route tests + regression on `test_generic_imports.py`)
7. **Confirm and discard.** Choosing a proposal re-stages the record from the proposal
   payload (title/creators/identifiers/metadata reflect the provider's record — verified
   through the preview GET), and commit then creates the item with the provider's
   identifiers, cover installed from the proposal's cover URL (the same install path
   enrichment uses), and the entry lands `unsorted`. Discarding marks all proposals
   `chosen=false` and the row still commits with its typed title/author. Committing a
   batch with unconfirmed rows is allowed (they land as typed) — the owner decides per
   row, not per batch. (tests: `test_list_import.py` confirm/discard + commit)
8. **The full flow works against a real backend.** A walkthrough with the sanitized
   fixture (12 rows) against a fresh data dir: upload → mapping (auto) → progress bar
   reaches 12/12 → confirm 2 rows, discard 1, leave the rest → commit → 12 entries
   `unsorted`, the 2 confirmed items carry ISBN + cover, the discarded one has no ISBN,
   enrichment backfill changes nothing on them → undo restores the library to its
   pre-import state. Recorded in the worklog with observed counts. (scratchpad
   Playwright spec + a live-run script, per TESTING.md's walkthrough reuse)
9. **No domain branching.** No file outside `domains/book/` names a book field, and the
   shared layers (`ImportService`, the job handler, the routes) never branch on
   `importer.name == "list"` where a declaration could say it — the connector's
   declaration drives behavior, matching how `browsable`/`incremental` already work
   (technical spec 6.6; the conformance suite's spirit). Where a shared change is
   genuinely needed (the `matching` state, the proposal store), it is domain-neutral and
   its tests prove neutrality with a second connector's data.
10. **Docs and contracts move together.** Product spec §5.4, technical spec §6, OpenAPI
    (regenerated `frontend/openapi.json`), and the importer catalog examples describe the
    same surface; the conformance suite passes for all seven connectors; the project
    validator passes.

## Required tests (TDD)

Written failing first, per the ladder:

- `test_list_import.py` — reader: parse, auto-map, explicit map, error rows, `source_fields`,
  identity-free `match` (always NEW), fingerprint composition, `stage` bytes; confirm/
  discard re-staging; commit with mixed confirmed/discarded/unconfirmed rows.
- `test_import_search_job.py` — job: sequential per-row search, rate-limiter spacing,
  quota wait/skip/resume, top-N proposal persistence with ranking, `search_failed`
  containment, progress payloads, `matching → previewed` flip, reclaim of an abandoned
  `matching` batch.
- Recorded-fixture replays: the handler and the proposal payload mapping against captured
  Open Library `search.json` responses (3–5 queries), with the capture script and
  provenance noted in the fixtures README.
- `test_domain_conformance.py` — new optional-contract assertions (empty identity set,
  mapping declaration, new error codes) and a no-regression pass over all connectors.
- Route tests: preview/mapping form fields, the `matching` 409, the job-progress 200,
  the confirm/discard endpoints, cross-user 404 on another user's batch (the 079
  isolation pattern).
- Frontend: Vitest component tests for the proposal list, the progress bar and the
  confirm/discard controls; the ImportPage contract test updated for the new input
  declaration rendering.
- E2E (Playwright): extend the existing import spec with the list connector flow
  (mocked/replayed provider transport via `--replay`, per the walkthrough substitution
  rule); the scratchpad walkthrough spec for AC8.

## Verification

- Focused: `cd backend && uv run pytest tests/test_list_import.py tests/test_import_search_job.py -x -q`
- Focused routes: `uv run pytest tests/test_generic_imports.py tests/test_domain_conformance.py -q`
- Backend exhaustive: `make test` (backend + frontend Vitest).
- Frontend: `npm run test:e2e` from `frontend/` (the parallel run is the gate; the new
  spec included).
- `make check` (validator + lint + typecheck + version surfaces).
- OpenAPI regeneration check: `frontend/openapi.json` matches the backend schema (the
  version-surface gate extends to the generated contract; regenerate, then re-run
  `make check`).
- Walkthrough (AC8) on a fresh disposable data dir with `scripts/walkthrough.py`,
  provider transport replayed from recorded fixtures if the live boundary is down, per
  DEC-108's substitution rule — recorded in the worklog either way.
- Container: not owed (no deployment change), but `make smoke-container` runs as usual
  after the version-surface check if anything in the image's env changed — it did not.

## Explicit non-scope

- **Mapping the CSV's extra columns (Editorial, Idioma, Formato, Estado, Precio,
  Comentarios) to domain fields** — the owner's explicit "queda a futuro". Nothing in this
  sprint maps them; they ride in `source_fields` uninterpreted. A future sprint decides
  per-domain, per-spreadsheet mapping.
- Re-file/move items between domains (already costed in "Not scheduled").
- Anything to TriagePage beyond reading committed rows — the confirm flow lives on the
  import preview screen.
- Multi-domain generality beyond what the declaration mechanism buys for free (books
  first; the contract stays domain-neutral but only books get a connector).
- Smart matching heuristics beyond `merge_and_rank`'s existing tie-breakers (no fuzzy
  scoring, no embedding anything). The provider's own relevance ranking is the matcher.
- A "search again" per-row retry button (the job's wait/resume covers the realistic
  failure mode; a manual re-search is future polish if the owner wants it).
- Export views, saved views, insights changes, auth changes, deployment changes.
- Bumping the version surfaces (no release in this sprint).

## Commit checkpoints

- `feat(domains): the list reader — column mapping, honest rows, identity-free match` (D1 + tests)
- `feat(db): import proposals store and the matching state` (D2 + migration + repo CRUD)
- `feat(imports): the search_import_rows job — sequential, quota-bound, rate-limited` (D3 + tests)
- `feat(api): proposal confirm and discard, commit gate on matching` (D4 backend + tests)
- `feat(ui): proposal cards, progress and confirm/discard on the import screen` (D4 frontend + Vitest)
- `test(imports): recorded Open Library search fixtures and replay tests` (D3/D5 fixtures)
- `docs(specs): a list you wrote — product and technical contract` (D5 docs)
- `e2e(imports): the list connector flow` (AC8's spec)
- `docs(sprint-083): close sprint and hand off` (closure, only after all gates)

## Risks and decisions to surface

- **Provider rate limits at 104 rows × 2 providers.** The owner's own CSV needs ~104
  sequential row-searches (Open Library keyless + Google Books keyed). At 0.5 s spacing
  that is ~1–2 minutes of background work — acceptable for a one-shot import; the progress
  UI exists because of it. If the owner wants faster, raising concurrency across rows is
  a DEC-level change (violates "secuencial y async" as specified — do not do it silently).
- **Open Library search quality for Spanish titles.** AC5's fixtures must capture real
  responses for a Spanish-titled row; if Open Library's relevance for e.g. `Maze runner #2:
  Prueba de fuego James Dashner` is poor, the finding is recorded and the top-N=3 list
  exists so the owner can still find the right one — the sprint does not attempt to fix
  provider relevance.
- **The transposed row (`Homero,Iliada`).** The search will propose results for a bogus
  query ("Iliada Homero" reads fine, actually) — the confirm step is the safety net; if
  the recorded fixture shows a wrong-but-plausible top result, that is the designed
  behavior, not a defect.
- **`chosen`-proposal re-staging vs. preview idempotency.** Re-previewing the same file
  (same fingerprint) returns the stored batch with its existing proposals and choices —
  confirmations survive a re-preview. Decisions recorded in the Outcome.
- **Quota starvation of interactive search.** The job consults the same per-provider
  daily limits as enrichment; a large import could eat the day's Google Books budget. The
  job's wait-and-resume behavior is the mitigation; the limits config stays the owner's
  dial (`AKASHA_PROVIDER_DAILY_LIMITS`). Recorded as a runbook note, not new machinery.

## Outcome

Delivered 2026-09-14 across two sessions (backend D1–D5 on 2026-09-13, the
frontend/walkthrough/fix slice resumed and closed on 2026-09-14), TDD
throughout. Commits, in order:

- D1 `417b864` the list reader — column mapping as a connector declaration,
  header auto-detect (accents folded, trailing spaces trimmed), honest error
  rows, `identity_kinds = frozenset()`, match-always-NEW, mapping composing
  the fingerprint.
- D2 `8081bdc` migration 0022 `import_proposals` + repo CRUD + proposals riding
  the preview GET with summary counts. The rank column is named `rank` not
  `score` (it is `merge_and_rank`'s position — the migration docstring says so).
- D3 `7c6afa4` `application/import_search.py` — sequential per-row search,
  top-3 proposals, quota defer-without-attempt, rate-limiter pacing,
  no-results-is-an-answer, all-fail containment; the `SearchingImporter`
  declaration stages `matching` + one job; commit's state gate gives the 409.
- D4 `079f300` the confirm/discard route + `ImportService.answer_proposal` —
  confirm re-stages the item half and recomputes `planned_action`, the
  confirmed identity travels `confirmed_identifiers`, discard keeps the row as
  typed, both require a drained batch. Isolation inventory updated as designed.
- D4.2 `05ea8e8` the ImportPage search-then-confirm screen — proposal cards,
  the job-progress banner, the column-mapping inputs rendered from the
  declaration, commit gated while `matching`.
- D5 `7655148` the sanitized 12-row fixture, recorded Open Library replay
  tests, conformance assertions for the new optional surfaces, product-spec
  §5.4, technical-spec §6, §6 route list, OpenAPI regenerated + examples.
- Frontend completion + the interrupted session's residue `6f72992` — the
  missing per-row Discard control ("None of these — keep as typed", D4.2's
  third control), the two import routes added to the documented-route set,
  formatting that never landed, and the fix to the residue audit's finding:
  **discard after confirm now restores the typed row** (confirm stashes the
  typed item half; discard puts it back and re-plans through the connector's
  own match — the old path left the provider's identifiers on a "keep as
  typed" row).
- E2E `0a03f81` the list-connector Playwright spec (stubbed routes: matching
  banner, gated commit, drained poll, Confirm/Discard, the proposal route
  shape) + the list connector in the shared e2e catalog stub. Also repaired a
  pre-existing break on main the run surfaced: editorial.spec.ts asserted the
  delete-dialog sentence DEC-158 removed (reproduced on a clean tree; a
  prerequisite defect fix, not sprint scope).
- Walkthrough fixes `94aaa7e` — two AC8-live findings, both TDD'd:
  **the row search queried every domain's providers** (the live run proposed a
  Cinemeta movie and a series for the Rayuela book row); the handler now
  resolves each row's domain from the record's own `item_type` and asks only
  that domain's providers, and its `kind != "list"` guard became the
  declaration check (AC9's rule). **Confirm stored the provider's raw
  identifier key** (`isbn13`) while every other surface keys on the canonical
  `isbn` the add path writes, leaving the confirmed row invisible to the
  enrichment join (no cover ever) and to exact-identity matching; confirm now
  normalizes through the same identity rule. The walkthrough script hardened
  with what the live run taught (undo wait on the result heading, the metahub
  cover 404 is a designed absence, the confirmed title may be the provider's
  own, covers are polled for — async enrichment).

**Verification (all run on the final tree):**

- Focused: `pytest tests/test_list_import.py tests/test_import_search_job.py`
  (56), then the route/conformance regression
  `tests/test_generic_imports.py tests/test_domain_conformance.py
  tests/test_import_proposals.py tests/test_isolation.py` — 343 focused green.
- Backend exhaustive: 1569 passed.
- Frontend Vitest: 330 passed (33 files), including the new discard test.
- `make check`: ruff format/check, eslint --max-warnings=0, mypy (74 files),
  tsc, OpenAPI `--check` (no drift), `api:check`, `validate_project.py` — green.
- Full Playwright: 142 passed, 2 skipped (production-bundle + scratchpad
  projects, as always), including the new list-connector spec.
- **Walkthrough (AC8)** on a fresh disposable data dir (`/tmp/akasha-s083`,
  auth off, backend :8002 + frontend dev :5175 with `AKASHA_E2E_BACKEND`),
  against the **live** Open Library and Google Books boundary (keyless/keyed;
  both answering — no replay substitution needed, and the correctness suite's
  recorded-fixture replays satisfy DEC-025 for the provider contract):
  upload → auto-mapping → `matching` → 12/12 rows searched (banner polled) →
  confirm Rayuela + El Hobbit, discard La cúpula 1 → commit → **10 entries
  `unsorted`** (12 rows − the fixture's 2 designed error rows: a missing title
  and a short row — the sprint's "12 entries" reads every row committing; the
  fixture deliberately includes rows that must not) → both confirmed rows carry
  the canonical `isbn` and **covers installed** (polled: Open Library edition →
  work → covers.openlibrary.org, ~5 s) → backfill no-op on them → undo through
  the screen's own controls → 0 rows. Backend log audited: only
  openlibrary.org and googleapis.com consulted (zero cross-domain provider
  calls), one `ConnectError` on a single row contained as designed. Script
  kept as `frontend/scripts/walkthrough-list.mjs` (run-unique, DB-audited).
- Container: not owed (no deployment or env change); `make smoke-container`
  not run for that reason.

**Deviations and decisions:**

- The fixture's honest 10-of-12 commit count (above) is the one reading of
  AC8's "12 entries" that keeps the fixture honest — the alternative (a fixture
  without error rows) would stop proving AC3.
- Confirm normalizes identifiers (canonical `isbn`, not the provider's
  `isbn13`) and the cover arrives through the post-commit enrichment backfill
  rather than at confirm time — this is the "same install path enrichment
  uses" AC7 names, and it is how the add path behaves too (cover installs are
  async there as well). Technical spec §6 updated to say exactly this.
- The discard-restores-typed-row behavior (D4's "discard keeps the row as
  typed" applied to the confirm-then-reconsider path) is recorded in technical
  spec §6 alongside the confirm contract.
- The interrupted session left no worklog entry; its residue is accounted for
  in `6f72992`'s message (what landed, what was formatting, what was missing).
- No new DEC entry was needed: the two `94aaa7e` fixes implement the sprint's
  own contract (AC7's canonical identity via "the same ItemPayload the add
  path fetches", AC9's no-domain-branching) rather than deviating from it. The
  editorial.spec.ts repair is recorded in its commit as a prerequisite defect.

**Impact on future sprints:** none — 083 was the last planned sprint; the
plan is complete. The roadmap's "Not scheduled" list is unchanged. The
`matching` state, the proposal store, and the searching declaration are now
shared surfaces any future connector may declare (the technical spec's §6
paragraphs and the conformance suite describe them).
