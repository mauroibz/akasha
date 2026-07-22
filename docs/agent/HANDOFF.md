# Agent handoff

**State:** Sprint 006 completed; Sprint 007 is ready and unclaimed.
**Active sprint:** [`007-goodreads-import.md`](../sprints/007-goodreads-import.md)
**Worktree expectation:** clean after the Sprint 006 closure commit.

## Current reality

- `/add` supports debounced provider search, ISBN/URL resolution, Open Library work-edition choice,
  manual fallback, shelves/opinion fields, exact duplicate navigation, and confirmed near matches.
- `/books/{entry_id}` is cached-only and edits opinion/shared metadata; provider failure cannot affect
  ordinary rendering. Confirmed refresh merges present provider metadata and preserves opinion data.
- Cover upload is bounded to JPEG/PNG/WebP byte/pixel limits, normalized to a local 600px JPEG, and
  retains the previous valid cover on invalid input or installation failure.
- OpenAPI and typed frontend clients include these contracts. Full unit and Chromium suites pass.
- No import schema, parser, preview/commit service, or import UI exists yet.

## First action

Follow `AGENTS.md`, claim Sprint 007, inspect its named persistence/API/frontend paths, and begin with
failing migration/parser fixtures for the complete Goodreads edge-case matrix.

## Known blockers

None. Isolated `uv build` may need approved network access for Hatchling when its cache is cold.
