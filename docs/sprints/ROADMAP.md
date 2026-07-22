# Implementation Roadmap

**Plan revision:** 3
**Delivery rule:** one sprint must leave a demonstrably usable or risk-reducing increment, green quality gates, updated documentation, and a clean worktree.
**Active sprint:** [Sprint 008](008-book-metadata-covers.md)

## Dependency graph

```text
001 Foundation
 └─ 002 Domain + persistence
     ├─ 003 Entries + shelves API
     │   └─ 004 Frontend shell + library
     └─ 005 Providers + cached add API
         └─ 006 Add/detail/edit UI
             └─ 007 Goodreads import
                 └─ 008 Working metadata + covers
                     └─ 009 Calibre import
                         └─ 010 Durable enrichment + undo
                             └─ 011 Triage workflow
                                 └─ 012 Scale, accessibility, resilience
                                     └─ 013 Container, backup, release
```

Sprints 003 and 005 are architecturally parallel but are intentionally sequenced for one-agent worktrees and simpler handoffs. Frontend vertical slices begin only after stable API contracts exist.

## Sprint index

| Sprint | Outcome | Key acceptance signal | Depends on | Status |
|---|---|---|---|---|
| 001 | Reproducible monorepo foundation | Backend/frontend hello slices, migration, all quality gates and dev commands work | — | completed |
| 002 | Domain model and durable persistence | Migrations and repositories enforce identity, score/status, source, and shelf invariants | 001 | completed |
| 003 | Entries, shelves, filtering, keyset API | CRUD and list API pass contract tests including null-safe asc/desc cursors | 002 | completed |
| 004 | Design system and virtualized library | `/` renders and edits a seeded multi-thousand-entry library by keyboard | 003 | completed |
| 005 | Metadata providers and cached add API | Merged provider search, URL/ISBN resolve, dedupe, and local cover cache work with mocked failures | 002 | completed |
| 006 | Add, detail, and metadata-edit UI | Manual/provider add and edit flows work end-to-end without mouse | 004, 005 | completed |
| 007 | Goodreads preview and commit | Realistic CSV imports idempotently as unsorted with suggestions/provisional scores | 006 | completed |
| 008 | Working book metadata and covers | Three real editions add with normalized metadata and render fully offline | 007 | in_progress |
| 009 | Calibre preview and commit | Read-only synthetic Calibre library imports/resyncs without overwriting user data | 008 | planned |
| 010 | Durable jobs, enrichment, ledger undo | Restart-safe enrichment and safe 24-hour undo pass crash/retry tests | 009 | planned |
| 011 | Bulk-first triage | Hundreds of unsorted entries can be filtered, selected, bulk accepted, and keyboard-triaged | 010 | planned |
| 012 | Production-quality hardening | Performance budgets, accessibility audit, error/reduced-motion behavior, full E2E suite pass | 011 | planned |
| 013 | Deployable v1 | Non-root image, Compose, healthchecks, backup/restore drill, persisted smoke test pass | 012 | planned |

## Detailed future sprint contracts

These are binding outcome boundaries. Before a future sprint becomes active, the closing agent for the prior sprint must expand it into a dedicated `docs/sprints/NNN-*.md` file using `TEMPLATE.md`, incorporating actual deviations.

### Sprint 002 — Domain model and persistence

Scope:

- Item identifiers/sources, ISBN and text normalization, edition-safe ambiguity decisions, and fill-empty merge semantics.
- Initial complete v1 schema for items, item identifiers, item sources, entries, shelves, import records/effects, and jobs.
- SQLAlchemy repositories and transaction fixture.

Acceptance:

- Alembic upgrade from empty DB and downgrade/upgrade round trip pass.
- Foreign keys are demonstrably enabled on every connection.
- Constraints reject invalid scores/statuses and duplicate authoritative identifiers/sources, including ISBN-10/13 conversion-equivalent races.
- Repository tests prove exact item/entry dedupe, split exact identities produce a typed conflict without mutation, ambiguous title/author never auto-merges, and shelf behavior.
- No API surface beyond health/config is required.

