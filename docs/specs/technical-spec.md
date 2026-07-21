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
5. start one cooperative durable-job polling loop in the FastAPI lifespan;
6. stop accepting job work and cancel cleanly on shutdown.

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
- `subtitle`, `year`, `cover_path`, `source`, `source_id` nullable
- `identifiers`, `metadata` required JSON-as-text with application validation
- `sort_author` generated from first metadata author
- `created_at`, `updated_at` required
- unique partial index on primary `(source, source_id)`
- case-insensitive title index

`item_sources`

- `item_id` foreign key to items, cascade delete
- `source`, `source_id` required
- primary key `(source, source_id)`; unique `(item_id, source)`

This table resolves an omission in the product draft: a merged search candidate can retain both Open Library and Google Books identities. `items.source/source_id` remains the preferred refresh source for simple reads.

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

`import_batch_entries`

- `batch_id`, `entry_id`, `item_id`
- booleans `created_entry`, `created_item`
- before-values JSON for fields filled or changed by the batch
- primary key `(batch_id, entry_id)`

This ledger makes undo safe: undo reverts only values created/filled by that batch and deletes only entries/items proven to have been created by it. It never deletes a pre-existing entry merely because `entries.import_batch` points at the latest import.

`jobs`

- `id` UUID, `kind`, `state` (`queued`, `running`, `succeeded`, `failed`)
- payload/progress/error JSON, attempts, `available_at`, lease timestamps
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

Matching precedence for imports:

1. canonical ISBN-13;
2. valid ISBN-10;
3. Calibre UUID;
4. normalized title plus normalized first author.

A match result records the rule and confidence. Near title/author matches from interactive search are warnings, not identity proof. Exact provider identity and canonical ISBN are exact duplicates.

### 6.2 Provider boundary

The domain defines immutable `Candidate` and `ItemPayload` models plus an async `Provider` protocol. Candidate must support multiple source references after merge. Provider adapters never leak raw provider responses above infrastructure.

- Search providers concurrently with an independent five-second timeout.
- Return successful results when one provider fails and log a structured warning.
- Return a typed `providers_unavailable` error only if every enabled provider fails.
- Google Books is disabled, not failed, when no key exists.
- Bound result count and response size.
- Mock all provider traffic in tests; no default test contacts public APIs.

Open Library work URLs resolve deterministically to an edition. Prefer an edition with a usable ISBN and requested/default `es`, then `en`, then the first stable edition result; return the selected edition identity to the user. Do not label an arbitrary work record as an edition.

### 6.3 Cache-on-add transaction

1. Fetch and normalize provider metadata outside a DB transaction.
2. Download, validate, resize, and encode a cover to a unique temporary file outside the transaction; enforce content-type, byte, pixel, and timeout limits.
3. Begin a short write transaction, resolve exact duplicates again, insert/reuse item and source links, atomically move the prepared cover to `covers/{item_id}.jpg`, and insert/reuse the entry.
4. Commit; on rollback, remove any newly moved file. A cover failure produces a valid entry with no cover.
5. Return `201` for a new entry and `200` with `already_exists=true` for an existing entry.

Do not hold a SQLite write lock during remote network work. `POST /api/entries` remains one client round trip; atomicity refers to persistent relational state, with explicit cleanup for file side effects.

### 6.4 Fill-empty versus explicit refresh

Import and resync may fill only fields considered empty (`NULL`, empty string, empty list/object as defined per field). They never overwrite non-empty user-visible fields. Identifier unions may add a previously absent key. For multiple source rows creating one new entry within the same commit, source confidence may choose the initial value; once an entry exists, a conflicting incoming score/status/note/date is recorded in `import_conflicts` rather than applied. A manual entry edit always wins and must not be reverted by later imports.

Explicit item refresh is destructive and must require `confirm_overwrite: true`. It fetches first, then atomically replaces provider-owned metadata and identifiers while preserving item identity and entry opinion fields. If fetch fails, existing data remains unchanged. A manual item with no refreshable source returns a typed conflict.

### 6.5 Imports

