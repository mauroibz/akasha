# Sprint 017 — Scale, accessibility, and resilience

**Status:** completed
**Depends on:** 016
**Roadmap revision:** 7

## Objective

Ensure the application meets performance budgets, passes accessibility audits,
handles errors gracefully, and has comprehensive E2E regression coverage.

## Required context

1. `AGENTS.md`
2. `docs/specs/product-spec.md` section 7 (UI, including "Rendering at scale")
3. `docs/specs/technical-spec.md` section 1 (target budgets), section 8 (frontend behavior and
   accessibility), section 9 (security and data safety), and section 10 (testing and quality
   gates). The original plan cited "section 12 (performance budgets) and section 13
   (accessibility)"; neither exists — the spec has twelve sections and section 12 is *Deferred
   decisions*.
4. `docs/decisions.md` DEC-002, DEC-018, DEC-019, DEC-022, DEC-023, DEC-024, and DEC-030 through DEC-034 (the Sprint 016 motion layer, including why `layout` animations are inert application-wide)
5. Sprint 016 Outcome and `docs/agent/WORKFLOW.md`
6. Existing `frontend/src/` test infrastructure and `frontend/e2e/` test suite

## Current implementation baseline

Re-derive this section at activation; the figures below predate Sprints 014–016 and must be
measured again rather than copied.

As of Sprint 013 the Chromium e2e suite was 33 passing plus 2 pre-existing skips, and
`frontend/e2e/library.spec.ts` carried responsive spatial regressions at 375/768/1440 with an
expanded-score-picker containment check. The library grid virtualizes rows of cards (DEC-023):
the mounted-DOM budget is two bounds — mounted virtual rows under 20 and mounted cards under 48
— and both are already asserted. Performance has not been measured against documented budgets,
and no automated accessibility checks exist.

Sprints 014–016 changed the surface this sprint audits. Sprint 015 replaced every control with a
shadcn primitive and rewrote several e2e selectors, so the suite size and the mounted-DOM margins
differ. Sprint 016 added Motion, so reduced-motion assertions are no longer vacuous and bundle
size grew. Accessibility work here runs against real Radix primitives, which changes what axe
reports.

## Deliverables

- Query/index measurement with 10k-entry benchmark; stored projection for normalized text sorts if needed.
- Automated axe accessibility checks on core screens.
- Error boundaries, degraded provider states, reduced-motion support, cancellation/race tests.
  The provider-state data source exists (`GET /api/health/providers`) and Sprint 015 renders it;
  what remains here is behavior under failure, not the indicator itself.
- Benchmarks must account for the background job runner, which Sprint 014 started driving in the
  application lifespan (DEC-027). A 10k-entry import now enqueues real enrichment work that
  competes for the SQLite write lock; measure with the queue draining, not idle.
- Complete critical E2E regression suite, extending rather than replacing the Sprint 013 grid coverage.
- Security limits: upload/image/path/provider limits, log redaction.

## Acceptance criteria

1. Technical-spec latency/render budgets pass on documented hardware or deviations are approved.
2. Automated axe checks and manual keyboard/focus checklist pass core screens.
3. Upload/image/path/provider limits and log redaction tests pass.
4. No uncaught frontend errors in E2E console.

## Required tests (TDD)

- Performance: 10k-entry benchmark script with documented results, measured against both mounted-DOM
  bounds from DEC-023 (rows and cards) rather than a single row count.
- Accessibility: axe automated checks on library, triage, detail, import, add pages, including grid
  mode with an expanded score-picker overlay open.
- Resilience: error boundary renders fallback, provider degradation shows message, cancellation is clean.
- Security: upload size limits, path traversal blocked, provider rate limits, log redaction.

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

- No container, backup, or release work (Sprint 018).

## Commit checkpoints

1. `perf: add 10k-entry benchmark and index measurement`
2. `feat: add automated axe accessibility checks`
3. `feat: add error boundaries and degraded provider states`
4. `test: add security limit and log redaction tests`
5. `test: complete critical E2E regression suite`
6. final `docs(sprint-017): close sprint and hand off`

## Risks and decisions to surface

- Whether normalized text sorts need a stored projection column.
- axe integration: CI vs local-only.
- Reduced-motion implementation: CSS vs JS-driven.
- The compact score picker is an overlay inside a fixed-height card (DEC-023); accessibility work on
  it must not restore in-flow expansion, which is the defect Sprint 013 repaired.

## Outcome

Completed 2026-08-12. Nine implementation commits plus this closure.

### AC1 — latency and render budgets

`scripts/benchmark_library.py` (new) seeds 10,000 entries into a migrated file-backed SQLite
database and times `list_entries` for every sort key in both directions, first page and page 26,
with and without a text filter, **twice**: idle, and with a thread draining the job queue through
the real `JobRepository` so every sample competes for the write lock (DEC-027). Query plans print
alongside the numbers.

It failed on first run, and decisively. Ordering by `normalize_text(title)` invokes a Python
function once per candidate row:

| scenario (contended p95) | before | after |
|---|---|---|
| first page, `title` | 312 ms | 82 ms |
| first page, `sort_author` | 412 ms | 85 ms |
| page 26, `sort_author` | 627 ms | 78 ms |
| text filter `q=garcia` | 988 ms | 10 ms |

