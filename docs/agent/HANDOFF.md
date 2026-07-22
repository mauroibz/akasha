# Agent handoff

**State:** Sprint 005 completed; Sprint 006 is ready and unclaimed.
**Active sprint:** [`006-add-detail-edit-ui.md`](../sprints/006-add-detail-edit-ui.md)
**Worktree expectation:** clean after the Sprint 005 closure commit.

## Current reality

- Provider search fans out with independent limits, retains merged identities, and supports bare
  ISBN plus Open Library book/work and Google Books URL resolution through typed APIs.
- `POST /api/entries` refetches selected metadata, validates secondary identities, prepares covers
  outside its short write transaction, and returns new/existing entries plus advisory near matches.
- Cached entries render without provider access. Covers are bounded, normalized, atomically
  installed after commit, and non-fatal with temporary-file cleanup.
- The frontend library remains complete from Sprint 004, but `/add` is still a placeholder. Sprint
  006 owns the add/detail/edit UI and the missing cover-upload/explicit-refresh backend contracts.
- Frontend library types remain checked against the regenerated `frontend/openapi.json`.

## First action

Follow `AGENTS.md`, claim Sprint 006, inspect its named frontend/backend paths and tests, and begin
with failing typed add-page tests for provider/manual/loading/error/duplicate/near-match states.

## Known blockers

None. Isolated `uv build` may need approved network access for Hatchling when its cache is cold.