### Sprint 003 — Entries, shelves, filtering, keyset API

Scope:

- Entry/item/shelf read and mutation services and routes.
- Server-side filters, counts, whitelisted sorting, opaque keyset cursors.
- Bulk entry mutation accepts explicit IDs or server filter plus exclusions; accept-suggested uses the same validated filter contract.

Acceptance:

- OpenAPI and API tests cover happy/error paths.
- NULL-last pagination works in both directions with duplicate values, matching text collation, deleted boundaries, query-plan assertions, and reload after sort-key edits.
- Default library excludes unsorted; explicit filters can find it.
- Manual score changes clear provisional state.
- Static `/entries/bulk` routing cannot be shadowed by `/{entry_id}`.

### Sprint 004 — Frontend shell and virtualized library

Scope:

- Design tokens, application shell, routing, typed API client, Query setup.
- Grid/table library, filters, sort, search, status counts, fixed-size virtualization.
- Optimistic inline score/status editing and keyboard guards.

Acceptance:

- Seeded 5,000-entry fixture remains responsive and mounts only visible rows.
- Grid/table preference persists.
- Optimistic failure rolls back and is announced accessibly.
- `/`, `a`, and score shortcuts obey input-focus rules and reduced motion.

### [Sprint 005 — Providers and cached add API](005-providers-add-api.md)

Scope:

- Open Library and optional Google Books adapters, merge/rank, edition-safe URL/ISBN resolution.
- Manual payloads, exact duplicate constraints, advisory near matches, and work-URL edition picking.
- Cover download/validation/resize/cache and one-call create orchestration.

Acceptance:

- All external HTTP is mocked in normal tests.
- Independent timeout/failure behavior returns partial success.
- Search merging retains both source identities; Open Library work years never become edition years, and work URLs require edition choice.
- Add holds no DB write lock during network/image work; cover failure cannot roll back a valid entry and double-submit is idempotent.
- Existing entry returns a typed already-exists response; near edition only warns.

### [Sprint 006 — Add, detail, and metadata-edit UI](006-add-detail-edit-ui.md)

Scope:

- Search/manual picker and add form; entry detail; item metadata editor; cover upload; explicit refresh.
- Complete keyboard path and duplicate affordances.

Acceptance:

- Manual and provider-backed Playwright add flows pass.
- Existing duplicate navigates to detail with toast; near duplicate remains addable.
- Metadata edit survives a fill-empty sync test.
- Explicit refresh communicates overwrite, updates only fields present in a validated payload, preserves omitted fields, and leaves all old data on failure.

### [Sprint 007 — Goodreads import](007-goodreads-import.md)

Scope:

- Size-limited staging, CSV parser (including Goodreads Book Id provenance), durable normalized preview records, explicit ambiguity decisions, and transactional effect ledger.
- Goodreads status suggestions, shelf filtering, date conversion, provisional score conversion.
- Import UI tab with preview and actionable row errors.

Acceptance:

- Excel-armored/empty ISBNs, malformed dates, UTF-8 text, missing columns, repeated files, and zero ratings have fixtures.
- Preview changes no library entities, persists the exact commit plan, and exposes parse errors/ambiguities.
- Commit is idempotent; new rows land unsorted while existing entries and manual edits remain untouched.
- UI never uploads on commit a second time or exposes staged host paths.

### [Sprint 008 — Working book metadata and covers](008-book-metadata-covers.md)

Scope:

- Normalize Open Library edition/work/author data and optional same-ISBN Google Books fill-empty data.
- Type metadata patches, migrate legacy publishers, cache and serve versioned covers, and expose the edition/original-year distinction throughout the UI.

Acceptance:

