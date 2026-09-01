# Sprint 059 — Nothing blocks the event loop **[GATED]**

**Status:** ready
**Depends on:** 056

**Roadmap revision:** 30

## Objective

A long import, a batch of covers or a large attachment must not stop the application answering
anybody else. Phase A **measures** whether that is true today on hardware that resembles a home
server. Phase B changes something only if the measurement says it should, and re-measures.

Phase A concluding *no change needed* is a complete and correct outcome, recorded as a decision with
its numbers. This is the gated shape DEC-035 and DEC-042 established for work whose cost is unknown
until it is measured.

## Required context

- `backend/src/book_tracker/api/imports.py`, `api/library.py`, `api/export.py` — every handler.
- `backend/src/book_tracker/application/imports.py` — `preview` and `commit`, called synchronously
  from `async def` handlers.
- `backend/src/book_tracker/infrastructure/covers.py` — Pillow decode, convert and resize.
- `backend/src/book_tracker/infrastructure/jobs.py` — the job runner, which shares the loop with
  request handling as an `asyncio` task.
- `backend/src/book_tracker/database.py` — the engine and its per-connection pragmas.
- `scripts/benchmark_library.py` — the existing measurement harness and the shape its numbers take.
- `docs/decisions.md`: **DEC-036**, which is the only contended latency number this project has, and
  the technical spec's 500 ms first-library-page budget it was measured against.
- `Dockerfile`'s `CMD`: one uvicorn worker, deliberately.

## Current implementation baseline

To be re-confirmed at activation. As observed 2026-09-01:

- **Every API handler is `async def`**, and there is not one `run_in_threadpool`, `anyio.to_thread`
  or `asyncio.to_thread` anywhere under `backend/src/book_tracker/`. Every SQLite query, every
  Pillow decode and resize, every CSV, zip and `metadata.db` read, and every file write therefore
  runs directly on the event loop.
- One uvicorn worker. There is no second process to answer while the first is busy, and there must
  not be one: two processes writing one SQLite file is a different and worse problem.
- `import_service.preview(...)` and `.commit(...)` are ordinary synchronous calls inside
  `async def preview` and `async def commit`.
- The job runner is an `asyncio` task on the same loop. Its provider calls are properly async; the
  cover work it does between them is not.
- The healthcheck allows a 3 s timeout, three times, so a loop blocked for about ten seconds is
  enough to mark a working container unhealthy.
- **The only contended measurement that exists is DEC-036's**, and it was a *read* path: first
  library page 82 ms p95 idle against 312 ms with the job queue draining, after the normalized-sort
  indexes landed. It was taken on a developer workstation, which DEC-036 itself notes is
  considerably faster than the target class of machine, and no import or cover path has ever been
  measured under contention at all.

Nothing above is a defect on its face. Single-threaded is a legitimate design for one user, and the
read paths were tuned against a real budget. What is missing is any evidence about the *write* paths
on the hardware this actually runs on — which is exactly what Phase A is for.

## Deliverables

### Phase A — measure, then decide

1. **A harness that measures latency under load, not throughput.** Extend
   `scripts/benchmark_library.py` or add a sibling beside it. One client drives a realistic
   background task; a second client asks for the first library page, repeatedly, and records the
   latency distribution while the first is working. The background tasks worth measuring, each on a
   library of realistic size:
   - a large import commit;
   - an enrichment backfill installing covers;
   - a large attachment upload.
2. **Constrain the CPU so the number means something.** Measure inside the container with an
   explicit CPU limit rather than on a fast workstation. A home server is a small number of slow
   cores and often a spinning disk; a measurement taken without that constraint answers a question
   nobody asked. State the constraint used, so the number can be reproduced.
3. **A verdict in `docs/decisions.md`**, with the table. Either the 500 ms first-page budget holds
   under every scenario — in which case Phase B does not happen and the decision records that this
   was checked and found sound — or it names which scenario breaches it and by how much.

### Phase B — only what Phase A named

Conditional on the verdict, and scoped by it rather than by this file:

4. **One offload seam, in one place.** A single helper that runs a synchronous callable on a worker
   thread, applied at the handler boundary of the paths Phase A named. One seam, not a scattering of
   `to_thread` calls: a later reader must be able to find every place work leaves the loop by
   grepping for one name.
5. **A bounded worker count, chosen deliberately.** Moving work to threads does not make SQLite
   concurrent. Writers still serialize, and `PRAGMA busy_timeout` is what stands between a queued
   writer and an error — Sprint 056 made that value configurable, and this sprint is where its
   default gets defended or changed with evidence.
6. **The engine's threading contract, confirmed rather than assumed.** Before any query moves off the
   loop, establish what the configured engine and pool actually permit across threads, and write it
   down beside `create_engine`. The per-connection `PRAGMA` listener in `database.py` must be
   verified to still apply to every connection a worker thread receives — foreign keys and WAL are
   invariants, and a pooled connection that silently missed a pragma would be the worst possible
   outcome of this sprint.
7. **Re-measure and record both numbers.** The same harness, the same constraint, before and after.

