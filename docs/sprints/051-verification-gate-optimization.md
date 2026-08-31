# Sprint 051 — The verification gates get faster

**Status:** in_progress
**Depends on:** 050
**Roadmap revision:** 28

## Objective

Implement the four items in `docs/agent/TESTING.md`'s *Optimization backlog* so the remaining
roadmap (Sprints 052–054, each of which pays the full gate at least once) runs against cheaper,
more readable gates. When the sprint closes, the backlog section is removed from TESTING.md
because nothing is left in it.

No application behavior changes. Every acceptance criterion is a gate property — duration,
output readability, a new tracked command, or a bound where none existed.

## Required context

- `docs/agent/TESTING.md` in full — the backlog this sprint empties, and the cadence the changes
  must keep serving.
- `frontend/playwright.config.ts` and `frontend/e2e/library.spec.ts` — the one-worker cause.
- `frontend/src/test/setup.ts` and `frontend/vite.config.ts` — the Vitest harness.
- `scripts/walkthrough_series.py` and `scripts/walkthrough_series_050.py` — the two existing
  walkthrough runners the launcher generalizes.
- `backend/pyproject.toml` (`[tool.pytest.ini_options]`) — no timeout plugin exists today.
- `Makefile` — the `test`/`check` gates whose shape must not change for callers.

## Current implementation baseline

Measured 2026-08-31 on this workstation, against the Sprint 050 tree:

- **Playwright runs the whole suite at one worker.** `playwright.config.ts` sets
  `fullyParallel: false` and configures no `workers`; a full run is **106 passed, 2 skipped in
  49.4 s**. TESTING.md records that two `library.spec.ts` invariants are load-sensitive — the
  10,000-entry DOM-budget checks at `library.spec.ts:75` and `:125`.
- **Vitest is green but noisy.** 190 tests pass in 23.3 s, but the run prints **21 copies** of
  `Query data cannot be undefined … Affected query key: ["attachments",3]` from
  `DetailPage.test.tsx`, whose fetch mocks answer `{"attachments":[]}` for some tests and leave
  the query function returning `undefined` in others. The scrollTo half of backlog item 2 is
  **already done** (`src/test/setup.ts:30` replaces jsdom's throwing stub, with the comment
  explaining why) — what remains is the attachment-query fixtures and any Radix/motion
  `act(...)` warnings still in the output.
- **The realistic-data walkthrough is per-sprint folklore.** Two runners exist
  (`scripts/walkthrough_series.py`, `scripts/walkthrough_series_050.py`), each hand-rolled:
  they create their own temporary data dir, drive the lifespan themselves, and hardcode their
  sprint's flow. TESTING.md's *Walkthrough reuse* section asks for a tracked, sanitized
  launcher that creates the temporary data directory, starts and stops the backend, and takes
  the library path in one command.
- **No test has a timeout.** `backend/pyproject.toml` has no `pytest-timeout` and no
  `timeout` addopt; `frontend/vite.config.ts` sets no `testTimeout`; `playwright.config.ts`
  sets no `timeout`. TESTING.md's triage section exists precisely because a deadlock currently
  looks like slow work (the Sprint 035 futex/ep_poll stall ran for minutes before diagnosis).

## Deliverables

### 1. Playwright: a parallel ordinary project and a serial heavy-library project

Backlog item 1, verbatim: *"Split Playwright into a parallel ordinary project and a serial
heavy-library project. Today the whole suite uses one worker because two `library.spec.ts`
invariants are load-sensitive."*