Budget is 500 ms (technical spec section 1), on a workstation faster than the target ZimaBoard.
DEC-036 stores the projection: `items.title_normalized` and `items.sort_author_normalized`
(migration `0007`), maintained by a mapper event so no write path can forget them, read by
ordering, filtering and the cursor alike. **No index accompanies them, and that is measured**: the
query drives from `entries` and reaches `items` by rowid, so SQLite builds a temp B-tree either
way, verified with and without the null-bucket CASE. Every scenario is now inside budget; the
dead `normalize_text` UDF registration is gone.

Bundle: DEC-037 splits the five non-landing routes and chunks vendor code by change rate. Eager
JavaScript **696.24 kB → 511.55 kB** across four chunks, largest chunk 193.67 kB, no chunk-size
warning; `chunkSizeWarningLimit` lowered to 300 kB as the regression guard. The 104 kB form stack
no longer loads for someone who only browses.

DEC-023 bounds re-asserted at 10,000 entries rather than 5,000, and in table mode for the first
time: **grid 7 rows / 28 cards, table 15 / 15**, against bounds of 20 and 48. Printed on every run.

### AC2 — accessibility

`e2e/accessibility.spec.ts` (new) runs `@axe-core/playwright` over twelve states in the existing
CI Playwright job: library grid, library compact, the score-picker overlay expanded inside its
card, triage, triage with a selection, detail, the opinion dialog, add, the manual form, the
degraded-provider notice, import, and shelves. Zero `serious`/`critical` violations under WCAG
2.0/2.1 A and AA; lesser impacts print rather than fail, and there are currently none of those
either.

Seven failed on first run and three were real defects (DEC-038): both list surfaces claimed
`role="table"` over rows containing no cells; the cover placeholder carried `aria-label` on a bare
`div` where ARIA ignores it; and the import page rendered tab triggers with no panels, so every
`aria-controls` pointed at nothing. Both lists are now feeds of articles carrying
`aria-posinset`/`aria-setsize`. The keyboard and focus half was walked by hand — see the worklog.

### AC3 — security limits and log redaction

`tests/test_security_limits.py` (new) covers what nothing covered: static-path containment,
provider timeout, and redaction. The rest of technical spec section 9 was already implemented and
tested next to its own code and is listed in that file's docstring rather than re-asserted.

Log redaction did not exist. `logging.py` configured structlog with a JSON renderer nothing used,
while every call site went through the standard library under a `%(message)s` format that dropped
`extra` entirely. Both halves are fixed: stdlib records route through the same chain, and a
processor removes a denylist of keys, scrubs configured secrets out of any string, truncates
oversized values under innocent keys, and recurses into nested structures.

The traversal test uses percent-encoded paths only. httpx collapses a literal `/../secret.txt`
before sending it, so the obvious form of that assertion proves the client normalizes and nothing
about the server — verified by probe.

### AC4 — no uncaught frontend errors

`e2e/console.ts` fails any test whose page logged `console.error` or threw, as an auto fixture
across all nine specs, with an annotation to opt out. Verified by probe that it bites and that the
opt-out works. Zero errors across the suite, and zero during the walkthrough.

### Commands

| command | result |
|---|---|
| `python scripts/validate_project.py` | passed |
| `make format` | clean |
| `make check` | passed (lint, typecheck, OpenAPI, validator) |
| `make test` | backend **164** (was 154), frontend **74** (was 68) |
| `npm run test:e2e -- --project=chromium` | **73 passed / 2 skipped** (was 53 / 2) |
| `make build` | succeeded, no chunk-size warning |
| `git diff --check` | clean |

The 2 skips remain `live-metadata.spec.ts`, which needs `LIVE_METADATA_MODE` and a live backend.

### Commits

`76253e8` benchmark and projection · `65d072f` code split · `513e0dc` 10k bounds · `9d67bbb` axe
and its repairs · `7f699bb` error boundaries, cancellation, two labels · `addea8a` security limits
and redaction · `1ac6e65` import order · `80c9c43` console guard and coverage gaps · `b172366`
walkthrough fixes.

### Deviations and decisions

- **DEC-036** supersedes DEC-015's deferral of a stored projection.
- **DEC-037** bundle split, with the warning limit lowered rather than raised.
- **DEC-038** both list surfaces become feeds of articles.
- Two prerequisite repairs: `configure_logging` replaced every root handler, which removed
  pytest's `caplog` and broke an unrelated provider-health test; and the error boundary never
  reset, so a caught error stayed pinned over every later route.
- Two defects beyond the two the roadmap named were found in the walkthrough and fixed: the
  library score control marked a provisional score with a dot and a dashed border that nothing
  explained (the same defect as the triage cell, on a surface nobody had listed), and a book with
  no year rendered a bare "unknown".
- **Not done, and deliberately:** product spec section 7 lists `s` as a triage shortcut opening
  shelf autocomplete. It is not implemented, and adding a keyboard shortcut is feature work, not
  hardening. Recorded for a later sprint rather than smuggled in here.
- This sprint's own `Required context` cited two technical-spec sections that do not exist; the
  references were corrected.
