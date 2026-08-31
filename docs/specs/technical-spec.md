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
│   │   ├── domain/          # what a domain is (spec), which exist (registry), shared contracts
│   │   ├── domains/         # one package per domain: book/, album/ (section 6.6)
│   │   ├── infrastructure/  # SQLAlchemy repositories, provider HTTP, files, jobs
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
| `BOOK_TRACKER_ATTACHMENT_MAX_BYTES` | no | `26214400` | per-file cap on attachments; bounds the worst file, not the total |

Commit `.env.example` without secrets. Production must fail fast if `USER_AGENT_CONTACT` is absent; tests and local development may use an explicit test default.

## 5. Canonical data model

All timestamps are UTC RFC 3339 strings at API boundaries and timezone-aware Python datetimes internally. User-entered reading dates are ISO `YYYY-MM-DD`. Scores are nullable integers 1–10. **Status is per-domain**: each domain declares its own vocabulary and every domain has `unsorted` (DEC-057, section 6.6). Books are `unsorted`/`read`/`reading`/`to_read`/`wishlist`/`dropped`; albums are `unsorted`/`wishlist`/`pending`/`owned`. A write is validated against the item's own domain; a filter spans the union.

### 5.1 Tables

`items`

- `id` integer primary key
- `type` text, default `book`
- `title` required text
- `subtitle`, `year`, and `cover_path` nullable
- `identifiers` optional JSON API/cache projection derived from relational identifiers; never the uniqueness authority
- `metadata` required JSON-as-text with application validation
- `creator_primary` generated from the first metadata creator — the name **as written**, which is what the `q` filter matches and what the API falls back to when the record carries no rendered `credit`
- `creator_sort_override` nullable owner text: the sort name corrected by hand, or seeded from a Calibre `authors.sort`
- `creator_sort` and `creator_sort_normalized` nullable, derived from `creator_sort_override` or the `creator_sort_name` heuristic and maintained by the same mapper event as the columns above (DEC-051). Ordering reads these; display and search do not
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
- checks for score, nonnegative `reread_count`, nonnegative `progress`, and boolean `score_provisional`. **There is no CHECK on `status`** (migration `0014`, DEC-067 row 1): the vocabulary is the domain's, and a constraint listing the union of every domain's values could neither express "`owned` is not a book status" nor admit a domain added later without a migration on this table. `validate_status`, keyed on the item's own domain, is the authority and is strictly stronger
- unique `(user_id, item_id)`
- indexes supporting status/score/date list paths

`entry_formats`

- one row per (entry, format); `ON DELETE CASCADE` from `entries`, indexed by `format`
- the value is a closed vocabulary the domain declares (DEC-059), not a joined row: a
  shelf is something the owner invents, a format is something the domain knows
- writes are validated against the item's own domain and refused with 422 otherwise

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

`attachments`

- `id` integer primary key
- `item_id` foreign key to items, cascade delete
- `filename` required text — the name the owner uploaded, held here and **never** used as a path
- `byte_size` and `sha256` required
- unique on `(item_id, sha256)`, so re-uploading the same bytes to the same item updates the name rather than duplicating the row
- indexed on `item_id` and on `sha256`, the second because deletion is refcounted

Blobs live at `{data_dir}/attachments/{sha256[:2]}/{sha256}`, content-addressed
(DEC-048). Identical bytes occupy one blob however many items reference them, and a
blob is removed only when no row still points at its digest. The backup hardlinks
blobs rather than copying them; where `/data` and `/backups` are separate volumes —
which is the shipped Compose deployment — it links from a sibling backup instead,
and copies only when neither is possible.

A blob can still be orphaned by a route that does not go through
`delete_attachment` — an item deleted outside the application, or a crash between
writing the blob and committing its row. `akasha-attachments reclaim` collects
those (DEC-050). It reports by default and removes nothing without `--apply`,
reads the filesystem before the database so a row committed between the two reads
protects its blob, never touches a blob younger than an hour, and leaves anything
under `attachments/` that it did not write. A blob a backup has linked survives
it: the backup holds its own reference to the same inode.

Uploads and downloads stream. `BlobWriter` hashes and writes a chunk at a time
into a temporary and moves it under its digest at commit, so the per-file cap is
enforced as bytes arrive rather than after the whole upload is buffered, and
downloads are a `FileResponse`. The download's validator is an ETag over digest
**and** filename, not `immutable`: the blob cannot change but the response
carries the editable name, so a rename has to be able to invalidate it.

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
4. normalized title plus normalized first author as an **ambiguous suggestion only**;
5. normalized title plus **exact** year, scoped to one item type, as an ambiguous suggestion only, and only for a source that carries no creator at all.

Rule 5 exists for a source that identifies its records by an opaque URI and knows nothing else about them — a Letterboxd export names a film, a year and a link, and the film may already be held under a different form of the same identity. It is deliberately narrower than rule 4 in three ways: the year must be exact rather than near, the caller must name the item type it is matching within, and it applies only when no first creator is available. Title plus year is a much weaker key than title plus author, because a novel and the film made of it routinely share both; scoping it to one domain is what keeps a book out of a film's candidate list. A caller that supplies neither a year nor an item type gets rules 1–4 unchanged.

A fuzzy title/author result never merges automatically because the model is edition-level: translations and reprints commonly share that key. It requires an explicit preview decision or creates a separate item. A match result records rule, confidence, and decision provenance. If two or more exact identities from one record resolve to different existing items, return a typed `identity_conflict`, quarantine that record for explicit resolution, and attach no new identifier or entry automatically.

### 6.2 Provider boundary

The domain defines separate immutable models: `SearchCandidate`, `ItemPayload`, `ImportRecord`, `MatchDecision`, and `ImportPlan`, plus an async `Provider` protocol. Search candidates support multiple source references after merge. Import records carry personal fields, source-row provenance, validation errors, and conflict alternatives; they never masquerade as provider candidates. Provider and import adapters never leak raw source responses above infrastructure.

- Search providers concurrently with an independent five-second timeout.
- Return successful results when one provider fails and log a structured warning.
- Return a typed `providers_unavailable` error only if every enabled provider fails.
- Google Books is disabled, not failed, when no key exists.
- Bound result count and response size.
- Mock all provider traffic in tests; no default test contacts public APIs. Mocking transport is required; substituting a mock for the provider method under test is not a proof of that method and does not satisfy a correctness criterion. Boundary behavior is proven by replaying a committed recorded response (DEC-025).