Shape: the two 10,000-entry DOM-budget tests (`library.spec.ts:75`, `:125`) move into — or are
selected into — a `heavy-library` project that runs with `workers: 1`; everything else runs
parallel (worker count at Playwright's default or an explicit measured choice). The
`production-bundle` project's serial preview-server constraint is untouched. The split is by
project `testMatch`/`testIgnore` or by a title grep, whichever is smaller; the two load-sensitive
tests must be named in the config with the reason, so the next load-sensitive test knows where
it goes.

Measure before and after on the same machine and record both numbers in the Outcome. The
acceptance is a real speedup, not a theoretical one; if parallelization does not materially
help (the suite is 49 s and boot-dominated), record the measurement and take the smaller win
of making the split explicit.

### 2. Vitest: green output is readable

Backlog item 2, verbatim: *"Remove known Vitest harness noise: provide a deliberate
`window.scrollTo` test shim, return defined attachment-query fixtures, and await Radix/motion
state updates correctly. Preserve real console failures while making green output readable."*

The scrollTo shim already exists and needs no work. What remains:

- Every fetch mock answering an attachments query returns a defined value, so the 21
  `Query data cannot be undefined` warnings on `["attachments",3]` are gone. The fix belongs in
  the shared mock/fetch-helper the tests use, not in 21 individual assertions.
- Any remaining `act(...)` warnings from Radix/motion state updates are awaited properly.
- A green `npm test` prints no harness noise; real console failures must still fail or print —
  do not blanket-suppress `console.error`.

### 3. A tracked, sanitized walkthrough launcher

Backlog item 3, verbatim: *"Promote the local realistic-data flow to a tracked, sanitized
launcher that creates a temporary data directory, starts and stops the backend, and accepts
the library path in one command."*

Generalize what `scripts/walkthrough_series.py` already does by hand into one tracked script —
`scripts/walkthrough.py` — that:

- creates a fresh temporary application data directory per run and cleans it up (or names it
  for inspection on failure);
- starts the backend against it on an ephemeral port, waits for readiness, and stops it
  cleanly (the `lifespan="off"` trap from Sprint 050's worklog is the runner's problem, not
  each flow's);
- accepts the source library path as an argument, never hardcoding an owner path;
- is flow-agnostic: a walkthrough spec (Playwright or script) runs against the base URL it
  prints, so the next sprint's gate is *launch, run flow, assert* rather than another
  hand-rolled runner.

The two existing series runners may be ported onto it or left as-is; the deliverable is the
launcher plus one flow proved through it end to end. Owner-specific paths stay in environment
variables or arguments, per TESTING.md's reuse rules.

### 4. Bounded test timeouts

Backlog item 4, verbatim: *"Add bounded test timeouts or phase timing where a deadlock
currently looks like slow work."*

- Backend: add `pytest-timeout` (or equivalent) with a per-test bound generous enough that no
  current test approaches it — measure the slowest current tests first and record the bound's
  justification in the config comment. A hang now fails with the test's name instead of
  stalling the gate.
- Frontend: set an explicit Vitest `testTimeout` for the same reason.
- Playwright already has per-test timeouts by default; if the config relies on the default,
  say so in a comment rather than leaving it implicit.
- Update TESTING.md's triage section to point at the bounds: "silence beyond the baseline"
  becomes "the bound fires and names the test".

## Acceptance criteria

1. Playwright runs the ordinary specs in parallel and the two load-sensitive `library.spec.ts`
   invariants serially; the full suite is green and materially faster than the 49.4 s baseline,
   or the measurement showing why it cannot be is recorded instead.
2. A green `npm test` prints zero `Query data cannot be undefined` lines and zero `act(...)`
    warnings; a deliberately failing console check still surfaces (prove the guard is not a
    blanket suppression).
3. `scripts/walkthrough.py` launches a backend on a fresh temporary data directory from one
   command, and one existing walkthrough flow runs green through it.
4. A test that hangs now fails with its name: demonstrate by timing out a deliberately sleeping
   throwaway test (not committed) in each of the backend and frontend suites.
5. `make check` and `make test` are green; every existing Playwright and Vitest test passes
   unmodified in behavior (only harness/config moved).
6. TESTING.md's *Optimization backlog* section is removed at closure and its triage section
   updated to name the new bounds; the time table is updated with the new measured durations.

## Required tests (TDD where applicable)

This sprint changes harness and configuration, not application behavior, so the TDD loop maps
onto it as: observe the property failing (serial run, noisy output, no timeout), change the
harness, observe the property hold. Specifically:

- The Playwright split is proven by the suite itself running green under the new projects, with
  the two heavy tests observed running in the serial project (`--list` output recorded).
- The Vitest noise removal is proven by grep on green output: zero matches for the two named
  warning shapes.
- The launcher is proven by running one existing flow through it against a fresh data dir.
- The timeout is proven by a throwaway sleeping test hitting the bound, in each suite, with the
  failure output recorded and the throwaway removed.

## Verification

```bash
cd frontend && npm run test:e2e            # full suite, new project split, timed
cd frontend && npm test                    # green and quiet
cd backend && uv run pytest -q             # green under the new timeout bound
python scripts/walkthrough.py --help       # and one flow through it
make check
make test
```

## Explicit non-scope

- **No application behavior change.** Nothing under `backend/src/book_tracker/` outside test
  configuration; nothing under `frontend/src/` outside test mocks and setup.
- **Parallelizing the backend pytest suite** (pytest-xdist) — the backlog does not name it and
  the 60 s backend gate is not the pain TESTING.md recorded.
- **Reducing test count or weakening assertions to buy speed** — TESTING.md's output discipline
  forbids it; this sprint optimizes scheduling, isolation and signal quality only.
- **The e2e `ECONNREFUSED` proxy noise** observed during the baseline run (the dev server
  proxies `/api` to a backend that is not running) — worth recording in the worklog, not
  silently fixing here; it is not one of the four backlog items.
- Porting every scratchpad walkthrough onto the new launcher — one flow proves it; the rest
  migrate when they next run.

## Commit checkpoints

1. `[TEST] Split Playwright into parallel and serial-heavy projects`
2. `[TEST] Silence the Vitest harness noise`
3. `[TEST] A tracked walkthrough launcher`
4. `[TEST] Bound every test with a timeout`
5. `[DOCS] Close sprint 051 and hand off`

## Risks and decisions to surface

- **Parallel Playwright may expose hidden inter-test coupling** (shared dev-server state,
  seeded fixtures). That coupling is a finding: surface it, fix the isolation — do not weaken
  the assertions.
- **The 49.4 s suite may be boot-dominated** (two web servers, one of which builds the
  production bundle). If so, the honest outcome is the explicit split plus the measurement,
  not a fabricated speedup.
- **Timeout bounds must be measured, not guessed.** A bound a current slow test can approach
  is a flaky-test generator; record the slowest observed tests and the headroom.
- **Removing the backlog section from TESTING.md** is part of closure — the section exists to
  be emptied, and leaving it after implementing all four items would re-register finished work
  as pending.

## Outcome

_Not started._
