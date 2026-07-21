# Agent handoff

**State:** repository planning baseline complete; Sprint 001 is ready and unclaimed.
**Active sprint:** [`001-foundation.md`](../sprints/001-foundation.md)
**Worktree expectation:** clean after baseline commit.

## Current reality

- The repository contains canonical product and technical specifications, an ordered 12-sprint roadmap, and the autonomous execution protocol.
- There is intentionally no backend/frontend application code yet.
- `python scripts/validate_project.py` is the only current executable validation command.
- Sprint 001 must create the package/toolchain/container foundation and turn the aspirational `make` commands into working commands.

## First action

Follow `/AGENTS.md`, claim Sprint 001, and implement only that sprint. Verify Docker availability before assuming the sprint can close because its container smoke test is mandatory.

## Known blockers

None. The four unresolved product questions have authorized defaults in technical spec section 12.
