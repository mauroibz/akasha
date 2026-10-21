# Sprint 101 — Metrics, provider health from real calls, the response cache

**Sprint:** 101
**Status:** ready
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

_Not started._
