# Agent handoff

**State:** Sprint 008 completed; Sprint 009 is ready and unclaimed.
**Active sprint:** [`009-calibre-import.md`](../sprints/009-calibre-import.md)
**Worktree expectation:** clean after the Sprint 007 closure commit.

## Current reality

- `/import` provides a bounded Goodreads upload, durable normalized preview, row errors, explicit
  ambiguity choices, and atomic idempotent commit using only the recorded batch plan.
- New Goodreads entries are `unsorted`; status is suggested, nonzero ratings are doubled and marked
  provisional, and shelves remain filterable. Existing personal and populated metadata are preserved.
- Ordered effects are recorded for Sprint 011, but enrichment and undo execution are not implemented.
- Open Library now resolves nested editions plus work/author metadata, Google Books fills missing
  same-ISBN fields when configured, and all standard metadata is typed/editable/preserved.
- Covers are securely cached and served through versioned API URLs. The required three-title live
  smoke passed with 2012/2015/2005 editions and offline rendering after restart.
- OpenAPI and typed frontend clients include metadata/cover contracts; 85 backend, 15 component,
  eight normal Chromium, and two opt-in live/offline flows pass. No Calibre reader/routes/UI exists.

## First action

Claim Sprint 009 and begin with synthetic Calibre schema fixtures plus confined read-only/query-only
adapter tests and before/after source database hash evidence.

## Known blockers

None. Isolated `uv build` may need approved network access for Hatchling when its cache is cold.
