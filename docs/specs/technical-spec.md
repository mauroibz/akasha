# Book Tracker v1 — Technical Specification

**Status:** implementation baseline 1.0
**Product source:** [`product-spec.md`](product-spec.md)
**Last updated:** 2026-07-21

## 1. System goals and quality attributes

The application is a single-user, LAN-only web application for recording opinions about book editions. It must remain usable with several thousand entries and while metadata providers are unavailable.

Priority order:

1. Preserve user-authored statuses, scores, notes, dates, shelves, and metadata corrections.
2. Keep add and triage workflows keyboard-first and responsive.
3. Render the library entirely from local state; remote calls occur only in explicit search, add, refresh, or enrichment operations.
4. Keep deployment and recovery simple on a ZimaBoard: one application container, one writable data volume, one read-only Calibre mount.
5. Prefer explicit v1 code over speculative plugin or multiuser frameworks.

Target budgets:

- Add a finished book in under 20 seconds under normal provider latency.
- Local API mutations: p95 under 200 ms on target hardware, excluding provider and image work.
- First library page: p95 under 500 ms for 10,000 entries on target hardware.
- No list screen mounts more than a small multiple of visible rows.
- WCAG 2.1 AA keyboard/focus/contrast behavior for core workflows.

## 2. Repository and runtime architecture

```text
akasha/
├── AGENTS.md
├── backend/
│   ├── alembic/
│   ├── src/book_tracker/
│   │   ├── api/             # thin FastAPI routers and error mapping
│   │   ├── application/     # use cases and transaction boundaries
│   │   ├── domain/          # enums, value objects, provider/import contracts
│   │   ├── infrastructure/  # SQLAlchemy repositories, providers, files, jobs
│   │   └── main.py          # app factory, lifespan, static SPA mount
│   └── tests/               # unit, integration, contract
├── frontend/
│   ├── src/
│   │   ├── api/             # generated/typed HTTP client boundary
│   │   ├── components/
│   │   ├── features/
│   │   ├── pages/
│   │   └── test/
│   └── e2e/
├── docs/
├── scripts/
├── Dockerfile
└── compose.yaml
```

The backend follows pragmatic ports-and-adapters boundaries, not a framework-heavy clean-architecture ceremony:

- API routers validate transport shapes and call application services.
- Application services own use-case orchestration and transactions.
- Domain modules contain provider/import protocols, normalization, matching, enums, and invariants without FastAPI or SQLAlchemy dependencies.
- Infrastructure modules implement SQL persistence, HTTP providers, cover storage, Calibre reads, and the durable job runner.

The frontend is feature-oriented. Shared primitive components live in `components/ui`; behavior belongs with its feature. Server state uses TanStack Query. Local component state is preferred over a global store until a concrete cross-page need appears.

## 3. Backend baseline

Use Python 3.12 with:

- FastAPI and Pydantic v2 / pydantic-settings;
- SQLAlchemy 2 declarative mappings and Alembic;
- SQLite through a single configured engine; application services may remain synchronous unless measured load justifies async DB access;
- `httpx.AsyncClient` for metadata providers;
- Pillow for cover validation and JPEG conversion;
- pytest, pytest-cov, respx, and time/path injection for deterministic tests;
- Ruff for formatting/linting and mypy in strict-enough project mode.

Application startup must:

1. validate settings and create `/data`, `/data/covers`, `/data/imports`, and `/data/backups` if absent;
2. enable SQLite `PRAGMA foreign_keys=ON` for every connection, WAL mode, and a bounded busy timeout;
3. refuse to auto-create or mutate schema outside Alembic;
4. report schema mismatch with a useful startup error;
5. once Sprint 011 introduces the jobs schema, start one cooperative durable-job polling loop in the FastAPI lifespan;
6. when that runner exists, stop accepting job work and cancel it cleanly on shutdown.

Do not run multiple Uvicorn workers: the target is one process and the v1 job lease design assumes it. Tests must still enforce idempotency in case a job is retried after a crash.

