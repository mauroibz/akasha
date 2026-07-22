# Agent handoff

**State:** Sprint 004 completed; Sprint 005 is ready and unclaimed.
**Active sprint:** [`005-providers-add-api.md`](../sprints/005-providers-add-api.md)
**Worktree expectation:** clean after the Sprint 004 closure commit.

## Current reality

- `/` is a typed, dark-first, keyboard-accessible library with server filters/facets/sorts,
  debounced search, opaque-cursor infinite queries, and persisted virtual grid/table views.
- Optimistic score/status edits snapshot and roll back query data with an assertive announcement;
  active score sorts reload from page one and entry-ID focus is restored.
- A shared editable-target guard protects `/`, `a`, navigation, and score shortcuts. Reduced-motion
  CSS and deterministic 5,000-entry Chromium checks are in place.
- Frontend library types are checked against `frontend/openapi.json` during `make check`.
- Sprint 005 owns provider models/adapters, edition-safe resolution, one-call cached creation, and
  the non-fatal bounded cover pipeline. The `/add` UI itself remains Sprint 006 scope.

## First action

Follow `AGENTS.md`, claim Sprint 005, inspect its named domain/repository/API code and tests, and
start with failing provider candidate merge/rank and independent provider-timeout tests.

## Known blockers

None. Isolated `uv build` may require network access to resolve hatchling when its build cache is
cold; the approved `make build` path passed during Sprint 004.