- Provider and file-backed tests cover normalized metadata, identity-safe merging, patch clearing, refresh preservation, secure cover download/serving, and zero provider calls during rendering.
- Component/Chromium tests cover search, virtual rows, detail/edit/refresh, mobile, keyboard, and missing-cover states; the specified three-title live smoke proves cached offline rendering.

### [Sprint 009 — Calibre import and re-sync](009-calibre-import.md)

Scope:

- Path confinement, read-only Calibre connection, supported schema queries, and preview-time staging of normalized rows/cover preparation so commit never rereads a changed source.
- Shared matching/commit pipeline and Calibre UI tab.

Acceptance:

- Synthetic Calibre libraries cover authors, identifiers, tags, descriptions, series, ratings, and absent optional data.
- Symlink/path escapes are rejected.
- `mode=ro` plus `query_only` is tested; source DB hash is unchanged after import.
- Re-sync adds/fills only and native 1–10 scores are not provisional.

### Sprint 010 — Durable enrichment and safe undo

Scope:

- DB-backed job polling, leasing, retries, progress API, rate-limited enrichment.
- Import-effect reverse undo for created and fill-empty values, queued-job cancellation/late-result guards, UI progress, and undo window.

Acceptance:

- Queued/running jobs survive simulated restart and handlers tolerate replay.
- Provider rate and retry caps are clock-injected and deterministic.
- Undo cannot remove later user edits, shared items, or pre-existing entries; it reverts a field only if current value still matches the recorded imported value.
- Partial retention is reported, repeated undo is harmless, and late jobs from an undone batch cannot mutate data.

### Sprint 011 — Bulk-first triage

Scope:

- Virtualized dense table, filters/grouping, selection/range/select-all semantics.
- Bulk action bar, suggested-status acceptance, conflict expansion/resolution, keyboard rhythm.

Acceptance:

- Server-side select-all means all rows matching the current filter and uses exclusions; unloaded or hidden rows are mutated only when that contract explicitly includes them.
- `j/k`, status, score, shelf, commit/advance shortcuts work with input guards.
- A Playwright scenario imports and triages hundreds of rows without one request per row.
- Conflicting values remain visible until explicitly resolved.

### Sprint 012 — Scale, accessibility, and resilience

Scope:

- Query/index measurement including whether normalized text sorts need a stored projection, 10k-entry benchmark, accessibility audit and fixes.
- Error boundaries, degraded provider states, reduced motion, cancellation/race tests.
- Complete critical E2E regression suite and security limits.

Acceptance:

- Technical-spec latency/render budgets pass on documented hardware or deviations are approved.
- Automated axe checks and manual keyboard/focus checklist pass core screens.
- Upload/image/path/provider limits and log redaction tests pass.
- No uncaught frontend errors in E2E console.

### Sprint 013 — Container, backup, and v1 release

Scope:

- Multi-stage non-root image, production static SPA routing, Compose mounts/config, healthcheck.
- Alembic startup/deploy procedure, online backup script, host-scheduler example, retention/checksums/integrity check, restore documentation.
- Fresh-install and upgrade smoke tests; operator runbook and release notes.

Acceptance:

- Final image contains no Node runtime and runs as non-root.
- `/data` persists DB/covers across recreation; `/calibre` is read-only in mount and code.
- Backup/restore drill recovers representative scores, notes, shelves, and covers.
- LAN-only warning is prominent; no public exposure or auth is implied.
- Clean-machine Compose smoke test passes and tags the v1 release only when explicitly requested.

## Cross-sprint definition of done

Every sprint must:

- satisfy every acceptance criterion or remain incomplete;
- add tests at the correct layer and run focused plus regression suites;
- preserve data and security invariants;
- update OpenAPI/types/docs when contracts move;
- record material deviations in `docs/decisions.md`;
- review downstream sprint impact;
- pass `python scripts/validate_project.py`, `make check`, and `make test` when available;
- end with a clean worktree and an updated next-agent handoff.