## 4. Configuration

Environment variables:

| Variable | Required | Default | Meaning |
|---|---:|---|---|
| `BOOK_TRACKER_DATA_DIR` | no | `/data` | DB, covers, staged imports, backups |
| `BOOK_TRACKER_CALIBRE_DIR` | no | `/calibre` | read-only Calibre library root |
| `BOOK_TRACKER_DATABASE_URL` | no | derived | SQLite URL, overridable in tests |
| `GOOGLE_BOOKS_API_KEY` | no | empty | enables Google Books provider |
| `USER_AGENT_CONTACT` | yes in production | none | contact included in provider User-Agent |
| `TZ` | no | `UTC` | display/default local timezone; stored dates remain ISO |
| `LOG_LEVEL` | no | `INFO` | structured application log threshold |

Commit `.env.example` without secrets. Production must fail fast if `USER_AGENT_CONTACT` is absent; tests and local development may use an explicit test default.

## 5. Canonical data model

All timestamps are UTC RFC 3339 strings at API boundaries and timezone-aware Python datetimes internally. User-entered reading dates are ISO `YYYY-MM-DD`. Scores are nullable integers 1–10. Status is one of `unsorted`, `read`, `reading`, `to_read`, `wishlist`, `dropped`.

### 5.1 Tables

`items`

- `id` integer primary key
- `type` text, default `book`
- `title` required text
- `subtitle`, `year`, and `cover_path` nullable
- `identifiers` optional JSON API/cache projection derived from relational identifiers; never the uniqueness authority
- `metadata` required JSON-as-text with application validation
- `sort_author` generated from first metadata author
- `created_at`, `updated_at` required
- case-insensitive title index

`item_identifiers`

- `item_id` foreign key to items, cascade delete
- `kind`, `normalized_value`, and original `value` required
- primary key `(item_id, kind, normalized_value)`
- unique `(kind, normalized_value)` for authoritative identities; ISBN-10 and ISBN-13 share canonical kind `isbn`, while Calibre UUID uses a stable namespaced kind

A valid ISBN-10 is converted to canonical ISBN-13 before storage, so conversion-equivalent values collide on the same `(kind, normalized_value)`. Provider identities live in `item_sources`, avoiding duplicate authority. Relational constraints—not check-then-insert or JSON queries—close duplicate races.

`item_sources`

- `item_id` foreign key to items, cascade delete
- `source`, `source_id`, and boolean `is_primary` required
- primary key `(source, source_id)`; unique `(item_id, source)`
- at most one primary source per item, enforced by a partial unique index

A merged search candidate can retain both Open Library and Google Books identities. The primary source selects explicit refresh; manual-only items have none.

Every mutable table has `created_at` and `updated_at` unless it is an immutable append-only effect row; jobs/batches additionally use their lifecycle timestamps.

`entries`

- product-spec fields plus foreign key `item_id` with restrict-on-delete
- checks for status, score, nonnegative `reread_count`, and boolean `score_provisional`
- unique `(user_id, item_id)`
- indexes supporting status/score/date list paths

`shelves` and `entry_shelves`

- as in product spec, with normalized unique slug per user
- shelf rename updates name and slug transactionally and rejects collisions
- deleting a shelf cascades join rows, never entries

`import_batches`

- `id` UUID text primary key
- `kind` (`goodreads` or `calibre`), `fingerprint`, `state`
- source descriptor JSON; never contains arbitrary host paths returned to browsers
- preview summary JSON, counters JSON, error JSON
- `created_at`, `committed_at`, `undo_expires_at`
- unique `(kind, fingerprint)` for committed input identity where practical

`import_records`

- `id` integer primary key; `batch_id` foreign key and source `row_number`
- normalized payload JSON, matched item/entry IDs, match kind, planned action
- conflicts JSON, validation errors JSON, and explicit ambiguity resolution
- unique `(batch_id, row_number)`