Open Library edition lookup by ISBN uses `https://openlibrary.org/isbn/{isbn}.json`. That endpoint answers with a redirect to the edition record, so the shared provider client must follow redirects. `https://openlibrary.org/books/{id}.json` accepts an OLID only and returns 404 for an ISBN; it is never used for ISBN lookup.

Background enrichment tries Open Library first and falls back to Google Books when Open Library fails or returns nothing usable — a payload carrying no year, no cover, and no metadata counts as nothing usable. A job that exhausts both providers records a typed, human-readable reason retrievable through `GET /api/import/jobs/{id}`; enrichment failures are never swallowed. The reason is two columns: `jobs.error` holds the sentence a person reads, `jobs.error_code` the stable machine-readable type, and the endpoint returns both.

The enrichment queue has exactly one producer and one consumer, and both must exist. Committing an import enqueues `enrich_item` for the rows *that batch* created or matched, and for those only, so batch progress never reports work the import did not cause. The job runner is driven by a background task started in the application lifespan, which reclaims expired leases on idle passes and is cancelled on shutdown. `POST /api/enrichment/backfill` queues the same work for items already persisted with empty fields; it only ever enqueues, and the handler it enqueues fills empty fields only, so no path through it can overwrite a hand edit.

Enrichment installs a missing cover after its metadata transaction commits, never inside it: covers are remote and image work, and a cover failure must not undo a metadata fill. An item that already has a cover is never re-fetched.

Undated search results are resolved against `/works/{id}/editions.json` for every result, not the first, bounded by a concurrency semaphore. Publication dates are parsed by finding a year anywhere in the value, because Open Library publishes `"1984"`, `"1984-03"`, and `"Mar 09, 2005"` interchangeably.

Merged search results preserve the relevance ordering the providers returned. Each candidate retains its provider-returned position, the two providers are interleaved fairly, and title-match, language, and cover-presence signals act only as tie-breakers. Merging must never re-sort results by title.

Provider availability is reported by `GET /api/health/providers` — one row per provider with `available` and a `reason`, plus a `degraded` flag — so the interface can render a degraded-search state. The absence of `GOOGLE_BOOKS_API_KEY` is logged at startup rather than silently reducing search to one provider. This endpoint is deliberately separate from readiness: a missing key must never make the application look down.

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

An importer is a domain-owned connector implementing the `Importer` protocol in
`domain/importers.py`. It declares a permanent `name`, user-facing `label`, the ordered
`item_types` it can produce, an `ImportInputSpec` (`upload`, `path` or `directory`), the exact
`identity_kinds` it trusts, and the closed set of `error_codes` its reader may raise. Its `read`
method normalizes the source into an `ImportSnapshot`; `stage` archives the source or prepares local
assets after fingerprint replay has been ruled out; and `match` applies its source-specific identity
and near-match strategy through the narrow `ImportMatcher` view. Importers live under the package of
the domain they lead with; `IMPORTERS_BY_DOMAIN` is **derived** from their declarations, indexing a
connector under every domain it targets, and `IMPORTERS` is keyed by name so one is published once.
The shared pipeline never imports or branches on one.

**A connector may target more than one domain** (DEC-106), because a television export carries films
and shows in one file. `NormalizedImportRecord.item_type` is the domain one row targets, `None`
meaning the connector's first declared type; a record naming a type the connector did not declare is
refused at the boundary, as an undeclared identity kind already is. The shared service resolves the
domain **per record** — at validation, at commit, and in the enrichment guard — so nothing above the
registry branches on which domain it is holding.

**The service applies the target selection, not the reader.** A reader always emits every row it can
parse; `POST /import/{importer}/preview` carries the chosen subset of the connector's declared types,
and the service drops the rest before staging and counts what it dropped. The chosen set folds into
the preview fingerprint whenever it is a strict subset, so the same source imported as one domain and
then as another is two imports rather than a replay of the first; a connector declaring one domain
always selects all of it and so fingerprints exactly as it always did.

Rows a reader cannot target at all — a source kind no registered domain holds — are returned as
`ImportSnapshot.skipped`, a tally of `ImportSkip(reason, count)` keyed on the source's own word for
the kind. They are counted and reported, never row errors, and never conflated with rows excluded by
the target selection: the preview summary carries both counts separately.

**A connector guides its own users.** `ImportInputSpec` also carries `guide` (ordered steps, plain
strings — deliberately not markdown, so the screen needs no renderer and a connector cannot ship
markup into a shared surface), `empty_state`, an https `help_url`, and `browsable`. `ImportReadError`
carries `user_message` and `action` beside `code`/`message`/`details`: `code` is what the client
branches on, `message` is what the log keeps, and **`action` is the one imperative sentence a person
can act on**, which only the connector knows. `declared_read_error` republishes any code outside a
connector's declaration as `undeclared_import_error`, so an unknown vocabulary never leaves the
boundary. The conformance suite rejects a malformed guide, a non-https `help_url`, an empty or
malformed error vocabulary, and `browsable` declared without a `browse` method (DEC-080).

**A connector may offer two ways in, on one tab.** `ImportInputSpec.alternate` is a second spec
rendered beneath the primary, **exactly one level deep** and using a different `field`. A Calibre
library is one source reachable two ways — the folder on your machine or a mount the server can
already see — and splitting that across two tabs would name one thing twice (DEC-081). The route
picks between them by content type rather than by declaration: a body of parts is the `upload` or
`directory` input, a JSON body is the `path` one. `max_bytes` and `max_files` are declared per input
because a folder of covers is legitimately far larger than a CSV, and raising the shared ceiling to
suit one connector is how a limit stops meaning anything.

**A `directory` connector is a folder read by the browser.** The client selects a folder, filters it,
and posts the members it kept as multipart parts whose filenames are relative paths. The route
streams each part to disk — Starlette spools a part only past 1 MiB and a cover is smaller than
that, so `MultiPartParser.spool_max_size` is overridden to 1 and peak memory tracks one member rather
than the library (measured: a 60 MiB bundle at a 1.8 MiB Python peak). Member paths come from the
client and are validated before a byte is written: absolute paths, `..`, any segment beginning with
`.`, and anything outside the connector's `members` (`PurePosixPath.match` patterns) are refused.
Absolute patterns and patterns containing `..` are conformance failures. The surviving members
are materialized at `<bundle>/library/...` and the connector points its **ordinary adapter** at that
directory, so an uploaded library and a mounted one normalize through identical code. The route owns
the bundle and removes it once preview has staged what it needs, including when the read failed.
`accepts_files` is the connector's promise that its `read` can take one; conformance refuses
`kind="directory"` without it.

