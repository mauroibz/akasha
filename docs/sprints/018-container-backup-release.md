# Sprint 018 — Container, backup, and v1 release

**Status:** ready
**Depends on:** 017
**Roadmap revision:** 7

## Objective

Akasha runs on the ZimaBoard from a single non-root container, survives recreation with its data
intact, and can be backed up and restored from a drill that has actually been performed.

## Required context

1. `AGENTS.md`
2. `docs/specs/product-spec.md` section 8 (Deployment)
3. `docs/specs/technical-spec.md` section 2 (repository and runtime architecture), section 4
   (configuration), section 9 (security and data safety), section 11 (observability and
   operations), and section 10's container smoke-test requirement
4. `docs/decisions.md` DEC-014 (dependency locks), DEC-025 (verification requires using the
   application), DEC-036 (the projection migration `0007` must run on an existing database), and
   DEC-037 (the build now emits several chunks, not one)
5. Sprint 017 Outcome and `docs/agent/WORKFLOW.md`
6. `Dockerfile`, `compose.yaml`, `scripts/smoke_container.sh`, and `backend/src/book_tracker/main.py`
   (the static SPA mount and its path containment)

## Current implementation baseline

Re-derive at activation. As of Sprint 017's close: a `Dockerfile` and `compose.yaml` exist at the
repository root and `scripts/smoke_container.sh` runs in CI as its own job, but nothing in this
sprint's acceptance list has been verified against a running image — non-root, persistence across
recreation, read-only Calibre, healthcheck, or signal handling. No backup script exists. The
frontend now builds several chunks rather than one (DEC-037), so any image or proxy step that
assumed a single asset filename needs checking. Migration `0007` backfills every existing item
row, so it is the first migration in this project that does real work on the owner's data at
deploy time.

## Deliverables

- Multi-stage image: `node:22-alpine` builds the frontend, `python:3.12-slim` runs the app and
  serves `dist/` through the existing SPA mount. No Node in the final image. Non-root user,
  healthcheck, direct signal delivery.
- Compose: `${DATA_DIR:-./data}:/data`, `${CALIBRE_DIR}:/calibre:ro`, environment documented,
  LAN-only warning prominent in the file itself and not only in prose.
- Alembic on startup or as a documented deploy step, exercised against a database that predates
  `0007` so the backfill is observed rather than assumed.
- `scripts/backup.sh`: SQLite online backup (never a naive copy of a live WAL database), covers and
  import audit metadata archived, checksums written, retention enforced, `PRAGMA integrity_check`
  run. A host/NAS scheduler example, not a cron daemon inside the application container.
- A restore drill that is performed, not described: restore into an empty directory and confirm
  representative scores, notes, shelves and covers come back.
- Fresh-install and upgrade smoke tests; operator runbook and release notes.

## Acceptance criteria

1. The final image contains no Node runtime and runs as a non-root user.
2. `/data` persists the database and covers across `docker compose down && up`; `/calibre` is
   read-only in the mount and in code.
3. A backup taken from a running instance restores representative scores, notes, shelves and
   covers into an empty data directory.
4. Upgrading a database created before migration `0007` completes and leaves text sorting and
   accent-insensitive search working (DEC-036).
5. The LAN-only warning is prominent; nothing implies the application is safe to expose.
6. A clean-machine Compose smoke test passes. The v1 tag is created only if the owner asks.

## Required tests (TDD)

- Container: image builds, runs as non-root, healthcheck reports ready, SIGTERM stops it promptly,
  SPA routes and `/api` both answer, static assets are served for every emitted chunk.
- Persistence: data written through the API survives container recreation.
- Read-only: a write attempt against `/calibre` fails, in the mount and in code.
- Migration: a pre-`0007` database upgrades, backfills, and sorts accented titles correctly
  afterwards.
- Backup: `integrity_check` passes on the copy, checksums match, retention deletes the right files
  and keeps the rest, and a restore is verified by reading real values back.

## Verification

```bash
python scripts/validate_project.py
make format
make check
make test
cd frontend && npm run test:e2e -- --project=chromium
cd .. && make build
make smoke-container
git diff --check
```

Plus, recorded in the Outcome: the image size and user, the persistence and restore drills with
what was read back, and the pre-`0007` upgrade.

## Explicit non-scope

- No cross-provider metadata merging or cover choice. That is Sprint 019 and it is **gated**:
  DEC-035 approves an assessment, not an implementation.
- No authentication, no public exposure, no reverse-proxy configuration beyond documentation.

## Commit checkpoints

1. `build: multi-stage non-root image and compose mounts`
2. `feat: add online backup with checksums, retention and integrity check`
3. `docs: operator runbook, restore drill, and release notes`
4. `test: container smoke, persistence, and pre-0007 upgrade`
5. final `docs(sprint-018): close sprint and hand off`

## Risks and decisions to surface

- Whether migrations run at container start or as an explicit deploy step. Automatic is friendlier
  and riskier; `0007` rewrites every item row, which makes this a real question rather than a
  stylistic one.
- Backup destination and retention count, which are the owner's to choose.
- Whether the v1 tag is created in this sprint at all. Do not tag, publish, deploy or push unless
  asked.

## Outcome

_Not started. On completion record delivered behavior, commands and actual results, commit IDs,
deviations/decisions, and impact on every future sprint._