Preview is mandatory and has no library side effects. Uploaded Goodreads files are copied to a private staged path with size limits and a SHA-256 fingerprint. Calibre requests identify only a path relative to configured `BOOK_TRACKER_CALIBRE_DIR`; resolve and verify it cannot escape the mount. Open `metadata.db` with `mode=ro` and `PRAGMA query_only=ON`.

Commit accepts a preview batch ID, rejects stale/missing/mismatched previews, and applies the normalized rows in one short transaction. Large input parsing and cover copying happen before the write transaction where possible. Each row receives a deterministic source identity so retries are idempotent.

Enrichment is enqueued after commit and limited to about two provider requests per second. Triage is immediately usable. Job progress is polled from the API.

Undo is available until `undo_expires_at` (24 hours). It uses the batch ledger, is idempotent, and refuses destructive cleanup if later user edits or references make reversal unsafe; the response reports retained records.

## 7. HTTP API contract

All routes are under `/api`. JSON uses snake_case. Validation errors follow FastAPI's standard 422 shape; domain failures use:

```json
{"error":{"code":"stable_machine_code","message":"human readable","details":{}}}
```

Never expose tracebacks, host filesystem paths, provider keys, or raw SQL.

### 7.1 Routes

The product-spec route list is authoritative, with these refinements:

- Define static routes such as `/entries/bulk` before `/entries/{entry_id}`.
- `GET /entries` accepts repeated `status`, `shelf`, `q`, `sort`, `order`, `after`, `limit`, and triage-only flags. Default excludes `unsorted`; an explicit filter can include it. The response is `{items, next_cursor, total, facets}`, where `facets.status_counts` supplies the unobtrusive status counts required by the library UI for the current non-status filters.
- `POST /entries/accept-suggested` returns affected count and operates in one transaction over the server-side filter, not client-loaded IDs.
- `POST /items/{id}/refresh` requires explicit overwrite confirmation.
- Import commit bodies contain preview batch IDs, not client-controlled source payloads.
- Cover files are served from a controlled route or static mount with immutable cache headers; database paths are relative and never accepted from clients.
- Add `GET /api/health/live` and `GET /api/health/ready`; readiness verifies DB access and migration head, not public provider availability.

OpenAPI is the API contract. Generate or validate frontend request/response types from it in CI so backend/frontend drift fails checks.

### 7.2 Keyset pagination

Use an opaque base64url-encoded, versioned JSON cursor containing sort key, direction, last normalized value, last ID, and null bucket. Clients must treat it as opaque. Reject a cursor when sort/filter identity does not match the request.

Every ordering is a whitelisted SQL expression plus `id` tie-breaker. NULL values always sort last using an explicit null bucket in both ordering and seek predicate. Tests cover asc/desc, nulls, duplicate values, deleted boundary rows, filter changes, and malformed cursors. `total` is exact initially; do not add an invalidation-prone count cache until measurement proves it necessary.

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

- domain unit tests: normalization, ISBN validation, merge/rank, matching, status/score invariants, cursor logic;
- repository/application integration tests against temporary SQLite databases migrated by Alembic;
- provider contract tests with captured minimal fixtures and mocked HTTP;
- import parser fixtures for malformed/realistic Goodreads and synthetic Calibre schemas;
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

Backup from day one using SQLite online backup semantics plus covers. A backup script must create a consistent DB copy, archive covers, checksum outputs, enforce retention, and be restore-tested. Do not copy a live WAL database naively. Deployment docs must include migration, rollback, backup, restore, and LAN-only proxy guidance.

## 12. Deferred decisions and explicit defaults

Defaults adopted until Mauro changes them:

1. `unsorted` is searchable and appears when explicitly filtered or through shelf views, but is excluded from `/` by default.
2. Entry deletion retains orphaned items/covers; no v1 prune action.
3. One item is one edition; rereads of another edition remain represented lossily by the same entry and incremented `reread_count`.
4. Series remains free text in metadata.

Deferred to v2+: export, authentication, sharing, multiuser UI, Calibre write-back, OPDS, and new item domains. Agents must not implement these as speculative infrastructure.
