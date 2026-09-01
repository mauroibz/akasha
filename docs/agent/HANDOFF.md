# Handoff — Sprint 059 is closed; a real e2e bug is next, then Sprint 060

Sprint 059 (nothing blocks the event loop) is **completed**. Phase A measured a real ~10x
budget breach in the import-commit path under a 2-CPU constraint; Phase B fixed exactly that
path with one offload seam (`infrastructure/offload.py`'s `off_loop`) and closed the new
cross-thread SQLite contention risk it introduced. Full account, numbers and commit IDs in the
sprint's own Outcome and `docs/decisions.md` DEC-122.

## What to do right now

**Fix the Calibre folder-picker e2e failure before touching Sprint 060.** This was found while
closing Sprint 058 (the user asked about a failing CI run) and confirmed real and reproducible —
not the transient runner-contention flakiness the earlier e2e fix addressed:

- 3 tests in `frontend/e2e/import.spec.ts` fail consistently: the ones that choose a Calibre
  folder via the browser's native folder picker (`webkitdirectory`).
- The concrete symptom (from a clean rerun, well after any runner contention had cleared): the
  "Preview Calibre library" button stays `disabled` for the full 60s test timeout after a folder
  is chosen. `readyInput()` gating that button is pure synchronous client state
  (`bundle.members.length` in `frontend/src/pages/ImportPage.tsx`) — no network call is involved,
  so this is not a slow request, it is the state never getting set.
- Confirmed unrelated to anything pushed this session: an independent Dependabot PR run (a
  `docker/login-action` version bump, touching nothing in `frontend/`) showed the identical 3
  failures in the same time window.
- Leading hypothesis, not yet confirmed: Chromium/`webkitdirectory` behavior drift on GitHub's
  hosted runners, since this is the first real e2e run against `main` since 2026-08-21 and
  nothing in the 25 commits that just landed touches Calibre import code.
- Start by reproducing locally if possible (may require CI's exact Chromium build —
  `npx playwright install chromium` at whatever version `package-lock.json` pins), then trace
  what sets `bundle` in `ImportPage.tsx` after `setInputFiles` on a `webkitdirectory` input.
- The user authorized this as an out-of-sprint repair, same pattern as the earlier e2e CI
  flakiness fix (see that worklog entry for the precedent). Record the diagnosis and fix in the
  worklog the same way.

**Then execute Sprint 060** — read `docs/sprints/060-storage-housekeeping.md`. It ships as
**v1.5.6**, not v1.5.5 (DEC-121 renumbered it). `docs/agent/state.json` already points at it.

## What Sprint 059 built, concretely

- `scripts/measure_event_loop.py`/`.sh` — the event-loop-contention harness, now referenced from
  `docs/agent/TESTING.md`.
- `backend/src/book_tracker/infrastructure/offload.py` — the one seam (`off_loop`,
  `CapacityLimiter(4)`).
- `api/imports.py`'s `commit` handler now runs through `off_loop`; `main.py` gained an
  `OperationalError` -> typed `library_busy` 503 handler.
- `backend/tests/test_event_loop_offload.py` — four tests proving the threading contract, the
  fix's effect, concurrency safety and the busy-timeout error path.
- `docs/operations/release-notes-v1.5.5.md`, listed in `docs/README.md`.

## Verified at this session's close

Full gate (Phase B touched `backend/src/`): `python scripts/validate_project.py`, `make check`,
`make test` (1,190 backend + 194 frontend), `make smoke-container` all green.
`bash scripts/measure_event_loop.sh 2 import covers attachment` — all three scenarios within
budget post-fix. A real browser walkthrough committed a 4,000-row import while confirming the UI
stayed responsive mid-commit.

## Private data and operational constraints

Unchanged. `exports/` is the owner's private source archive, gitignored whole, read-only
walkthrough input. Secrets, databases, uploaded imports and covers are never committed. v1 has
no auth and stays LAN-only; Calibre is opened read-only. The owner authorized autonomous work
through the Calibre e2e fix and into Sprint 060, including pushing commits as each stage closes
— that authorization does not extend to force-pushes, history rewrites, or anything outside the
normal sprint-closure pattern already used this session (commit, then push `main`, no tags
unless a sprint's own release step calls for one).
