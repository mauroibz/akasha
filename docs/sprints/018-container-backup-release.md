# Sprint 018 — Container, backup, and v1 release

**Status:** completed
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

**Completed 2026-08-13.** Akasha runs on one non-root container, keeps its data across recreation,
and has a backup that was restored from rather than merely written.

### Delivered

- `b04b6bc` — Compose gained the read-only Calibre mount that had been commented out since Sprint
  008 with a note saying Sprint 008 would enable it, plus a `${BACKUP_DIR:-./backups}:/backups`
  mount kept outside the data volume. `backup_dir` derives as a sibling of `data_dir`, so `/data`
  and `/backups` in the container and `./data` and `./backups` in a checkout both fall out of one
  rule. The LAN-only warning moved from a Compose label nobody reads to the top of the file.
  Dockerfile gained `STOPSIGNAL SIGTERM` and a `/backups` directory owned by uid 10001.
- `2c8d790` — `book_tracker/backup.py` with `create_backup`, `verify_backup`, `restore_backup` and
  label-scoped `enforce_retention`, exposed as the `akasha-backup` console script and driven from
  the host by `scripts/backup.sh`. Python rather than shell so it ships in the image and runs under
  mypy, ruff and pytest.
- `319b3c6` — Startup takes an online backup before applying pending migrations and refuses to
  migrate if it cannot (DEC-039). Fresh databases are skipped. `migrations.upgrade` accepts a
  revision and `pending_revisions` was added.
- `98a11d0` — `scripts/smoke_container.sh` rewritten to drive `docker compose` against the real
  API. It had been writing to `schema_probe`, the placeholder table Sprint 001 created and nothing
  has used since.
- `8de2dbc` — Three defects the walkthrough found, below.
- `1555e7a` — Operator runbook, v1 release notes, DEC-039/040/041, technical-spec section 11 and
  README brought in line.

### Verified

- **AC1** — image 242 MB, `Config.User` 10001:10001, `command -v node` finds nothing. Asserted in
  `make smoke-container`.
- **AC2** — an entry written through `POST /api/entries`, scored and annotated, read back
  identically after `docker compose down && docker compose up -d`. `touch /calibre/breakin` fails
  at the mount, and `CalibreAdapter` reads the same mount with `query_only` on.
- **AC3** — walkthrough drill: two real books added through the UI in the container, scored 8 and
  9, one note each, one on a shelf, both with provider covers. Backup taken from the running
  instance (`{"covers": 2, "entries": 2, "items": 2, "shelves": 1}`), the data directory then
  deleted outright, restored into an empty one, stack restarted. Both scores, both notes, the
  shelf membership and both cover files came back; `/api/items/1/cover` and `/2/cover` served 7772
  and 29477 bytes.
- **AC4** — a database seeded at `0006_job_error_code` with accented rows, started under the
  container: exactly one `pre-migration-*` backup at revision `0006`, then head. Sorting returned
  `Ávila, Ébano, Zurita` and `q=avila` matched `Ávila`, in the API and in the UI.
- **AC5** — LAN-only warning is the first thing in `compose.yaml`, repeated in `.env.example`, the
  README, the runbook and the release notes.
- **AC6** — `make smoke-container` passes end to end. **No v1 tag was created**, per the owner.
- Gates: validator, `make check`, `make test` backend **186** / frontend **74**, Playwright **75
  passed / 2 skipped** across both projects, `make build` with no chunk-size warning,
  `git diff --check` clean.

### Three defects found by the walkthrough, none by the tests

- **The production bundle rendered a blank page**, and had since Sprint 017. DEC-037's
  `manualChunks` object form assigns only the exact modules named and leaves their transitive
  runtime unassigned, so React was spread across chunks that imported each other and the entry
  threw `Cannot read properties of undefined (reading 'createContext')`. Nothing caught it because
  Playwright runs against the dev server, which does not chunk. Fixed by matching resolved package
  names with a fall-through vendor chunk, and guarded by a second Playwright project that loads a
  real build (DEC-041). Entry chunk 194 kB to 36 kB.
- **The pre-migration backup ran once per restart.** `restart: unless-stopped` plus a migration
  that kept failing wrote ten copies of the same database in ninety seconds, and nightly retention
  deliberately never prunes pre-migration backups. Now taken once per revision.
- **`akasha-backup restore` could not run without `USER_AGENT_CONTACT`**, because
  `book_tracker/__init__` imported `main`, which built the FastAPI app at import. That is exactly
  the variable a bare machine being restored onto has not set. The package init is now empty.

### Deviations

- **A sixth checkpoint was added** for the pre-migration backup (`319b3c6`); the sprint file listed
  five and the owner chose the guarded-automatic option during planning.
- **Documentation was written after the tests**, not before them as the checkpoint order implied,
  so the runbook could record what the drills actually did rather than what they were expected to.
- The Calibre mount default is `${CALIBRE_DIR:-./calibre}`; the sprint file wrote `${CALIBRE_DIR}`
  with no default, which fails Compose interpolation for anyone without a Calibre library.

### Impact on Sprint 019

_[Roadmap revision 8 renumbered this sprint: the metadata-completeness work described below
is now Sprint 020, and Sprint 019 is post-v1 polish. Text left as written — see DEC-042.]_

Sprint 019 Phase A is an assessment and inherits a working deployment plus `scripts/backup.sh`, so
it can measure against a container rather than a dev server. Two observations it already owns were
seen again during this walkthrough: a provider "image not available" placeholder stored as a real
cover, and edition choice picking a 2024 reprint of *Pedro Páramo* over the 1955 original.