### Either way

8. **`docs/agent/TESTING.md` gains the harness** in its verification vocabulary, so a later sprint
   that touches an import path knows the measurement exists and how to run it.
9. **Release notes for v1.5.5.** If Phase A ends the sprint, the release is a documented measurement
   and whatever small things came with it — and that is worth saying plainly rather than dressing up.

## Acceptance criteria

1. The harness runs from a clean checkout, takes a named CPU constraint, and prints a latency
   distribution for the observing client for each of the three background scenarios.
2. A decision entry carries the measurements, the constraint they were taken under, and an explicit
   verdict against the 500 ms first-library-page budget.
3. If the verdict is *no breach*: the sprint closes with no runtime change, and the decision says
   what was measured and why nothing was done. This is a pass, not a failure.
4. If the verdict is *breach*: the named scenario is re-measured after the change and is inside
   budget, with both numbers recorded.
5. The container's healthcheck does not report `unhealthy` at any point during any measured
   scenario.
6. Foreign keys, WAL and the busy timeout are proved to apply on a connection used from a worker
   thread — a test that asserts the pragmas on a connection obtained off the main thread.
7. No behaviour visible to a person changes: same responses, same status codes, same ordering,
   same undo semantics. The full backend and frontend suites are the guard.
8. Still exactly one uvicorn worker.

## Required tests (TDD)

- **Pragmas hold off-thread.** The load-bearing test of Phase B. Obtain a connection from a worker
  thread and assert `foreign_keys`, `journal_mode` and `busy_timeout`.
- **Concurrency does not corrupt the ledger.** An import commit running while another request writes
  through the same engine leaves both results correct, with no lost row and no partial batch —
  written against the existing repository tests rather than a new abstraction.
- **A queued writer waits rather than failing.** With a deliberately short busy timeout, prove the
  error surfaces as a typed application error and not as an unhandled `database is locked`.
- **The undo window is unaffected.** The 24-hour batch undo behaves identically for a batch
  committed through the offloaded path.
- The existing suites are the regression gate: nothing in this sprint may change a single assertion
  about what a request returns.

## Verification

```bash
python scripts/validate_project.py
make check
make test
make smoke-container
python scripts/<the harness> --cpus <limit>   # each scenario, before and after
npm run test:e2e                              # only if Phase B changed a request path
```

**The gate depends on which phase the sprint ends in.**

*If Phase A ends it* — the measurement finds no breach and no runtime code changes — the sprint
qualifies for the narrowed gate in `docs/agent/TESTING.md`: the harness, `validate_project.py`,
`make check` and `make smoke-container`, with `make test` and Playwright not owed. A new measurement
script under `scripts/` does not withdraw the narrowing; anything under `backend/src/` does.

*If Phase B runs*, the **full gate is owed with no argument**. It moves work across a thread boundary
on every write path in the application, which is the broadest-blast-radius change in this whole line,
and a walkthrough against realistic data is owed on the import flow: run a real import end to end and
report what it felt like, per the walkthrough gate in `AGENTS.md`.

## Explicit non-scope

- **Multiple uvicorn workers.** One SQLite file, one writer process. Not negotiable in this sprint.
- **An async database driver, or rewriting the repository layer.** The seam is a thread boundary at
  the handler, not a new persistence model.
- **A separate worker process for the job runner.** DEC's existing note that the runner is testable
  without subprocess orchestration still holds; if Phase A shows the runner is the problem, say so
  and let it be its own sprint rather than smuggling a process model in here.
- **Streaming, pagination or protocol changes** to make responses feel faster. This is about not
  blocking, not about response shape.
- Anything from Sprints 056, 058 or 060.

## Commit checkpoints

Phase A:

1. `[ADD] Measure request latency while the server is busy`
2. `[DOCS] The verdict, with its numbers`

Phase B, only if the verdict calls for it:

3. `[ADD] One seam for work that must leave the loop`
4. `[CHANGE] Move the measured-blocking paths onto it`
5. `[DOCS] Re-measured, and release notes for v1.5.5`
6. `[DOCS] Close sprint 059 and hand off`

## Risks and decisions to surface

- **This sprint can end with no code change, and that must stay an acceptable outcome.** The pressure
  to justify the sprint by changing something is the main risk to its honesty. DEC-035 and DEC-042
  set the precedent; criterion 3 states it as a pass.
- **Threads plus SQLite is where a data-safety bug would live if this sprint produced one.** The
  pragma listener, the busy timeout and the transaction boundaries in `JobRepository._write` are the
  three things to prove rather than assume. If any of them cannot be proved cleanly, stop and record
  it instead of shipping.
- **A measurement taken on the wrong machine is worse than none**, because it will be quoted later.
  State the CPU constraint next to every number.
- If Phase A finds the breach is in a *provider* wait rather than in local work, the answer is not
  threads at all, and the sprint should say so and stop.

## Outcome

_Not started. On completion record delivered behavior, commands and actual results, commit IDs, deviations/decisions, and impact on every future sprint._