**A connector may plan an upload before it happens.** Declaring `incremental` and implementing
`IncrementalImporter` publishes `POST /api/import/{importer}/plan`, which takes the cheap half of the
source plus a `manifest` of `[{path, size}]` and answers with the subset worth sending. Content
addressing dedupes *storage*, not *transfer* — the server only recognises bytes after they arrive —
so without this an unchanged re-sync pays full price. **The client cannot hash instead:**
`crypto.subtle` requires a secure context, and while `localhost` is one, a reverse-proxied
`http://host.lan` is not, so a digest negotiation would work from the box and fail silently from the
rest of the LAN (DEC-082). The connector reaches storage only through `ImportInventory`, whose three
questions — `existing`, `with_cover` and attachment filenames through `attached` — are batched in
chunks of 500 so a large shelf is a constant number of round trips. `planned_upload` refuses a plan
naming a path the client never offered.
`metadata.db` therefore travels twice, once to plan and once to preview; that is a stated cost, not
an oversight. Planning by identity means a changed file under an unchanged identity is not detected,
and the escape hatch is that an item without a cover is always wanted. **The plan is never
load-bearing:** a client whose plan fails sends everything and says so.

**A `path` connector may be browsed.** Setting `input.browsable` and implementing `BrowsableImporter`
publishes `GET /api/import/{importer}/browse?path=`, which returns one level of the source as an
`ImportBrowseResult`: the relative path, its parent, the **names** of immediate subdirectories, and
whether that folder is itself importable. Names only — an absolute path would publish the
deployment's filesystem layout to anyone on the LAN. Confinement is resolved by the connector using
the same code its reader uses (`CalibreAdapter.confine`), so the picker cannot reach anywhere a
preview could not open: an absolute path, a `..` segment and a symlink out of the mount are all
refused, the last after resolution.