Preview persists these normalized records, so commit applies exactly the reviewed plan rather than reparsing an upload or rereading a Calibre database that may have changed.

`import_effects`

- `effect_id` integer primary key and `batch_id`, `record_id`, effect/entity types, entity ID
- before-values and after-values JSON
- monotonic `effect_id` provides deterministic reverse-order undo

This ledger makes undo safe: reverse only effects recorded for the batch; delete entities only when the batch created them and they remain unmodified/unreferenced; revert a filled field only if its current value still equals the recorded imported value. Late jobs from an undone batch are ignored.

`jobs`

- `id` UUID, nullable `batch_id`, `kind`, `state` (`queued`, `running`, `succeeded`, `failed`, `cancelled`)
- payload/progress/error JSON, attempts, `available_at`, heartbeat/lease timestamps
- `created_at`, `updated_at`, `finished_at`

Jobs survive restart. Handlers are idempotent. The lifespan runner claims one queued job in a short transaction, processes network/file work outside that transaction, and persists progress. On startup, expired `running` jobs return to `queued` with incremented attempts. Cap retries and expose terminal failure.

### 5.2 Deletion and orphan policy

Deleting an entry deletes its shelf joins but retains the item, source links, and cover as a cache. No orphan-prune endpoint is part of v1; that product question is deferred. Import undo may remove an orphan item only when its ledger proves the batch created it and no entry references it.

### 5.3 Migration policy

- Alembic from the first schema.
- Every schema change includes upgrade, downgrade where safe, and a migration test from the previous head.
- Never call `metadata.create_all()` in production. Tests may use migrations so schema behavior matches production.
- Back up the live DB before production migration.

## 6. Core application contracts

### 6.1 Normalization and identity

Normalize ISBN by stripping armor/separators and validating ISBN-10/13 checksums; convert ISBN-10 to canonical ISBN-13 when possible. Normalize near-match text with Unicode NFKD, combining-mark removal, casefold, punctuation-to-space, and collapsed whitespace.

Matching precedence for imports and add dedupe:

1. authoritative provider source ID;
2. canonical ISBN-13 (including validated ISBN-10 conversion-equivalence);
3. Calibre UUID;
4. normalized title plus normalized first author as an **ambiguous suggestion only**.

A fuzzy title/author result never merges automatically because the model is edition-level: translations and reprints commonly share that key. It requires an explicit preview decision or creates a separate item. A match result records rule, confidence, and decision provenance. If two or more exact identities from one record resolve to different existing items, return a typed `identity_conflict`, quarantine that record for explicit resolution, and attach no new identifier or entry automatically.

### 6.2 Provider boundary

The domain defines separate immutable models: `SearchCandidate`, `ItemPayload`, `ImportRecord`, `MatchDecision`, and `ImportPlan`, plus an async `Provider` protocol. Search candidates support multiple source references after merge. Import records carry personal fields, source-row provenance, validation errors, and conflict alternatives; they never masquerade as provider candidates. Provider and import adapters never leak raw source responses above infrastructure.

- Search providers concurrently with an independent five-second timeout.
- Return successful results when one provider fails and log a structured warning.
- Return a typed `providers_unavailable` error only if every enabled provider fails.
- Google Books is disabled, not failed, when no key exists.
- Bound result count and response size.
- Mock all provider traffic in tests; no default test contacts public APIs.

Open Library search must not map work-level `first_publish_year` into edition publication year. It may expose that value separately as `original_year`; `items.year` is populated only from edition data. A work URL resolves to an edition-picker list, preferring editions with valid ISBNs and useful language metadata for ranking, but never silently chooses one. A chosen result always carries an edition identity.

### 6.3 Cache-on-add transaction

