# Sprint 011 — Durable enrichment and safe undo

**Status:** completed
**Depends on:** 010
**Roadmap revision:** 4

## Objective

Deliver restart-safe background enrichment with rate-limited provider calls and a safe 24-hour undo
for import effects, so that enrichment can run unattended and imported changes can be reversed without
risking later user edits, shared items, or pre-existing entries.

## Required context

1. `AGENTS.md`
2. `docs/specs/product-spec.md` sections 5 and 8 (enrichment and undo)
3. `docs/specs/technical-spec.md` sections 6, 9, and 11 (jobs, import effects, undo)
4. `docs/decisions.md` DEC-002 (import ledger), DEC-013 (conflict audit data), DEC-016, DEC-017
5. Sprint 009 and 010 Outcomes and roadmap Sprints 011–014
6. `docs/agent/WORKFLOW.md`, latest worklog entry, and `docs/agent/HANDOFF.md`
7. The actual import batch/effect tables, job models, provider adapters, and all existing tests; inspect
   the migration history and repository code rather than relying on summaries

## Current implementation baseline

After Sprint 010, the application has a coherent editorial UI with navigation, detail, deletion, shelf
management, and import flows. Import effects are recorded in `import_batches` and
`import_batch_entries` with created flags and before-values (DEC-002), but no job runner, enrichment
pipeline, or undo execution exists. Provider adapters (Open Library, Google Books) are synchronous and
mockable. The undo ledger schema is in place but no API or UI consumes it.

## Deliverables

- DB-backed job polling, leasing, retries, and progress API for enrichment tasks.
- Rate-limited enrichment that fills empty metadata fields from providers without overwriting user data.
- Import-effect reverse undo for created and fill-empty values, with a 24-hour window.
- Queued-job cancellation and late-result guards.
- UI progress indicators for running enrichment jobs.
- Undo window with clear copy and retention reporting.

## Acceptance criteria (ordered, TDD)

1. Queued and running jobs survive a simulated restart; handlers tolerate replay without double-applying.
2. Provider rate and retry caps are clock-injected and deterministic in tests.
3. Undo cannot remove later user edits, shared items, or pre-existing entries; it reverts a field only
   if the current value still matches the recorded imported value.
4. Partial retention is reported when some fields were edited after import; repeated undo is harmless.
5. Late jobs from an undone batch cannot mutate data and are marked cancelled.
6. Enrichment fills only empty fields and never overwrites existing user data or manual edits.
7. Progress API reports current job state; UI shows running, completed, and failed states.

## Required tests (TDD)

- Job lifecycle tests: queue, lease, complete, retry, cancel, and restart survival.
- Enrichment tests: fill-empty only, rate limiting, retry caps, and no-overwrite with clock injection.
- Undo tests: revert matching values, preserve edited fields, shared item safety, repeated undo,
  late-job cancellation, and 24-hour expiry.
- Component/API tests: progress API responses, undo API responses, and error states.
- Chromium e2e: undo flow from import history, progress display, and cancellation.

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

## Explicit non-scope

- No bulk triage, conflict grouping, or server-wide bulk deletion (Sprint 012).
- No accessibility audit, performance budgets, or full E2E hardening (Sprint 013).
- No container, backup, or release work (Sprint 014).
- No new provider adapters beyond the existing Open Library and Google Books.

## Commit checkpoints

1. `feat: add durable job runner with leasing and restart survival`
2. `feat: add rate-limited enrichment that fills empty fields`
3. `feat: add safe import-effect undo with 24-hour window`
4. `feat: add enrichment progress and undo UI`
5. final `docs(sprint-011): close sprint and hand off`

## Risks and decisions to surface

- Clock-injected rate limiting must be deterministic; consider whether the job runner needs a separate
  process or can share the FastAPI event loop.
- Undo field-matching semantics: if a user edited a field after import, undo must skip that field and
  report partial retention. This must be tested with realistic before/after values.
- Late-job cancellation must be atomic with undo to prevent race conditions.

