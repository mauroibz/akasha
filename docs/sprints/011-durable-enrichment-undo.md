# Sprint 011 — Durable enrichment and safe undo

**Status:** in_progress
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

_Not started. On completion record delivered behavior, commands and actual results, commit IDs,
deviations/decisions, and impact on every future sprint._
