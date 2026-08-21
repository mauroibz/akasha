# Verification playbook

**Status:** canonical
**Decision:** DEC-084

This playbook keeps sprint evidence trustworthy without paying for the same evidence repeatedly.
It governs cadence and execution; the active sprint still governs which behaviors and commands are
required.

## The verification ladder

1. **During TDD, stay focused.** Run the failing test, then its file or nearest neighboring suite.
   Do not run every backend, frontend and browser test after each small edit.
2. **At a coherent checkpoint, widen one level.** Run regression tests for the boundary changed and
   commit the green slice. If the boundary is external, use recorded real responses rather than a
   mock of the unit whose correctness is at issue.
3. **Stabilize the user flow before the walkthrough.** Run the affected E2E spec first. Then perform
   the realistic-data walkthrough once against the final interaction, not while selectors and copy
   are still moving.
4. **Freeze implementation.** Runtime code, tests, migrations, dependencies, lockfiles, build/test
   configuration and generated contracts stop changing before exhaustive verification begins.
5. **Run the exhaustive gate once.** Execute every distinct command in the sprint's Verification
   section, `make check`, `make test`, and any required Playwright, build, container or migration
   proof. If the sprint already lists `make check` or `make test`, that is the same command—not a
   reason to execute it twice.
6. **Reconcile and close.** Update the Outcome, canonical docs, roadmap, worklog, handoff and state.
   Then classify the post-gate diff with the matrix below.

Passing a lower rung never replaces a required higher rung. The ladder changes when a command runs,
not whether it runs.

## Post-gate rerun matrix

| Change after the exhaustive gate | Required before closure |
|---|---|
| Outcome, roadmap, worklog, handoff or state text only | `python scripts/validate_project.py`, applicable documentation formatting/link checks, `git diff --check` |
| README, guide, product/technical spec or examples only | The checks above, plus any formatter, doctest or example validator that owns the changed artifact |
| Runtime source, tests, migration or fixture | Focused proof for the change, then the affected exhaustive test gate again |
| Dependency, lockfile, build/test configuration or CI | `make check`, `make test`, and the affected build/browser/container gate again |
| OpenAPI or another generated contract | Regenerate/check it, run both producer and consumer type checks, then the affected test gate |
| Unclear or mixed | Treat it as product-affecting and rerun the full gate |

A documentation edit that changes executable examples, generated inputs or operational commands is
not “text only.” Classify by effect, not extension.

## Time and environment triage

Measured on this workstation at Sprint 035 closure:

| Gate | Normal duration |
|---|---:|
| `make check` | about 8 seconds |
| backend pytest, 559 tests | about 60 seconds |
| frontend Vitest, 179 tests | about 25 seconds |
| `make test` combined | about 85 seconds |
| full Playwright, one worker | about 1 minute 40 seconds |
| Sprint 035 realistic-data walkthrough | about 13 seconds after services are ready |

These are diagnostic baselines, not performance acceptance criteria. If a normally chatty command
produces no output through twice the expected phase duration:

1. inspect the process and identify the exact test or phase;
2. reproduce that unit once, with verbose naming and a bounded timeout;
3. decide whether it is computation, an application deadlock, or an execution-environment failure;
4. change one variable—the test scope or environment—and compare;
5. do not rerun the same opaque command in the same environment without a new hypothesis.

Known Codex-hosted failure signature: FastAPI/Starlette `TestClient` can block with its main thread
on a futex and its event-loop thread in `ep_poll` inside the isolated PID/network sandbox. During
Sprint 035 the export memory cases stalled there for minutes, then passed outside that namespace in
3.79 seconds; the complete backend suite passed outside it in about 60 seconds. After confirming
that signature with a focused case, use the approved non-sandbox test execution rather than waiting
or repeating the sandboxed run. This is an environment workaround, never permission to ignore a
failure that reproduces outside the sandbox.

## Walkthrough reuse

Before writing a walkthrough, search the active sprint, `frontend/e2e/`,
`frontend/e2e/scratchpad/`, the last worklog entry and the handoff. Adapt the nearest existing flow.

- Keep owner-specific paths and destructive data targets in environment variables.
- Use a clean temporary application data directory; realistic source data is input, never the live
  application database.
- Prefer role/name selectors and literal string comparison. Escape dynamic regular expressions, or
  avoid constructing them from filenames.
- Make setup and teardown repeatable. Record the launch command, environment variables, observed
  counts and disk measurements in the worklog.
- Preserve useful local walkthroughs under the ignored `frontend/e2e/scratchpad/` directory. When a
  flow becomes generally reusable and contains no private paths or data, promote a sanitized runner
  or fixture to tracked test infrastructure in a scoped sprint.

The walkthrough remains a manual acceptance gate even when expressed as Playwright: a skipped local
walkthrough does not count as having exercised the flow.

## Output discipline

- Prefer concise reporters for green runs; retain complete failure output or an artifact path.
- Record counts, duration and the first actionable failure—not thousands of lines of known warning
  noise—in the Outcome and worklog.
- Poll a long-running command at sensible phase boundaries. Silence alone is not evidence of a
  hang, but silence beyond the baseline requires diagnosis.
- Never weaken a test to shorten a gate. Optimize scheduling, isolation and signal quality instead.

## Optimization backlog—not implemented yet

These observations are registered so a future sprint can cost and implement them deliberately:

1. Split Playwright into a parallel ordinary project and a serial heavy-library project. Today the
   whole suite uses one worker because two `library.spec.ts` invariants are load-sensitive.
2. Remove known Vitest harness noise: provide a deliberate `window.scrollTo` test shim, return
   defined attachment-query fixtures, and await Radix/motion state updates correctly. Preserve real
   console failures while making green output readable.
3. Promote the local realistic-data flow to a tracked, sanitized launcher that creates a temporary
   data directory, starts and stops the backend, and accepts the library path in one command.
4. Add bounded test timeouts or phase timing where a deadlock currently looks like slow work.
