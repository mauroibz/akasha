# Sprint 101 — Metrics, provider health from real calls, the response cache

**Sprint:** 101
**Status:** completed
**Roadmap revision:** 45
**Depends on:** 100
**Owner:** Mauro

## Objective

A self-hoster can see what the application is doing, and *provider health* reports whether
providers are answering, not just whether they are configured. Asking a free API the same
question twice in a day costs one request.

## Required context

- [`../production-grade-proposal.md`](../production-grade-proposal.md) §6.6 (R6, R7); DEC-165,
  DEC-167; [`../../AGENTS.md`](../../AGENTS.md) (network providers are never consulted while
  rendering cached library pages).
- `backend/src/book_tracker/app/{providers,middleware,health}.py`,
  `infrastructure/jobs.py`, `components/ProviderHealthNotice.tsx`.

## Current implementation baseline

- Request ids exist (Sprint 088).
- `/api/health/providers` reports *configured*, not *working*.
- There is no metrics endpoint and no response cache.

## Deliverables

1. **Provider health from real calls.** Every provider call records its outcome and latency in a
   bounded in-memory window per provider. Health reports `working`, `degraded` or `down` from
   the last N calls, and `ProviderHealthNotice` shows it.
2. **Response cache.** A SQLite table, added by migration, holds search and resolve answers keyed
   by provider and normalized query, with a TTL of about 24 hours. A hit makes no network call.
   Failures are never cached.
3. **Metrics.** An opt-in `GET /metrics` (`AKASHA_METRICS=on`) in Prometheus text format. It
   reports queue depth, job outcomes by type, provider latency and error counts, and request
   latency. With the setting off the route is absent.

## Acceptance criteria

1. A provider that failed its last calls reads `down` in health and the notice says so. One that
   recovers reads `working` again.
2. The same search twice within the TTL reaches the provider once.
3. `/metrics` answers only when enabled and carries the four families.

## Verification

Per DEC-167: the covering backend tests, the route-structure suites when a route is added,
`vitest related`, `make check`, and a live check of `/metrics` and the health notice.

## Outcome

**Delivered.**

- `infrastructure/observed.py`: `ObservedProvider` wraps every catalogued provider without
  naming any.
  - Each call is timed into `ProviderObservations`, with a window of 20 calls per provider.
    - `down`: the last three calls failed.
    - `degraded`: at least 30% of the window failed.
    - `working`: anything else.
  - "Record not found" is an answer, not an outage.
- `search` goes through `ResponseCache`: the `provider_responses` table (migration 0025), with a
  24-hour TTL, keyed by provider, normalized query and limit. Failures are never stored, and
  `fetch` is never cached.
- `/api/health/providers` rows carry `state`. `ProviderHealthNotice` names a provider that is
  configured but not answering.
- `AKASHA_METRICS=on` mounts `/metrics` in Prometheus text (`app/metrics.py`, no new dependency).
  It reports queue depth, jobs by kind and state, provider calls and seconds, and request latency
  by route template, which the request middleware records.
- Documented in `.env.example`, the README settings table, runbook *Metrics*, and technical spec
  §8.

**Acceptance.**

1. `test_operability.py`:
   - three failed calls read `down`, and ten good calls read `working` again;
   - not-found calls stay `working`;
   - the health route reports `down` with `degraded: true`;
   - the notice test names a down and a degraded provider.
2. `test_operability.py`: the same search, differently spaced and cased, reaches the provider
   once, a new query reaches it again, and so does the same query after 25 hours. A failure is
   not cached.

   Live: the second identical *Ficciones Borges* search took 2 ms against 1.07 s, and `/metrics`
   counted one OpenLibrary call for the two requests.
3. `test_operability.py`: `/metrics` is 404 when the setting is off. When it is on, it serves the
   five families. Read live on the dev server.

**Verification.**

- The full backend suite, run because the wrapper sits in front of every provider call: 1686
  passed. One earlier full run had `test_events.py::test_the_stream_carries_each_change_to_a_job`
  fail. It passed alone and passed in the rerun. It is timing-sensitive under load, recorded and
  not marked.
- `vitest related` on the notice and `make check`, both green.

**Commit.** 852a6ca.

**Deviations.**

- *Resolve* is not cached separately. Its text searches go through `search` and are cached; its
  lookups by id are `fetch` and stay live.
- A provider's live `down` state was not provoked against a real outage. The unit and route tests
  cover it.