1. Fetch and normalize the primary provider payload outside a DB transaction. Secondary `source_refs` supplied by the client become authoritative only after provider validation or agreement on canonical ISBN; ignore unverifiable refs.
2. Download, validate, resize, and encode a cover to a unique temporary file outside the transaction; enforce content-type, byte, pixel, URL, and timeout limits. Cover preparation failure is non-fatal.
3. Begin a short `BEGIN IMMEDIATE` write transaction, re-resolve exact identity through unique relational constraints, and insert/reuse item, identifiers, sources, and entry. Commit without a cover path.
4. After the relational commit, atomically install a prepared cover and update `cover_path` in a second short transaction, or enqueue an idempotent cover job. Failure leaves the valid entry intact and cleans/retries temporary files.
5. Return `201` for a new entry and `200` with `already_exists=true` for an existing entry. Protect double-submit through constraints and an idempotency key or equivalent request token.

Do not hold a SQLite write lock during remote, parsing, or image work. `POST /api/entries` remains one client round trip; relational creation is atomic, while cover installation is explicitly eventual and non-fatal.

### 6.4 Fill-empty versus explicit refresh

Import and resync may fill only fields considered empty (`NULL`, empty string, empty list/object as defined per field). They never overwrite non-empty user-visible fields. Identifier unions may add a previously absent key only when all exact identities resolve to the same item. For multiple source rows creating one new entry within the same commit, source confidence may choose the initial value; once an entry exists, a conflicting incoming score/status/note/date is recorded only in the batch's `import_records`, never on the entry itself. A manual entry edit always wins and must not be reverted by later imports.

Explicit item refresh requires `confirm_overwrite: true`. Fetch and validate the replacement first; on timeout, malformed data, or invalid payload, leave the item unchanged. In one short transaction, overwrite only provider-managed fields actually present in the successful response and add authoritative identifiers/source links. Omitted provider fields do not erase old values, and entry opinion fields are never touched. A manual-only item with no primary source returns a typed conflict.

### 6.5 Imports

Preview is mandatory and has no library side effects beyond durable staging/audit records. Uploaded Goodreads files are copied to `/data/imports/{batch_id}/` with size limits and a SHA-256 fingerprint. Parse and persist normalized `ImportRecord` rows, match decisions, explicit ambiguities, row errors, and preview counts. Calibre requests identify only a path relative to configured `BOOK_TRACKER_CALIBRE_DIR`; resolve and verify it cannot escape the mount, open `metadata.db` with `mode=ro` and `PRAGMA query_only=ON`, and stage its normalized rows during preview so commit never rereads a changing source DB.

Commit accepts a preview batch ID, rejects stale/missing/mismatched previews or unresolved ambiguities, and applies the persisted plan in one bounded `BEGIN IMMEDIATE` transaction. Revalidate authoritative identifiers because the library may have changed since preview. If exact keys now resolve to different items, mark the record `identity_conflict` and abort that record rather than choosing a winner. Otherwise create/reuse items and entries, fill empty item fields, attach shelves only to newly created entries, record audit conflicts/effects, and persist enrichment jobs before commit. Existing entries are never reset to `unsorted` or modified. All parsing, Calibre reads, cover copies, image work, and provider calls stay outside the write transaction. A uniqueness race may reload and reuse a winner only when every exact identity agrees on that item.

Enrichment is enqueued after commit and limited to about two provider requests per second. Every metadata or cover fill performed for an import appends its `import_effect` in the same short transaction as the mutation, so undo includes asynchronous effects. Triage is immediately usable. Job progress is polled from the API.

Undo is available in the UI until `undo_expires_at` (24 hours), while the durable audit ledger remains recoverable. Reverse effects in order, cancel queued jobs, and make late job results no-ops. Delete only batch-created entities that remain unmodified and unreferenced; revert a filled field only when its current value equals recorded `after_values`. The response reports reverted, retained, and skipped effects, and repeated undo is harmless.

## 7. HTTP API contract

All routes are under `/api`. JSON uses snake_case. Validation errors follow FastAPI's standard 422 shape; domain failures use:

```json
{"error":{"code":"stable_machine_code","message":"human readable","details":{}}}
```

