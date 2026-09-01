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

Measured on this workstation 2026-09-01, at Sprint 053's closure (DEC-114):

| Gate | Normal duration | |
|---|---:|---|
| `make check` | about 2 seconds | red if a local scratchpad spec is unformatted — Sprint 055 |
| backend pytest, 1090 tests, as `addopts` runs it | about 68 seconds | |
| backend pytest, `--no-cov` | about 42 seconds | **coverage costs 26 s of the above** |
| frontend Vitest, 194 tests | about 24 seconds | |
| `make test` combined | about 91 seconds | |
| full Playwright, parallel | about 38 seconds | **fails 1–2 tests every run** — Sprint 055 |
| full Playwright, serial (`--workers=1`) | about 102 seconds | green; the trustworthy result today |
| Sprint 053 walkthrough, after the backend is ready | about 8 seconds | |

Until Sprint 055 lands, **the serial Playwright run is the gate**: the parallel split has not passed
once, always on the same two rendering-timing tests, so a session that runs it runs the serial one
afterwards anyway and pays for both.

These are diagnostic baselines, not performance acceptance criteria. Every test is bounded, so a
deadlock no longer looks like slow work: the bound fires and names the test — backend pytest at 30 s
(`--timeout=30` in `backend/pyproject.toml`), frontend Vitest at 15 s (`testTimeout` in
`frontend/vite.config.ts`), Playwright at 60 s (`timeout` in `frontend/playwright.config.ts`). If a
normally chatty command still produces no output through twice the expected phase duration:

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

`scripts/walkthrough.py` is the tracked launcher: one command creates a fresh temporary data
directory, starts the backend on an ephemeral port, waits for readiness, and stops it cleanly.

**Fresh per launch, not per spec run.** Rerunning a spec against a still-running launcher inherits
the previous attempt's data: a committed batch replays by fingerprint and approved rows leave an
empty inbox, so a spec that is merely being debugged fails in ways that look exactly like product
defects. That cost three attempts in Sprint 053. Restart the backend for every attempt — a short
wrapper that kills the old one, starts a new one, waits for the printed URL and runs the spec makes
that free.

**Enrichment is a background job, so a browser assertion races it.** Prove a post-commit enrichment
criterion with a short script that commits through the API and polls until the covers arrive
(about 6 seconds in Sprint 053), rather than by adding a sleep to a Playwright spec.
`--replay <module>` installs a module's `walkthrough_transport(live)` seam (the pattern
`scripts/walkthrough_series_050.py` defines) so provider responses replay from fixtures while the
rest of the boundary stays live; `--keep` preserves the data dir for inspection. A flow runs against
the base URL the launcher prints.

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
- Scratchpad specs are excluded from the normal Playwright gate. Run one explicitly with
  `BOOK_TRACKER_INCLUDE_SCRATCHPAD=1 npm run test:e2e -- --project=chromium --workers=1
  e2e/scratchpad/<file>.spec.ts` from `frontend/`.

### Current UI idioms

Use the controls the application actually exposes when adapting a walkthrough:

- the domain chooser is a `radiogroup`, not tabs or a native select;
- the Library status filter is a popover whose option names include live facet counts;
- Library-row status controls are popovers, while Triage-row status controls are native selects
  (DEC-086);
- the Triage heading reads `Inbox N unsorted` while rows remain, and `Inbox is clear` once they
  are all approved;
- Detail remains `/books/:id` for every domain, a deliberate cosmetic coupling (DEC-067 row 8).

`frontend/e2e/scratchpad/anime-walkthrough.spec.ts` is the working reference for the domain chooser,
Library filters, row controls and Detail route. `frontend/e2e/scratchpad/sprint42-walkthrough.spec.ts`
is the working reference for mixed-domain Triage rows and their native status selects. Adapt their
role/name selectors; do not copy their owner-specific data paths.

The walkthrough remains a manual acceptance gate even when expressed as Playwright: a skipped local
walkthrough does not count as having exercised the flow.

## Output discipline

- Prefer concise reporters for green runs; retain complete failure output or an artifact path.
- Record counts, duration and the first actionable failure—not thousands of lines of known warning
  noise—in the Outcome and worklog.
- Poll a long-running command at sensible phase boundaries. Silence alone is not evidence of a
  hang, but silence beyond the baseline requires diagnosis.
- Never weaken a test to shorten a gate. Optimize scheduling, isolation and signal quality instead.