A `NormalizedImportRecord` has a neutral item (`title`, `subtitle`, `year`, identifiers, opaque
metadata and optional curated creator sort), a neutral entry (score, notes, date added, the target
domain's declared entry values, provisional flag and suggested status), shelves, row errors and
opaque source fields. Its `source_files` are connector-declared relative paths under the source root,
persisted beside `cover_stage`; every path must match the input's declared members. Before matching,
the shared service validates metadata against the target
domain's `fields`, entry values against `entry_fields`, suggested status against `statuses`, and
identifiers against the importer's declared kinds. An invalid connector row is refused with
`invalid_import_record`; it is never smuggled into another domain's vocabulary.

Preview is mandatory and has no library side effects beyond durable staging/audit records. Uploaded
Goodreads files are copied to `/data/imports/{batch_id}/` with size limits and a SHA-256 fingerprint.
Parse and persist normalized `ImportRecord` rows, match decisions, explicit ambiguities, row errors,
and preview counts. Calibre requests identify only a path relative to configured
`BOOK_TRACKER_CALIBRE_DIR`; resolve and verify it cannot escape the mount, open `metadata.db` with
`mode=ro` and `PRAGMA query_only=ON`, and stage its normalized rows during preview so commit never
rereads a changing source DB.

Commit accepts a preview batch ID, rejects stale/missing/mismatched previews or unresolved ambiguities, and applies the persisted plan in one bounded `BEGIN IMMEDIATE` transaction. Revalidate authoritative identifiers because the library may have changed since preview. If exact keys now resolve to different items, mark the record `identity_conflict` and abort that record rather than choosing a winner. Otherwise create/reuse items and entries, fill empty item fields, attach shelves only to newly created entries, record audit conflicts/effects, and persist enrichment jobs before commit. Existing entries are never reset to `unsorted` or modified. All parsing, Calibre reads, cover copies, image work, and provider calls stay outside the write transaction. A uniqueness race may reload and reuse a winner only when every exact identity agrees on that item.

A committed, unexpired batch may accept one `source_file` per request. The route resolves the path
to its persisted record and `matched_item_id`, streams it through the ordinary content-addressed
`BlobWriter` under `attachment_max_bytes`, inserts the attachment and appends an `attachment` import
effect carrying row id, filename and digest. One request per file keeps the request bound independent
of library size and isolates failures. Undo reverses that effect before its item's earlier create
effect, deleting the blob only after the row is gone and no other row references it. It retains a
row whose filename or digest no longer matches, and the existing attachment guard still retains an
item carrying any file the ledger does not claim.

Enrichment is enqueued after commit and limited to about two provider requests per second. Every metadata or cover fill performed for an import appends its `import_effect` in the same short transaction as the mutation, so undo includes asynchronous effects. Triage is immediately usable. Job progress is polled from the API.

Undo is available in the UI until `undo_expires_at` (24 hours), while the durable audit ledger remains recoverable. Reverse effects in order, cancel queued jobs, and make late job results no-ops. Delete only batch-created entities that remain unmodified and unreferenced; revert a filled field only when its current value equals recorded `after_values`. The response reports reverted, retained, and skipped effects, and repeated undo is harmless.

### 6.6 The domain contract

A **domain** is a kind of thing the library holds: books, albums or anime. This section is the whole contract. A new domain is built from it alone; reading how albums were built is not required and is not a substitute, because that record describes one domain's choices rather than the rules (DEC-052, DEC-066).

**The core is neutral and stays that way.** `items` has been `type` / `title` / `subtitle` / `year` / `cover_path` / `identifiers` / opaque `metadata` since Sprint 002, and `entries` hold one person's opinion of an item. No shared layer branches on which domain it is holding; a domain is never translated into another domain's vocabulary, and there is no `if item_type == ...` anywhere above the registry. **A shared layer that needs to know the domain asks the registry for a declaration; it does not grow a branch.**

```text
  api/ · application/ · infrastructure/     shared layers — never branch on item type
                    ▲
                    │ ask the registry for a declaration
  domain/spec.py     what a domain IS          domain/registry.py   which ones EXIST
                    ▲                                    ▲
      ┌─────────────┴─────────────┐        ┌─────────────┴─────────────┐
      │  domains/book/            │        │  domains/album/           │
      │  declaration · adapters   │        │  declaration · adapter    │
      │  · importers              │        │                           │
      └───────────────────────────┘        └───────────────────────────┘
                     never import each other
```

**The registry is code, not a plugin runtime** (product spec section 2). A domain is a Python object registered at import time. There is no discovery, no entry point, no sandbox and no versioning between a domain and the core: they are built and shipped together.

#### What a domain supplies

One `Domain` (defined in `backend/src/book_tracker/domain/spec.py`, declared in `backend/src/book_tracker/domains/<item_type>/__init__.py`), whose every field is an obligation:

| Field | Obligation |
|---|---|
| `item_type` | The value stored in `items.type`. **Permanent** — a lowercase identifier, never renamed, never user-facing. |
| `label` | The user-facing name of one item ("Book", "Album"). Copy, and free to change. |
| `identity` | An `IdentityStrategy`: how two candidates are judged the same record, and which source wins a merge. |
| `fields` | The ordered `FieldSpec` list describing this domain's metadata. Storage stays opaque; this is the only description of it that exists. |
| `enrichment` | An `EnrichmentSpec` — the ordered `item_identifiers.kind` values background enrichment may be keyed on, the provider order that answers them, and the metadata fields whose absence means a record is still worth a lookup — or `None` for a domain that does not enrich, which is a complete answer rather than a gap. A domain declares more than one key only when its **sources** supply different ones (a Letterboxd export names a film by a `boxd.it` URI and an IMDb export by its `tt` id, and neither carries the other's); an item carrying several is queued once, under the first it has, and every provider in the order must answer every declared key (DEC-113). All three parts are per-domain because all three were books' until Sprint 039, and a `completeness_fields` entry naming a field the domain does not declare is refused: a field it never stores is always absent, so the record would be re-queued for ever (DEC-067 row 3). `Domain.enriches` survives as a boolean reading of it. |
| `statuses` | The `StatusSpec` vocabulary, in the order a control offers it. Must contain `unsorted`, which must not be choosable. |
| `default_status` | What a newly added entry gets when nobody chose. Must be one of `statuses`. |
| `entry_fields` | Which of `date_started` / `date_finished` / `reread_count` this domain's entries have. Anything absent is **refused on write**, not merely hidden. |
| `progress` | A `ProgressSpec` — how far through one of these the reader is — or `None` where that means nothing, which is a complete answer (DEC-077 shape (a)). Bounded below and **never above**: `total_field` names a `number` metadata field for reading "20 / 170" and is display only, because a cached total goes stale, an airing series has none, and a refresh could lower it under a count already stored (DEC-092). `NULL` is *not recorded* and `0` is *recorded as zero*. |
| `entry_field_labels` | What this domain calls those fields, for the ones a neutral word gets wrong: an anime has *Rewatches*, a book has *Rereads*. Partial — `Started` and `Finished` are right for both, and a key naming a field the domain does not declare is refused by conformance. The client falls back to a neutral word, never to a book's. |
| `formats` | The `FormatSpec` vocabulary for how a copy is held. Closed and declared, which is what a shelf is not (DEC-059). |
| `entry_panel_label` | The heading over the personal region of the detail page. "Your reading data" is a book's phrase. |
| `recognize` | What a string pasted into the add box means to this domain, or `None`. |
| `chooses_covers` | Whether to offer the cover chooser. The shared chooser is Open Library's work-editions path, so only a domain that source serves may declare it; a domain declaring `false` is never offered a control that could only say no. |

Plus, outside the record itself:

- **An adapter** implementing the `Provider` protocol (`domain/providers.py`), in the domain's own package as `domains/<item_type>/providers.py`: `name`, `item_type`, `async search(query, limit)` and `async fetch(source_id)`, returning `SearchCandidate` / `ItemPayload`. It owns its own rate limit, User-Agent and authentication, and never leaks a raw provider response above infrastructure (section 6.2). Its boundary behaviour is proven against committed recorded responses, never against a mock of the method under test (DEC-025).
- **Cover URLs**, as candidates only. The shared pipeline keeps sole ownership of https upgrading, the host allowlist, the redirect policy and the pixel and byte bounds; a domain whose art lives on a new host adds that host to the allowlist and nothing else (seam 4).
- **A curated sort name where the source knows one.** `SearchCandidate.creator_sort` seeds the owner's override; the `creator_sort_name` heuristic runs only when nothing knew. A source that distinguishes a person from a group must say so this way rather than let the heuristic invert `Daft Punk` (DEC-051, DEC-052).
- **Zero or more importers** implementing `Importer` (`domain/importers.py`) in the domain's own
  package. Each owns source reading, normalization, matching and source/asset staging; the shared
  service owns validation, durable preview, commit, triage, fingerprint replay and undo (section
  6.5). A domain without an importer registers an empty tuple and remains complete.

#### Rules each supplied part must satisfy

- **Statuses.** Values are permanent and stored; labels are copy. `unsorted` exists in every domain because imports land there and the default library view hides it, and it is never offered as a choice. Every choosable status carries a triage hotkey, unique within the domain — the hotkey lives on the status rather than in a second table that can drift from it.
- **Formats.** Multi-valued on the entry and independent of status, so "wishlist → vinyl" is expressible. The vocabulary is closed and declared; a value the owner invents is a **shelf**, and the two must never converge into one control (DEC-059).
- **Entry values.** `validate_entry_values` is the one allowlisting boundary for PATCH, add and import. It admits neutral opinion fields, only the passage fields this domain declares, and `progress` only under the domain's progress rule; an unfamiliar key is refused naming the domain. Declaring a passage name outside `PASSAGE_FIELDS` remains a conformance defect because no shared write model can express it.
- **Metadata fields.** Names are permanent, labels are copy. A `rows` field declares `columns` and no other field type may; the renderer and the validator both key on that. A field may never shadow `title`, `subtitle`, `year` or `creator_sort_override` — those are neutral item columns edited *beside* the metadata, and a metadata field of the same name would render twice and save to one of them.
- **Identity.** `identity_key(candidate) -> str | None`, where `None` means *never merge this candidate*. That is a complete answer, not a degraded one: barcodes are not unique across releases, so albums have no cross-provider identity and merging on a weaker key would be wrong rather than approximate. `source_preference` decides which row of a merged group is primary and breaks ranking ties.
- **The URL recognizer must answer for any string and must never raise.** `resolve_input` asks every registered domain in turn, so a recognizer that raises does not fail its own domain — it denies every domain after it in the registry its turn. Parse through `split_url`, which is the shared guard (`urlsplit` raises on a malformed authority such as `http://[`). The shared loop isolates a raising recognizer as well, so the failure is contained; a domain that raises is still in breach.

#### What a domain may never touch

- **`items` and `entries` columns.** Everything a domain knows that the neutral columns do not carry goes in opaque `metadata`. A domain never adds a column, and never stores a value one of the four reserved item columns already holds.
- **Another domain.** No domain imports another, reads another's vocabulary, or renders under another's labels. A value that exists in two domains (`wishlist`, `digital`) is a coincidence of spelling, not shared state.
- **The shared pipelines.** Keyset pagination and cursors, the job runner, the import ledger and undo, backup, attachments, shelves, and the score/notes/dates entry layer are the core's. A domain that appears to need a change in one of them has found a seventh seam, and that is a decision to record, not a patch to make (DEC-055).
- **The cover pipeline's safety rules.** A domain supplies URLs; it does not relax the scheme, the allowlist, the redirect check or the size bounds.
- **The screens.** No screen branches on the item type. A domain that needs a screen to render differently declares the difference — a label, a vocabulary, a field spec — and the screen renders the declaration.

#### Where a domain's code lives

One package per domain, `backend/src/book_tracker/domains/<item_type>/`, holding its registry entry, its field spec, its status and format vocabularies, its identity strategy, its URL recognizer, its provider adapter and its importers. The point is that **one domain's team edits one directory**, so two domains can be built in parallel without contending for the same files.

Books and albums live there as of Sprint 028: `domains/book/` holds its declaration, its Open Library and Google Books adapters and its Goodreads and Calibre importers; `domains/album/` holds its declaration and its MusicBrainz adapter. What remains in `infrastructure/providers.py` is the shared HTTP boundary — the bounded retrying JSON read, the retry policy and the one client every adapter uses — which belongs to no domain. `domain/spec.py` is what a domain is; `domain/registry.py` is which domains exist.

**The practical guide to building one is [`docs/guides/adding-a-domain.md`](../guides/adding-a-domain.md)**, which walks this section step by step with diagrams and a worked example. This section is the contract; that guide is how to satisfy it.

Exactly three required things stay shared, and they are registration points rather than the
domain's substance. An importer adds the optional fourth:

1. **The registry** — the domain is added to `DOMAINS`, which is what makes it exist.
2. **Provider wiring** in the application lifespan, where its adapter is constructed with its configuration.
3. **Migrations**, which are global by nature and are the one path to a schema change.
4. **Importer registration**, when the domain has one — add the domain-owned connector to
   `IMPORTERS_BY_DOMAIN`; `IMPORTERS`, `GET /api/importers` and the generic routes derive from it.

Anything else a domain has to edit outside its own package is a coupling, and a coupling is a defect to record and cost. Two remain after Sprint 028, both deliberately (DEC-066, DEC-067): the published unions (`EntryStatus`, `EntryFormat`, `ItemTypeName`), which are three type-safe lines per domain that a test refuses to let drift, and the cover host allowlist, which is central precisely so a domain cannot widen it from its own package. The third — `entries.ck_entries_status`, a CHECK rendered from the registry when its migration was written — was removed in migration `0014`, because a domain needing a schema change on a shared table is not a coupling that can be paid per domain: two domain teams would both write that migration against the same alembic head.

#### How the core serves a domain

- `GET /api/item-types` publishes every field of every registered domain, and every screen renders from it: the library's tabs, the status chips, the format selector, the triage hotkeys, the metadata dialog and the detail page's field order.
- `GET /api/importers` publishes every registered importer and its input descriptor; the import
  screen renders its tabs and input control from that declaration.
- **A write is validated against the item's own domain** (`LibraryService._validated`), refused with a 422 that names the domain — the value is very often valid one row further down the library, so "invalid status" alone would send the reader hunting. A bulk write spanning domains is refused whole.
- **A filter legitimately spans domains**, so query parameters validate against the union of every domain's values while writes validate against one domain. `type` is not an ordinary facet dimension: both status facets clear it so the inbox badge keeps agreeing with the domain-agnostic triage screen, while `format_counts` applies it because that selector sits under the tab (DEC-062).
- Enrichment is queued only for domains that declare an `enrichment` spec, asked once per domain on that domain's own identifier kind and its own incompleteness rule.

#### How a domain is verified

`backend/tests/test_domain_conformance.py` is parametrized over `DOMAINS`: a domain is held to the contract **by existing**, and nothing in that file is extended when one is added. Its checks split in two, and the split is load-bearing. `REGISTRY_CHECKS` are what a domain satisfies on its own, and an unregistered fixture domain satisfies all of them — that is what makes this a contract rather than a description of books and albums. `CORE_CHECKS` are whether the core can host the domain: whether the published unions carry its values, and whether the database will accept them.

The suite is required to be able to fail. Malformed domains declared inside the file — a status with no label, a default outside the vocabulary, a `rows` field with no columns, a recognizer that raises — must each be rejected by the check that owns them.

## 7. HTTP API contract

All routes are under `/api`. JSON uses snake_case. Validation errors follow FastAPI's standard 422 shape; domain failures use:

```json
{"error":{"code":"stable_machine_code","message":"human readable","details":{}}}
```

An import connector may add `user_message` and `action` to that object; both are omitted when it
did not supply them, so every other refusal keeps exactly the shape above (§6.5, §7.1).

Never expose tracebacks, host filesystem paths, provider keys, or raw SQL.

### 7.1 Routes

The product-spec route list is authoritative, with these refinements:

- Define static routes such as `/entries/bulk` before `/entries/{entry_id}`.
- Bulk mutation accepts either explicit `entry_ids` or a validated server-side filter plus `excluded_entry_ids`; never both. This supports select-all across unloaded virtual rows without sending thousands of IDs. Return affected count and apply in one transaction.
- `GET /entries` accepts repeated `status`, `shelf`, `format`, `type`, `q`, `sort`, `order`, `after`, `limit`, and triage-only flags. Default excludes `unsorted`; an explicit filter can include it. `type` selects domains and is validated against the registry; unlike `shelf` and `format`, repeating it *widens*, because a row has exactly one type. The response is `{items, next_cursor, total, facets}`. `facets.status_counts` is the whole-library total per status — what the inbox badge counts — `facets.status_counts_by_type` splits the same counts by item type, because a status two domains share is not one number on a screen that lists each domain's statuses separately, and `facets.format_counts` does the same for formats. Each facet clears its own dimension, so a count reads as "what you would get if you clicked this". **`type` is the exception and is not one dimension** (DEC-062): both status facets clear it, so the inbox badge keeps agreeing with the domain-agnostic triage surface and an unselected tab still has a count to show, while `format_counts` applies it, because that selector sits under the tab.
- `GET /item-types` publishes each domain's metadata fields, its ordered status vocabulary (value, label, whether it is directly choosable, triage key), its default status, which entry fields it has, its formats, and the heading for the personal region of the detail page. Every screen renders from it rather than branching on the item type (seam 5b).
- Writes validate `status`, `formats` and the passage fields (`date_started`, `date_finished`, `reread_count`) against **the item's own domain**, returning 422 with a message naming the domain. A bulk write spanning domains is refused whole rather than half-applied.
- `POST /entries/accept-suggested` returns affected count and operates in one transaction over the server-side filter, not client-loaded IDs.
- `POST /items/{id}/refresh` requires explicit overwrite confirmation.
- `POST /entries` requires `confirm_near_match=true` before creating a title/first-author
  near-match; the initial 409 includes advisory existing entry IDs and performs no write. It also
  accepts `notes`, `formats` and the passage fields, each validated against the item's own domain
  and refused with a 422 naming it — the same rule `PATCH` follows, applied **before the write**, so
  a refusal never leaves a half-added row.
- A manual `POST /entries` payload must name `manual.item_type`; absence is a 422 rather than a
  fallback to the default domain. Its opaque `manual.metadata` is validated against that domain's
  `fields`, and `/add` renders the same declaration behind an authoritative domain chooser.
- **Two searches exist and they are not the same kind of thing.** `GET /entries?q=` is SQL over
  stored normalized projections: free, local, and reached by every keystroke the library filter
  makes. `GET /search?q=&type=` fans out to the chosen domain's providers at five seconds each and
  is counted against a daily budget (DEC-045). Since Sprint 029 both are spent from `/` behind one
  input, so **which of them a keystroke reaches is a frontend rule, stated in section 8** — the
  backend contract is unchanged, and the invariant it protects is unchanged with it: rendering a
  library page consults no provider, at any query length. A search reaches only the named domain's
  providers (DEC-052 seam 4); the spend is recorded and never blocked, because somebody is waiting
  for it.
- `GET /search/resolve` takes the same input when it is a URL or a bare ISBN and skips the keyword
  search entirely. It is domain-neutral: a MusicBrainz release-group URL resolves exactly as an Open
  Library edition URL does, which is why the one bar advertises the path for every domain.
- `GET /search/preview` returns one candidate's full provider payload and writes nothing. It exists
  because a search result carries an identity but not a description, a page count or a tracklist,
  and there is no provider response cache, so it is one live request per call (DEC-064). It follows
  `search`'s quota rule rather than enrichment's: the spend is recorded and never blocked, because
  somebody is waiting for it.
- `POST /items/{id}/cover` accepts one JPEG, PNG, or WebP multipart upload, applies the shared
  byte/pixel/600px limits, and retains the previous valid cover if validation or installation fails.
- `GET /importers` publishes `{id, label, item_types, input, attachment_max_bytes}` from the importer registry, where
  `input` carries the connector's declared `guide`, `empty_state`, `help_url`, `browsable`,
  `incremental`, `accepts_files`, `max_bytes`, `max_files` and a one-deep `alternate`, alongside
  `kind`/`label`/`field`/`accept`/`placeholder`/`help`.
  `POST /import/{importer}/preview` accepts the declared upload field, path field, or — for a
  `directory` input — repeated file parts whose filenames are relative paths inside the chosen
  folder. A connector with an `alternate` accepts either on the same route, chosen by content type.
  It also accepts an optional `targets` — a comma-separated multipart field or a JSON list — naming
  which of the connector's `item_types` this import is for; absent means all of them, and a type the
  connector does not declare is a 422 `invalid_import_targets`. Its `summary` carries
  `skipped_not_requested`, `skipped_unsupported` and `skipped_reasons` beside the existing counts.
  An oversize bundle is a 413 naming the alternate; a member outside the declared shape is a 422
  that names what to choose instead.
  `POST /import/{importer}/commit` accepts only the durable preview batch ID and ambiguity choices,
  never client-controlled normalized records. Calibre's path is relative to the configured mount;
  preview responses may expose its normalized UUID/book identity and whether a local cover was
  staged, never a source filesystem path.
- `POST /import/{importer}/plan` exists only for a connector that declares `incremental`; any other
  is a 404 `importer_not_incremental`. It applies the same member validation the upload route does,
  so a manifest cannot smuggle a path the upload would refuse, and it removes its bundle on every
  path. See §6.5.
- `POST /import/{importer}/batches/{batch_id}/files` takes multipart `path` and exactly one `file`
  after commit. The path must be both connector-declared and named by one persisted record's
  `source_files`. Unknown importer/batch/path is 404; a non-committed, undone or expired batch is
  409; an over-cap body is 413 with no attachment row or orphaned blob; an undeclared path is 422.
  Repeating identical bytes is idempotent through the item/digest uniqueness constraint.
- `GET /import/{importer}/browse?path=` exists only for a connector that declares `browsable`; any
  other importer, and any unknown one, is a 404 `importer_not_browsable`. It is read-only, returns
  directory names and nothing else, and refuses an absolute path, a `..` segment or a symlink out of
  the mount with the connector's own 422. See §6.5.
- **A refused read carries what the reader can do about it.** The error envelope is
  `{error: {code, message, details}}`, plus `user_message` and `action` **when the connector supplied
  them** — omitted otherwise, so every other error keeps the shape it has always had. The client
  prefers `user_message` over `message` for display and renders `action` beside it.
- Cover files are served from a controlled route or static mount with immutable cache headers; database paths are relative and never accepted from clients.
- `GET /api/export` streams the whole library rather than buffering it: rows are walked in keyset
  batches of 200 and each is serialized and yielded on its own, so peak memory tracks the batch and
  not the corpus (measured at x1.07 JSON / x1.66 CSV peak for x10 output). Select **columns, not
  mapped entities** — an ORM entity is retained by the `Session` identity map for as long as the
  session lives, and `yield_per` does not help because SQLite's driver has no server-side cursor and
  materializes the result anyway. The JSON omits every derived column by design; the CSV neutralizes
  leading `=`, `+`, `-`, `@` so a spreadsheet reads a note as text, which makes the JSON the lossless
  artifact and the CSV the convenience view.
- Add `GET /api/health/live` and `GET /api/health/ready`; readiness verifies DB access and migration head, not public provider availability. `GET /api/health/providers` reports provider configuration separately and never affects readiness.

OpenAPI is the API contract. Generate or validate frontend request/response types from it in CI so backend/frontend drift fails checks.

### 7.2 Keyset pagination

Use an opaque base64url-encoded, versioned JSON cursor containing sort key, direction, last normalized value, last ID, and null bucket. Clients must treat it as opaque. Reject a cursor when sort/filter identity does not match the request. **The filter identity must list every filter**, `type` included: one that omits a filter accepts a cursor cut under a different query and then skips or repeats a page silently, which is a wrong answer rather than an error. **The version is currently 2**; it is bumped whenever a stored projection a cursor compares against changes meaning, so a cursor issued before the change fails with `invalid_cursor` rather than silently skipping or repeating a page.

Every ordering is a whitelisted SQL expression plus `id` tie-breaker. NULL values always sort last using an explicit null bucket in both ordering and seek predicate. Text ordering, search, and cursor comparison read stored normalized projections. Search and the `title` sort read `items.title_normalized` and `items.creator_primary_normalized`; the `creator` *ordering* reads `items.creator_sort_normalized` instead, because the name a creator sorts under is not the name it displays under (DEC-051). They hold the domain `normalize_text` value (Unicode NFKD, combining-mark removal, casefold, punctuation-to-space, and whitespace collapse) and maintained by a mapper event on every item write (DEC-036). They are not generated columns, because SQLite generated columns cannot call an application-registered function, which is also why the earlier per-row UDF was replaced: it cost 312 ms p95 on a contended 10,000-entry first page. Tests cover asc/desc, nulls, duplicate values, deleted boundary rows, filter changes, malformed cursors, and `EXPLAIN QUERY PLAN` for common composite indexes. `total` is exact but advisory under concurrent edits; do not add an invalidation-prone count cache until measurement proves it necessary. Any mutation of the active sort key invalidates infinite pages and reloads from page one while restoring focus by entry ID.

## 8. Frontend architecture and behavior

Use strict TypeScript, React Router, TanStack Query, TanStack Virtual, React Hook Form with schema validation, shadcn/ui primitives, Tailwind tokens, and Motion. Avoid a custom global state store in v1.

Design tokens:

- dark-first zinc near-black surfaces, not pure black: zinc-950 background, zinc-900 surface, zinc-800 border, zinc-50 text, zinc-400 muted;
- a deliberate non-default saturated accent: amber-400 on a zinc-950 foreground, with a score ramp of red-400 (1–3), amber-400 (4–6), lime-400 (7–8), emerald-400 (9–10) (DEC-026);
- Geist or Inter with bundled/local or privacy-safe loading. Inter is self-hosted and bundled; naming a font without loading it is not compliance;
- small controls carry their own radius token: at the card radius a 16 px checkbox reads as a radio button;
- these are declared once as Tailwind theme tokens and CSS variables. Inline colour literals in components are a defect;
- no generic border-shadow card grid;
- visible focus rings and touch targets at least 44 px where practical;
- all motion disabled/reduced under `prefers-reduced-motion`.

Cross-cutting behavior:

- Query keys include every server filter/sort value.
- Optimistic mutations snapshot and roll back cache; failed writes announce an accessible error and never silently lose input.
- Search input is debounced and cancellable; stale responses cannot replace newer results.
- **One input feeds both searches, and the rule deciding which it reaches is load-bearing**
  (DEC-065, as built in DEC-073). The library filter is debounced **250 ms** into the URL's `q` and
  is the only thing typing normally reaches. A **provider** search fires only when every one of
  these holds: the query has been still for **~800 ms** measured from the last keystroke, it is at
  least **three characters**, the URL has caught up with the box, the library has actually answered
  — pending or errored is "we do not know yet", not "the library has nothing" — and it answered with
  **zero** rows. It never fires twice for the same string and domain. The **Add** button overrides
  all of it and searches immediately, serving a repeat from what it already holds.
  - Every clause is there because the literal rule — search whenever the library misses — fires once
    per keystroke while typing any title not already owned, which is every add. That is the quota
    (DEC-045) and the tier breach DEC-044 already measured. **The rule is verified by counting
    requests, not by inspection.**
  - The provider search owns an `AbortController` and a request-id guard: a superseded request is
    aborted rather than left running against a rate-limited API, and a late response for an older
    query may not replace a newer result set. Both are quota protection, not tidiness.
  - Results belong to the domain that produced them, and switching domain clears them rather than
    showing one domain's results under another's name.
- **Two result sets on one page are two regions, not one.** The library is a `role="feed"` with
  server-side `aria-posinset`/`aria-setsize` (DEC-038); provider results are a plainly labelled
  `section` beside it and are never announced as feed items. They render **below** the library:
  the library virtualizes against the window, so a variable-height block above it moves the
  `scrollMargin` every row measures itself against, which is the Sprint 013 class of bug avoided by
  construction rather than survived (DEC-073).
- **Keyboard shortcuts belong to the surface that has focus.** With provider results on screen,
  `j`/`k` and the digit shortcuts stay with the library and do nothing from inside the results
  region, so one list's shortcut never acts on the other list.
- Route-level error boundaries and useful empty/loading states are mandatory.
- Keyboard shortcuts are disabled while an input, textarea, select, dialog, or content-editable element owns focus unless explicitly relevant. The component library renders these as buttons carrying roles rather than as native tags, so the guard is on the `dialog`, `alertdialog`, `combobox`, `listbox`, and `menu` roles as well as on tag names (DEC-029).
- `0` means score 10 only in score-shortcut context; Escape cancels an edit.
- Virtual rows have stable keys and fixed measured sizes. Sort/filter changes crossfade the container; rows do not use layout animations.
- Both list densities are `role="feed"` with `article` children carrying `aria-posinset`/`aria-setsize` from the server-side total, and the feed sets `aria-busy` while a page is loading. Neither is an ARIA table: they have no column headers and no cells, and claiming otherwise produced a structure screen readers could not navigate (DEC-038).
- The library grid virtualizes rows of cards, not single entries. The column count is derived from the measured container width so no card falls below its minimum width; a virtual row is one fixed-height band of that many fixed-height cards. Mounted DOM is therefore bounded per row and per card, and both bounds are asserted.
- **The library and Triage virtualize against the window, not against scroll containers of their own.** A primary surface uses the whole page, so the list element has no overflow and its virtualizer is given a measured `scroll margin` for what sits above it. The mounted-DOM bounds are unchanged and are re-asserted at 10,000 Library entries and 200 Triage entries against the window (DEC-073, DEC-087).
- A library card is a fixed box: fixed-size cover, clamped metadata, and a control row that never wraps. Controls that expand (the compact score picker) render as an overlay anchored inside the card, so expanding a control never changes a card's layout box or paints into a neighbor.
- Two components are deliberately bespoke rather than library primitives, and must stay that way (DEC-026). The score picker may not become a portalled primitive, because its expanded panel is required to remain geometrically inside its card; portalling to `document.body` breaks that by construction. The library card box may not adopt a primitive carrying its own intrinsic padding, because the card height is pinned for fixed-size virtualization and the column calculation subtracts a matched row padding.
- Every user action produces visible feedback. Feedback rendered only into a visually hidden element is a defect, not an implementation. The visible surface carries the accessible announcement rather than sitting beside a second, duplicate live region (DEC-028): a confirmation is announced once and seen once.
- Selection is independent of mounted rows: either explicit selected IDs or `all_matching=true` with excluded IDs. `Ctrl/Cmd+A` means all server rows matching the current filter, not merely loaded rows.
- In Triage, pointer selection is checkbox-only and row-body clicks open detail. The native score select patches one entry immediately through `PATCH /entries/{id}` with an optimistic snapshot/rollback. A row status select represents a **target**, not the persisted `unsorted` value: explicit draft → imported `suggested_status` → the row domain's `default_status`. It offers only that domain's `choosable` statuses, so Inbox is neither displayed nor selectable. Changing the target updates a client draft map mirrored to tab-scoped `sessionStorage`; changing it back to the suggestion/default removes the explicit draft. The icon-only row Apply action is the only commit surface for that draft and sends the existing `PATCH /entries/bulk` shape for one entry. A successful attempt clears only its draft, a failed one remains visible and retryable, and both Triage and Library queries invalidate after success. Explicit checkbox bulk actions still commit immediately and clear drafts for entries they move. Native selects remain deliberate in this fixed-height virtual row: an expanding score picker is clipped by the row geometry, while a portalled select hides the route containing its focused trigger and fails the `aria-hidden-focus` gate (DEC-086, DEC-087, DEC-095, DEC-096).

The product spec defines each screen. Sprint acceptance tests must include the critical keyboard flows and reduced-motion behavior.

## 9. Security and data safety

Although LAN-only, treat all imports, provider payloads, images, query parameters, and notes as untrusted.

- Parameterized SQL only; whitelist sort expressions.
- Escape rendered text; do not render provider descriptions as raw HTML without sanitization.
- Limit uploads, decompression/image dimensions, provider response sizes, and request timeouts.
- Prevent path traversal and symlink escape for Calibre and staged files. For attachments this is structural rather than filtered: the stored path is the content digest and an uploaded filename is only ever metadata, so no caller-supplied string reaches the filesystem.
- **Serve attachments as downloads, never inline.** `Content-Disposition: attachment`, `X-Content-Type-Options: nosniff`, and a fixed `application/octet-stream`. Attachments are the only user-controlled content type the application serves — everything else is re-encoded to JPEG by the cover pipeline — and the SPA shares their origin, so an uploaded HTML or SVG rendered inline would run against the application's own API.
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

CI runs the Chromium Playwright suite as its own job. The layout and keyboard regressions are the only automated guardrail on the virtualization and grid contracts in section 8, and they are not part of `make test`. The same job runs the `@axe-core/playwright` checks in `e2e/accessibility.spec.ts`, which fail on any `serious` or `critical` WCAG 2.0/2.1 A/AA violation on every reachable screen, including the score-picker overlay open inside its card and a dialog open over detail (DEC-038). Lesser impacts are reported, not failed. Automated checks cover only what is computable from a rendered tree; the keyboard and focus checklist is walked by hand and recorded in the worklog.

Automated gates are necessary and not sufficient. A sprint touching user-visible behavior additionally requires the walkthrough gate in `AGENTS.md` section 3: the application is run against realistic data, the sprint's flow is performed end to end, and the observations are recorded in the worklog. This requirement exists because thirteen sprints closed green on a product with an invisible feedback layer and a wholly failing enrichment pipeline (DEC-025).

Coverage is a diagnostic, not a target to game. Critical domain and import code should have branch coverage; acceptance criteria are behavior-based.

## 11. Observability and operations

Emit structured logs with timestamp, level, event name, request/job correlation ID, duration, and safe counters. Provider failures and job retries are warnings; exhausted jobs are errors. Never log secrets or personal notes, and do not rely on call sites to remember: `logging.py` redacts a denylist of keys (notes, review, description, payload, row/record, api_key, token and kin), scrubs configured secret values out of any string so a key embedded in a logged URL cannot escape, truncates oversized values under innocent keys, and recurses into nested structures. Standard-library records are routed through the same chain, so a `logger.warning(..., extra={...})` is rendered and redacted rather than having its structured fields silently dropped.

The final image runs as a non-root user (uid 10001), has a healthcheck, and receives signals directly; `STOPSIGNAL` is `SIGTERM` and uvicorn runs its own graceful shutdown, so a stop closes SQLite rather than killing it mid-write. Compose mounts, by default (DEC-075):

- `data:/data` — named volume, `AKASHA_DATA_VOLUME` overridable
- `backups:/backups` — named volume, `AKASHA_BACKUP_VOLUME` overridable
- `${CALIBRE_DIR:-./calibre}:/calibre:ro`

A fresh named volume is seeded from the image's own `/data`, `/backups` on first mount, ownership included, so there is nothing to `chown` from the host. Opting into `${DATA_DIR:-./data}:/data` and `${BACKUP_DIR:-./backups}:/backups` as real host directories instead is a second, explicitly invoked Compose file, `compose.bind-mounts.yaml`.

Backups live outside the data volume, not under `/data` (DEC-040): a copy kept inside the volume it protects is lost with that volume. `backup_dir` derives as a sibling of `data_dir`. The backup itself is `book_tracker.backup`, exposed as the `akasha-backup` console script and driven nightly from the host scheduler by `scripts/backup.sh` — the single application process is not a cron daemon. It copies the database through SQLite's online backup API and never file-by-file, archives covers and import audit metadata, writes a manifest and SHA-256 checksums, runs `PRAGMA integrity_check` on the copy, and enforces label-scoped retention. Restore verifies every checksum and the database before writing, and refuses a non-empty target. Nothing on the restore path imports the application, so restoring onto a bare machine needs no configuration.

Migrations run at startup, preceded by an online backup whenever revisions are pending against an existing database; startup fails rather than migrating without one, and the backup is taken once per revision rather than once per restart attempt (DEC-039). Deployment docs cover migration, rollback, backup, restore, and LAN-only proxy guidance in `docs/operations/runbook.md`.

## 12. Deferred decisions and explicit defaults

Defaults adopted until Mauro changes them:

1. `unsorted` is searchable and appears when explicitly filtered or through shelf views, but is excluded from `/` by default.
2. Entry deletion retains orphaned items/covers; no v1 prune action.
3. One item is one edition; rereads of another edition remain represented lossily by the same entry and incremented `reread_count`.
4. Series remains free text in metadata.

Deferred to v2+: authentication, sharing, multiuser UI, Calibre write-back and OPDS. Unscheduled
item domains remain speculative; the roadmap-authorized movie line is governed by Sprints 046–047
and DEC-098 rather than by this deferral.