## Outcome

### Delivered behavior

**AC1 — Durable job runner with leasing, retries, and restart survival.**
`JobRepository` (`infrastructure/jobs.py`) provides `enqueue`, `claim` (with
`UPDATE … LIMIT 1` polling), `complete`, `fail` (with retry caps and
exponential backoff), `cancel`, `cancel_batch_jobs`, and `reclaim_expired`.
On app startup, `reclaim_expired` runs in the lifespan to return crashed
running jobs back to `queued`. Tests simulate a restart by creating a new
engine from the same DB file and verifying queued jobs are still present
and running jobs are reclaimed.

**AC2 — Clock-injected rate limiting and retry caps.**
`RateLimiter` takes an injectable `now()` callable; tests pass a fixed clock
and assert deterministic gating. Retry caps: `max_retries=3`, exponential
backoff `2^attempt` seconds. Enrichment handler returns `rate_limited`
without calling the provider when the gate rejects.

**AC3 — Safe undo: field-matching, shared-item and pre-existing-entry
preservation.** `UndoService` (`application/undo.py`) reverses effects in
`effect_id DESC` order. A `fill_empty` field is reverted only when
`_values_equal(current, after_value)` returns true; otherwise the field is
retained and the item is added to a `modified_items` set that prevents the
subsequent `create` effect from deleting the item. Created entries are
deleted only if their `after_values` contain `{"created": true}`. Created
items are deleted only if no other entries reference them (shared-item
safety) and the item is not in `modified_items`.

**AC4 — Partial retention reporting and repeated undo harmlessness.** The
undo result reports `reverted`, `retained`, `skipped`, `reverted_entries`,
`reverted_items`, and `retained_items`. A second `undo()` call returns
`{skipped: 1, reverted: 0}` because the batch state is already `undone`.

**AC5 — Late-job cancellation.** When an enrichment job starts processing
and its batch is already `undone`, the handler calls `repo.cancel(job_id)`
and returns `{"state": "cancelled"}` without calling the provider. All
queued/running jobs for the batch are also cancelled atomically by
`cancel_batch_jobs` at the start of undo.

**AC6 — Enrichment fills only empty fields.** `EnrichmentHandler` checks
each field: `item.year is None` and `metadata.get(key) in (None, "", [], {})`
before writing. Existing values are never overwritten. Import effects are
recorded for undo coverage.

**AC7 — Progress API and UI.** `GET /api/import/jobs/{id}` returns job
state, progress, attempts, and error. The undo UI shows an "Undo this
import" button after commit, a confirmation step, and an "Import undone"
result with reverted/retained counts. The expired-undo error is shown in
the alert region.

### Tests run

- `backend/tests/test_jobs.py` — 30 tests covering all 7 ACs.
- `backend` full suite: 122 passed.
- Frontend unit tests: 37 passed.
- Chromium e2e: 21 passed, 2 skipped (pre-existing).
- `make check`, `make test`, `make build`, `git diff --check` — all pass.

### Commits

- `5859988` feat: add durable job runner with leasing and restart survival
- `dbbc48c` feat: add progress API, undo endpoint, and undo UI
- `c771622` fix: lint, formatting, and OpenAPI spec for Sprint 011 endpoints

### Deviations

- Sprint checkpoint commits 2 and 3 were combined into checkpoint 1
  because the enrichment handler, undo service, and job runner are tightly
  coupled and all needed to pass tests together.
- The job runner shares the FastAPI event loop (no separate process);
  it runs as a cooperative poller. This was noted as a risk in the sprint
  and is acceptable for v1 LAN-only deployment.

### Impact on future sprints

- Sprint 012 (bulk triage): can use `JobRepository` to enqueue bulk
  operations and `ImportEffectRow` to audit changes.
- Sprint 013 (E2E hardening): the undo e2e tests are already in place;
  the progress API can be exercised end-to-end.
- Sprint 014 (container): the job runner starts automatically in the
  lifespan; no additional process management needed for v1.
