# Sprint 017 — Scale, accessibility, and resilience

**Status:** ready
**Depends on:** 016
**Roadmap revision:** 7

## Objective

Ensure the application meets performance budgets, passes accessibility audits,
handles errors gracefully, and has comprehensive E2E regression coverage.

## Required context

1. `AGENTS.md`
2. `docs/specs/product-spec.md` section 6 (non-functional requirements)
3. `docs/specs/technical-spec.md` section 12 (performance budgets) and section 13 (accessibility)
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

_Not started. On completion record delivered behavior, commands and actual results, commit IDs,
deviations/decisions, and impact on every future sprint._