Never expose tracebacks, host filesystem paths, provider keys, or raw SQL.

### 7.1 Routes

The product-spec route list is authoritative, with these refinements:

- Define static routes such as `/entries/bulk` before `/entries/{entry_id}`.
- Bulk mutation accepts either explicit `entry_ids` or a validated server-side filter plus `excluded_entry_ids`; never both. This supports select-all across unloaded virtual rows without sending thousands of IDs. Return affected count and apply in one transaction.
- `GET /entries` accepts repeated `status`, `shelf`, `q`, `sort`, `order`, `after`, `limit`, and triage-only flags. Default excludes `unsorted`; an explicit filter can include it. The response is `{items, next_cursor, total, facets}`, where `facets.status_counts` supplies the unobtrusive status counts required by the library UI for the current non-status filters.
- `POST /entries/accept-suggested` returns affected count and operates in one transaction over the server-side filter, not client-loaded IDs.
- `POST /items/{id}/refresh` requires explicit overwrite confirmation.
- `POST /entries` requires `confirm_near_match=true` before creating a title/first-author
  near-match; the initial 409 includes advisory existing entry IDs and performs no write.
- `POST /items/{id}/cover` accepts one JPEG, PNG, or WebP multipart upload, applies the shared
  byte/pixel/600px limits, and retains the previous valid cover if validation or installation fails.
- Import commit bodies contain preview batch IDs, not client-controlled source payloads.
- Cover files are served from a controlled route or static mount with immutable cache headers; database paths are relative and never accepted from clients.
- Add `GET /api/health/live` and `GET /api/health/ready`; readiness verifies DB access and migration head, not public provider availability.

OpenAPI is the API contract. Generate or validate frontend request/response types from it in CI so backend/frontend drift fails checks.

### 7.2 Keyset pagination

Use an opaque base64url-encoded, versioned JSON cursor containing sort key, direction, last normalized value, last ID, and null bucket. Clients must treat it as opaque. Reject a cursor when sort/filter identity does not match the request.

Every ordering is a whitelisted SQL expression plus `id` tie-breaker. NULL values always sort last using an explicit null bucket in both ordering and seek predicate. Text ordering, search, and cursor comparison use the same deterministic SQLite `normalize_text` function (Unicode NFKD, combining-mark removal, casefold, punctuation-to-space, and whitespace collapse). Tests cover asc/desc, nulls, duplicate values, deleted boundary rows, filter changes, malformed cursors, and `EXPLAIN QUERY PLAN` for common composite indexes. `total` is exact but advisory under concurrent edits; do not add an invalidation-prone count cache until measurement proves it necessary. Any mutation of the active sort key invalidates infinite pages and reloads from page one while restoring focus by entry ID.

## 8. Frontend architecture and behavior

Use strict TypeScript, React Router, TanStack Query, TanStack Virtual, React Hook Form with schema validation, shadcn/ui primitives, Tailwind tokens, and Motion. Avoid a custom global state store in v1.

Design tokens:

- dark-first zinc near-black surfaces, not pure black;
- a deliberate non-default saturated accent;
- Geist or Inter with bundled/local or privacy-safe loading;
- no generic border-shadow card grid;
- visible focus rings and touch targets at least 44 px where practical;
- all motion disabled/reduced under `prefers-reduced-motion`.

Cross-cutting behavior:

- Query keys include every server filter/sort value.
- Optimistic mutations snapshot and roll back cache; failed writes announce an accessible error and never silently lose input.
- Search input is debounced and cancellable; stale responses cannot replace newer results.
- Route-level error boundaries and useful empty/loading states are mandatory.
- Keyboard shortcuts are disabled while an input, textarea, select, dialog, or content-editable element owns focus unless explicitly relevant.
- `0` means score 10 only in score-shortcut context; Escape cancels an edit.
- Virtual rows have stable keys and fixed measured sizes. Sort/filter changes crossfade the container; rows do not use layout animations.
- Selection is independent of mounted rows: either explicit selected IDs or `all_matching=true` with excluded IDs. `Ctrl/Cmd+A` means all server rows matching the current filter, not merely loaded rows.

