# Akasha v1.5.5 — release notes

Sprint 059: a measurement, and a fix for what it found. No screen changed, no response shape
changed, no status code changed — every acceptance criterion is about whether the application
stays responsive while it works, not about what it does.

## What changed

- **A large import commit no longer freezes the application for everyone else.** Committing an
  import ran entirely synchronously inside the request handler — many database writes and a
  per-item cover install, with no `await` anywhere in the middle — so the single worker process
  could not answer any other request until the whole commit finished. Measured on hardware
  constrained to 2 CPUs (this repository's own precedent for "small home server"), a 5,000-row
  commit held the first library page's p95 latency at just over five seconds against a 500 ms
  budget, with real request timeouts. It now moves onto a worker thread through one seam
  (`infrastructure/offload.py`'s `off_loop`), and the same measurement now shows a 78 ms p95 with
  zero errors.
- **Cover uploads and large attachment uploads were already fine.** Measured at the same 2-CPU
  constraint, both stayed comfortably within budget before any code changed — each individual
  upload's work is short enough that the loop reliably regains control between requests. Neither
  was touched.
- **A newly possible failure mode was closed in the same change.** Moving work onto a worker
  thread is the first time this application can have two real threads writing to SQLite at once;
  a write that loses the race for the lock now surfaces as a typed, retryable `library_busy`
  error instead of an unhandled database error, if `PRAGMA busy_timeout` (configurable since
  Sprint 056) still expires.
- **`scripts/measure_event_loop.py`/`.sh`** is now a tracked measurement harness — the container's
  own Docker healthcheck is watched throughout a scenario, not just timed from outside, because a
  slow response and an actual `unhealthy` container are different claims.

## What this release deliberately does not do

- **No second uvicorn worker.** Still exactly one process, one SQLite file.
- **No async database driver, no repository rewrite.** The fix is a thread boundary at the
  handler, nothing about how data is read or written changed.
- **No behavior visible to a person changed.** Same responses, same status codes, same ordering,
  same undo semantics — proven by the full backend and frontend suites passing unchanged.

## Upgrading

```bash
echo "AKASHA_VERSION=1.5.5" >> .env
docker compose pull
docker compose up -d
```

Nothing migrates and no data volume moves.
