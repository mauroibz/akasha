# Agent handoff

**State:** Sprint 007 completed; Sprint 008 is ready and unclaimed.
**Active sprint:** [`008-calibre-import.md`](../sprints/008-calibre-import.md)
**Worktree expectation:** clean after the Sprint 007 closure commit.

## Current reality

- `/import` provides a bounded Goodreads upload, durable normalized preview, row errors, explicit
  ambiguity choices, and atomic idempotent commit using only the recorded batch plan.
- New Goodreads entries are `unsorted`; status is suggested, nonzero ratings are doubled and marked
  provisional, and shelves remain filterable. Existing personal and populated metadata are preserved.
- Ordered effects are recorded for Sprint 009, but enrichment and undo execution are not implemented.
- OpenAPI and typed frontend clients include import contracts; 82 backend, 15 component, and eight
  Chromium tests pass. No Calibre reader, routes, cover staging, or UI tab exists yet.

## First action

Follow `AGENTS.md`, claim Sprint 008, build synthetic Calibre databases, and begin with failing
path-confinement/read-only/query-only adapter tests plus before/after source hash evidence.

## Known blockers

None. Isolated `uv build` may need approved network access for Hatchling when its cache is cold.