The product spec defines each screen. Sprint acceptance tests must include the critical keyboard flows and reduced-motion behavior.

## 9. Security and data safety

Although LAN-only, treat all imports, provider payloads, images, query parameters, and notes as untrusted.

- Parameterized SQL only; whitelist sort expressions.
- Escape rendered text; do not render provider descriptions as raw HTML without sanitization.
- Limit uploads, decompression/image dimensions, provider response sizes, and request timeouts.
- Prevent path traversal and symlink escape for Calibre and staged files.
- Enforce read-only Calibre mount in Compose and read-only SQLite URI/query mode in code.
- Do not log notes, import row contents, API keys, or full provider payloads.
- No CORS by default in the single-origin deployment.
- No auth means no public exposure. Documentation and Compose comments must state this prominently.

## 10. Testing and quality gates

Test pyramid:

- domain unit tests: ISBN armor/checksums/conversion-equivalence, accent normalization, merge/rank, edition-safe ambiguous matching, precedence/conflicts, status/score invariants, and cursor encode/filter/null/tie logic;
- repository/application integration tests against migrated temporary **file-backed** SQLite databases, covering WAL/foreign keys, concurrent identity races, import rollback/idempotency, existing-entry preservation, undo before/after user edits, stale-job recovery, pagination plans, and sort-key mutation reloads;
- provider/filesystem contract tests with mocked HTTP for concurrent partial failure, 429/timeout/malformed payloads, Open Library work/edition years, refresh complete/partial/failure, oversized/non-image covers, atomic rename, and path/read-only failures;
- import parser fixtures for BOM/quoted/malformed/realistic Goodreads exports and synthetic Calibre schema variants; verify source Calibre DB hashes never change;
- API tests through the ASGI app;
- frontend component tests for forms, optimistic rollback, keyboard guards, and accessibility;
- Playwright tests for add-manual, edit-score, import-preview/commit/triage, and critical navigation;
- container smoke test with persistent `/data`, read-only `/calibre`, readiness, and SPA fallback.

`make check` must format-check, lint, type-check, validate docs/state, and verify generated API types. `make test` must run deterministic unit/integration/component tests. Network-dependent and live-provider smoke tests are opt-in and never gates for normal commits.

Coverage is a diagnostic, not a target to game. Critical domain and import code should have branch coverage; acceptance criteria are behavior-based.

## 11. Observability and operations

Emit structured logs with timestamp, level, event name, request/job correlation ID, duration, and safe counters. Provider failures and job retries are warnings; exhausted jobs are errors. Never log secrets or personal notes.

The final image runs as a non-root user, has a healthcheck, and receives signals directly. Compose mounts:

- `${DATA_DIR:-./data}:/data`
- `${CALIBRE_DIR}:/calibre:ro`

Backup from the first production deployment using SQLite online backup semantics plus covers. A backup script must create a consistent DB copy, archive covers and import audit metadata, checksum outputs, enforce retention, run `PRAGMA integrity_check`, and be restore-tested. Do not copy a live WAL database naively. Schedule nightly execution from the host/NAS scheduler rather than pretending the single application process is a cron daemon. Deployment docs must include migration, rollback, backup, restore, and LAN-only proxy guidance.

## 12. Deferred decisions and explicit defaults

Defaults adopted until Mauro changes them:

1. `unsorted` is searchable and appears when explicitly filtered or through shelf views, but is excluded from `/` by default.
2. Entry deletion retains orphaned items/covers; no v1 prune action.
3. One item is one edition; rereads of another edition remain represented lossily by the same entry and incremented `reread_count`.
4. Series remains free text in metadata.

Deferred to v2+: export, authentication, sharing, multiuser UI, Calibre write-back, OPDS, and new item domains. Agents must not implement these as speculative infrastructure.
