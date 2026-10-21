# Sprint 087 — Jobs that keep their word

**Sprint:** 087
**Status:** ready
**Roadmap revision:** 45
**Depends on:** 086
**Owner:** Mauro

## Objective

Background work never loses an attempt to its own bookkeeping, the request path never runs
synchronous database work on the event loop, and every error that reaches the browser is the one
envelope, tied to the log lines that explain it by a request id. This is the first sprint of the
production-grade line (DEC-165) and the foundation the command bar, the event stream and the
redrawn import stand on.

## Required context

- `AGENTS.md`, `docs/agent/WORKFLOW.md`, `docs/agent/TESTING.md` (especially "Event-loop
  contention").
- [`../production-grade-proposal.md`](../production-grade-proposal.md) §2.4 (R1, R2, R3, R5 server
  half, R7) and §6.1, §6.2, §6.4 (server half), §6.6 (request ids only).
- DEC-165 (this line), the Sprint 059 verdict in `docs/decisions.md` (why `off_loop` exists and is
  bounded at four threads), DEC-045 (provider quotas and deferral).
- `backend/src/book_tracker/infrastructure/jobs.py` (`JobRepository`, `RateLimiter`, `JobRunner`),
  `infrastructure/offload.py`, `application/enrichment.py`, `application/import_search.py`,
  `reclaim.py`, `main.py` (`authentication_boundary`, the exception handlers, `missing_api`),
  `api/auth.py` (`error_response`), `api/identity.py`, `logging.py`, every module in `api/`.
- Tests: `test_jobs.py`, `test_enrichment.py`, `test_import_search_job.py`,
  `test_event_loop_offload.py`, `test_logging.py`, `test_auth_api.py`.

## Current implementation baseline

Measured 2026-10-21 at `e8127f6`:

- **R1.** `JobRepository.claim` leases a job for `LEASE_DURATION` (5 minutes). `heartbeat()`
  (`jobs.py:152`) has no caller. `ImportSearchHandler.process` walks every row of a batch inside
  one job, so a batch slower than five minutes is reclaimed by `reclaim_expired` while it is still
  running, and the reclaim spends an attempt.
- **R2.** `EnrichmentHandler.process` (`enrichment.py:294-299`) returns `state: failed,
  error_code: rate_limited` when the shared `RateLimiter` (one timestamp, 0.5 s, built in
  `main.py:276`) is not ready, which spends a retry. `ImportSearchHandler` waits on the same gate
  instead (`import_search.py:170-173`). The providers that need real pacing already pace
  themselves in their clients: MusicBrainz (`domains/album/providers.py:194-211`), AniList and
  Kitsu (`domains/anime/providers.py`), both Wikidata clients (`domains/movie/providers.py`).
- **R3.** Of the 65 API routes, 45 are `async def` with no `await` at all, so their synchronous
  SQLAlchemy work runs on the event loop; 20 await something and also do synchronous work around
  it. `authentication_boundary` calls `has_credentialed_user` and `SessionStore.lookup`
  synchronously on every authenticated request. `JobRunner.run_forever` and `tick` call `claim`,
  `complete`, `fail`, `reclaim_expired` and `reclaim_import_batches` synchronously, and both
  handlers open sync sessions inside `async def process`.
- **R5 (server).** Three error shapes reach the client: the `{"error": {code, message, details}}`
  envelope (`api/auth.py:102`, `LibraryError`), `{"detail": "Not Found"}` from `missing_api` and
  the auth-off 404, and FastAPI's default `HTTPException` and 422 bodies.
- **R7.** `logging.py` already merges structlog contextvars; nothing binds a request id.

## Deliverables

1. **Leases stay alive.** `ImportSearchHandler` heartbeats its job once per row. `JobRunner`
   gives every handler the same means (a `heartbeat` callable or the repository), so a future long
   handler does not have to discover it.
2. **A busy gate waits.** `EnrichmentHandler` waits for the rate gate the way import search
   already does; `rate_limited` is no longer produced. The global gate stays as the floor for the
   providers that do not pace themselves; no second per-provider layer is built (DEC-165).
3. **Nothing synchronous on the loop.**
   - Every `async def` route with no `await` becomes `def`, so Starlette's threadpool runs it.
   - The 20 awaiting routes move their synchronous database and disk work into `off_loop`.
   - `authentication_boundary` performs its lookups through `off_loop`.
   - `JobRunner`'s repository calls and both handlers' database blocks run through `off_loop`.
   - One test walks the route table and fails on an `async def` endpoint that never awaits.
4. **One error envelope.** Exception handlers for Starlette's `HTTPException` and
   `RequestValidationError`; `missing_api` and the auth-off 404 return the envelope. Validation
   errors carry their field list in `details`. No client code changes are owed: every client
   parser already reads the envelope and falls back on status.
5. **Request ids.** An outermost middleware accepts a well-formed incoming `X-Request-Id` or makes
   one, binds it into the structlog context for the life of the request, returns it as
   `X-Request-Id`, and logs one `request_finished` line (method, route template, status,
   duration). Job processing binds `job_id` and `job_kind` the same way.

## Acceptance criteria

1. An import search job whose rows take longer in total than `LEASE_DURATION` is not reclaimed
   while it runs and finishes with `attempts == 0`.
2. Two enrichment jobs processed back to back inside the gate's interval both succeed; no job
   records `rate_limited`, and neither spends an attempt.
3. Every API route endpoint is either `def` or an `async def` that awaits; the route-table test
   enforces it. A request to `/api/health/live` returns while an offloaded library write, an
   authenticated request's session lookup, and a job runner claim are each held artificially slow.
4. `GET /api/nonexistent`, a 404 from auth-off mode, an `HTTPException` raised by a route, and a
   malformed body to a validated route all return `{"error": {"code", "message", "details"}}`.
   The validation case names the offending field in `details`.
5. Every response carries `X-Request-Id`. An incoming id of 8–64 characters from `[A-Za-z0-9._-]`
   is echoed; anything else is replaced. Log lines emitted while handling the request carry
   `request_id`, and lines emitted while processing a job carry `job_id`.
6. No behaviour visible to the person changes except that background work finishes more often;
   the full gate, including Playwright, stays green.

## Required tests (TDD)

- `test_jobs.py`: heartbeat extends the lease; a heartbeating handler survives
  `reclaim_expired` at a time past the original lease.
- `test_import_search_job.py`: the handler heartbeats per row; a slow batch completes with zero
  attempts spent.
- `test_enrichment.py`: back-to-back jobs under a not-ready gate wait and succeed.
- `test_event_loop_offload.py`: route-table rule; health stays responsive while the middleware
  lookup and the runner's claim are slowed.
- A new `test_error_envelope.py`: the four error sources above, each in the envelope.
- `test_logging.py`: request id generated, echoed, rejected when malformed, present on log lines;
  job ids on job log lines.

## Verification

- `cd backend && uv run pytest` on the focused files, then `make check` and `make test`.
- `cd frontend && npx playwright test` (the full browser suite: the error shapes changed under
  the client).
- Walkthrough: run against a copy of the owner's data, import a real Goodreads CSV of at least
  200 rows, and confirm from the jobs table that no job was reclaimed or recorded `rate_limited`.
  Confirm `X-Request-Id` in the browser's network panel and the same id in the server log for one
  failing request.

## Explicit non-scope

- The generated client, `ApiError`, the query-key factory and `create_app`'s split: Sprint 088.
- The event stream, incremental progress written for it, and the activity indicator: Sprint 089.
- `/metrics`, provider health from real calls, the response cache: Sprint 101.
- Raising or lowering the threadpool size. Measure it here; change it only with evidence.

## Commit checkpoints

1. `[FIX]` Long jobs heartbeat; enrichment waits on the rate gate.
2. `[FIX]` Routes that never await become sync; the route-table rule.
3. `[FIX]` The middleware, the runner and the handlers leave the event loop.
4. `[MOD]` One error envelope for every error.
5. `[ADD]` Request ids in headers and logs.
6. `[DOCS]` Close sprint 087 and hand off.

## Risks and decisions to surface

- Starlette's threadpool allows 40 threads, while `off_loop` allows four (Sprint 059). Reads are
  safe under WAL; concurrent writers queue on `busy_timeout` and surface as `library_busy`
  already. Record the measured contention in the Outcome.
- A `def` route cannot call an `async` helper. A route that needs both stays `async def` with its
  synchronous part offloaded.
- `fastapi.testclient` and `httpx.ASGITransport` behave differently with threadpool routes in a
  few fixtures; fix fixtures rather than keep a route async for a test's sake.

## Outcome

_Not started._
