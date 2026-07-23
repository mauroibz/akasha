# Sprint 014 — Scale, accessibility, and resilience

**Status:** planned
**Depends on:** 013
**Roadmap revision:** 5

## Objective

Ensure the application meets performance budgets, passes accessibility audits,
handles errors gracefully, and has comprehensive E2E regression coverage.

## Required context

1. `AGENTS.md`
2. `docs/specs/product-spec.md` section 6 (non-functional requirements)
3. `docs/specs/technical-spec.md` section 12 (performance budgets) and section 13 (accessibility)
4. `docs/decisions.md` DEC-002, DEC-018, DEC-019, and DEC-022
5. Sprint 013 Outcome and `docs/agent/WORKFLOW.md`
6. Existing `frontend/src/` test infrastructure and `frontend/e2e/` test suite

## Current implementation baseline

After Sprint 012, the application has a bulk-first triage page with server-side
select-all, keyboard shortcuts, and 27 passing e2e tests. Sprint 013 is scheduled
to repair the reported library grid overlap and add responsive spatial regression
coverage. Performance has not been measured against documented budgets, and no
automated accessibility checks exist.

## Deliverables

- Query/index measurement with 10k-entry benchmark; stored projection for normalized text sorts if needed.
- Automated axe accessibility checks on core screens.
- Error boundaries, degraded provider states, reduced-motion support, cancellation/race tests.
- Complete critical E2E regression suite, including the Sprint 013 grid coverage.
- Security limits: upload/image/path/provider limits, log redaction.

## Acceptance criteria

1. Technical-spec latency/render budgets pass on documented hardware or deviations are approved.
2. Automated axe checks and manual keyboard/focus checklist pass core screens.
3. Upload/image/path/provider limits and log redaction tests pass.
4. No uncaught frontend errors in E2E console.

## Required tests (TDD)

- Performance: 10k-entry benchmark script with documented results.
- Accessibility: axe automated checks on library, triage, detail, import, add pages.
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

- No container, backup, or release work (Sprint 015).

## Commit checkpoints

1. `perf: add 10k-entry benchmark and index measurement`
2. `feat: add automated axe accessibility checks`
3. `feat: add error boundaries and degraded provider states`
4. `test: add security limit and log redaction tests`
5. `test: complete critical E2E regression suite`
6. final `docs(sprint-014): close sprint and hand off`

## Risks and decisions to surface

- Whether normalized text sorts need a stored projection column.
- axe integration: CI vs local-only.
- Reduced-motion implementation: CSS vs JS-driven.

## Outcome

_Not started. On completion record delivered behavior, commands and actual results, commit IDs,
deviations/decisions, and impact on every future sprint._
