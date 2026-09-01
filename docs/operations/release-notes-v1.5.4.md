# Akasha v1.5.4 — release notes

An out-of-sprint patch, not tied to a numbered sprint (see DEC-121). It carries one fix — CI's
`e2e` job stops flaking under runner CPU contention — and nothing else. No application code, no
migration, no screen, no request path. `books.db`, covers, attachments and backups are all
untouched.

## What changed

- **The `e2e` CI job no longer fails intermittently.** `ci.yml`'s `e2e` job runs no backend, so
  every request Playwright didn't stub was a real connection refusal; `/api/item-types` and
  `/api/shelves` are fetched by nearly every screen, and GitHub's shared runners are
  CPU-constrained enough to expose the race that a 12-core workstation never showed.
  `frontend/e2e/console.ts`'s shared fixture now stubs both endpoints by default (a spec can
  still override its own stub — Playwright resolves the most-recently-registered route first),
  and `playwright.config.ts` retries twice in CI.
- **Still occasionally load-sensitive:** one test (`library.spec.ts`'s keyboard-guards/reduced-motion
  check) can still flake under heavy CPU contention; it isn't yet in `playwright.config.ts`'s
  `HEAVY_LIBRARY` serial set. Watched, not yet acted on — see the 2026-09-01 worklog entry.

## Why this release exists

Sprint 058 shipped the publish workflow and put `v1.5.3` on `ghcr.io/mauroibz/akasha`, but its
own acceptance criteria (AC4/AC5) require proving a real upgrade and a real rollback between
**two published versions** — and until this release, only one had ever gone through the
workflow. Rather than manufacture a version number for no reason, this release bundles the CI
fix that was already sitting on `main`, unreleased, and doubles as the second version that
proves the deployment line actually rolls forward and back. See DEC-121 for the full account,
including the version renumbering it forces on Sprints 059 and 060 (`v1.5.5` and `v1.5.6`,
formerly `v1.5.4` and `v1.5.5`).

## Upgrading

```bash
echo "AKASHA_VERSION=1.5.4" >> .env
docker compose pull
docker compose up -d
```

Nothing migrates and no data volume moves.
