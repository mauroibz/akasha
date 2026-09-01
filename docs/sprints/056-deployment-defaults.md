# Sprint 056 — The deployment defaults a home server needs

**Status:** completed
**Depends on:** 055

**Roadmap revision:** 30

## Objective

A first `docker compose up -d` on a machine that already runs other things lands on a port nothing
else wants, keeps its logs bounded, honours every knob the documentation promises, and survives a
slow first migration without declaring itself unhealthy.

No application behaviour changes. This sprint is the shipped configuration and the operator
documentation, and its gate is the container smoke test.

## Required context

- `compose.yaml`, `compose.bind-mounts.yaml`, `.env.example`, `Dockerfile`, `scripts/backup.sh`,
  `scripts/smoke_container.sh` — the whole surface this sprint changes.
- `docs/operations/runbook.md` — canonical operator documentation; several of its instructions are
  corrected here.
- `backend/src/book_tracker/config.py` — which settings exist, and which of them the container is
  currently able to receive.
- `README.md`'s configuration table, and `SECURITY.md`'s threat model.
- `docs/decisions.md`: DEC-039 (startup takes a pre-migration backup and refuses to migrate without
  one), DEC-040 (backups live outside the data volume), DEC-048 (the attachment cap is
  configuration, not code), DEC-075 (named volumes by default).

## Current implementation baseline

Measured 2026-09-01 at Sprint 055's closure commit, on Docker 29.5.2 / Compose v5.1.4.

`bash scripts/smoke_container.sh` **passes end to end from a clean build** — healthcheck, non-root,
no Node in the runtime, API persistence across recreation, every emitted chunk served, read-only
Calibre, an in-container restore, the named-volume restore drill, and a graceful SIGTERM in 0 s with
exit 143. The artifact is sound. Everything below is about what the shipped *configuration* carries.

| Observed | Where |
|---|---|
| Publishes `${AKASHA_PORT:-8000}`. 8000 is among the most contended ports on a machine that runs anything else. | `compose.yaml` |
| No `logging:` block, so Docker's `json-file` default applies and has **no size bound**. Uvicorn's access log is on — `CMD` passes no `--no-access-log` — and one library page is many requests. | `compose.yaml`, `Dockerfile` |
| Exactly five variables are passed to the container. `.env.example` documents `BOOK_TRACKER_ATTACHMENT_MAX_BYTES` and `BOOK_TRACKER_SQLITE_BUSY_TIMEOUT_MS`, and `config.py` carries `TMDB_READ_TOKEN`. **None of the three reaches the process in the supported deployment.** | `compose.yaml:18-23` vs `.env.example`, `config.py` |
| `--start-period=10s --interval=10s --retries=3` — about 40 s before `unhealthy`. A start with pending revisions takes a pre-migration backup first (DEC-039), which tars every cover. | `Dockerfile` |
| `image: akasha:local` is a fixed tag, so each rebuild orphans its predecessor as a dangling image and the runbook's rollback must rebuild from an old commit rather than start an image that already exists. | `compose.yaml`, `docs/operations/runbook.md` |
| `compose.bind-mounts.yaml` overrides `/data` **and** `/backups` together. Backups cannot be moved onto a second disk without also taking the sqlite file onto a bind mount — and a second disk is exactly what DEC-040's own reasoning asks for. | `compose.bind-mounts.yaml` |
| The nightly cron example writes to `/var/log/akasha-backup.log`, which is not writable on every host — several appliance distributions ship a read-only root filesystem. `BACKUP_RETENTION` is documented in `.env.example`, but `scripts/backup.sh` reads it from the process environment and cron does not source `.env`, so the documented value is silently ignored. | `docs/operations/runbook.md`, `scripts/backup.sh` |
| "Trusted LAN" is stated everywhere and **overlay networks are never mentioned.** A host joined to a VPN or mesh network (WireGuard, Tailscale, ZeroTier, and the like) carries an extra interface, and `AKASHA_BIND=0.0.0.0` publishes on that one too — so an unauthenticated port becomes reachable from outside the building without anyone having forwarded anything. | `SECURITY.md`, `compose.yaml`, `docs/operations/runbook.md` |

## Deliverables

### 1. A published port that does not collide

The default published port becomes **4441**. The container keeps listening on 8000 internally, so
the healthcheck, the Dockerfile and every in-container path are untouched; only the host side of the
mapping moves. Update `compose.yaml`, `.env.example`, `README.md` (quick start and configuration
table) and `docs/operations/runbook.md` together — a stale `localhost:8000` in any of them is the
defect this deliverable exists to prevent.

**This is a breaking change for an existing install that never set `AKASHA_PORT`.** It must be named
as such in the release notes, with the one-line remedy: put `AKASHA_PORT=8000` in `.env` to keep the
old address.

### 2. Bounded logs

Add a `logging:` block to the service — `json-file` with a size cap and a file count. Anything in the
region of 10 MiB × 5 is defensible; pick a number, write the reason beside it, and make it
overridable by environment variable in the same shape as the rest of the file.

The point is not the number. It is that a home server's disk cannot be the thing that discovers the
logs are unbounded, and that this application's disk is often shared with whatever else the machine
is for.

### 3. Every documented setting reaches the process

`BOOK_TRACKER_ATTACHMENT_MAX_BYTES`, `BOOK_TRACKER_SQLITE_BUSY_TIMEOUT_MS` and `TMDB_READ_TOKEN`
become explicit passthroughs in `compose.yaml`'s `environment:` block, each with a default that
preserves today's behaviour. Document `TMDB_READ_TOKEN` in `.env.example` and in `README.md`'s
configuration table, where it has never appeared.

**Do not reach for `env_file: .env`.** It would inject `BOOK_TRACKER_ENVIRONMENT=development` from
the shipped example straight into the container and quietly disable the production guard that makes
`USER_AGENT_CONTACT` mandatory. Explicit passthrough, one variable per line, is the contract: the
compose file stays the list of what the container is allowed to receive.

Audit `config.py` against `compose.yaml` while here, and either pass a setting through or delete its
documentation. A knob that does nothing is worse than an absent one.

### 4. Room for a first migration

Raise the healthcheck's `--start-period` to a value that admits a pre-migration backup and a
migration on a slow disk — 60 s is the recommendation. Interval and retries stay as they are.

Write the reason into the Dockerfile beside it: the start period is sized by the slowest legitimate
start, which is DEC-039's backup plus a migration that rewrites every row, not by a warm restart.

### 5. A rollback that starts an image instead of rebuilding one

`image: akasha:${AKASHA_VERSION:-local}`, so a build can be tagged with the version it came from and
a rollback is a variable rather than a rebuild from an old commit. Update the runbook's rollback and
upgrade sections to match.

This is deliberately the smaller half of the problem — Sprint 057 removes the rebuild entirely — but
it is worth having independently, and it is the shape 057 builds on.

### 6. Backups on their own disk, without moving the database

A second overlay — `compose.backups-host.yaml` is the obvious name — that binds **only** `/backups`
to a host path, leaving `/data` as the named volume `compose.yaml` gives it. Document it in the
runbook beside the existing bind-mount section, including the one thing it costs: the host directory
must exist and be owned by uid 10001 before the first start, which needs one privileged command,
stated exactly once with its expected result.

DEC-040 says a backup on the same disk as the database does not survive losing that disk. On the
default named volumes both land under the same Docker data root, so today the shipped configuration
cannot satisfy its own decision without also giving up DEC-075. This closes that gap.

### 7. The operator runbook says things that are true on more than one host

- The cron example writes its log somewhere the operator chooses, with a note that a host with a
  read-only root filesystem needs a writable path — not `/var/log`.
- `BACKUP_RETENTION` is set in the crontab line or the environment, not in `.env`; say so where the
  variable is documented, in both `.env.example` and the runbook.
- The rollback and restore recipes carry the `AKASHA_VERSION` tag from deliverable 5.

### 8. The exposure boundary names overlay networks

`SECURITY.md`, `compose.yaml`'s header comment and the runbook's reverse-proxy section all say "LAN
only". Add the sentence they are missing: a host that has joined a VPN or mesh network has an extra
interface, `0.0.0.0` publishes on it too, and the way to exclude it is to bind `AKASHA_BIND` to one
address rather than to everything. Keep it provider-neutral — the property belongs to overlay
networks generally, not to any particular one.

This changes no code and no default. `AKASHA_BIND` already does the job; what is missing is the
sentence telling an operator that it is a decision they are making.

### 9. Release notes for v1.5.1

`docs/operations/release-notes-v1.5.1.md`, in the shape of the five that precede it, leading with the
port change because it is the one thing an existing install must act on.

## Acceptance criteria

1. With no `.env` override, `docker compose config` shows the host side of the port mapping as
   **4441** and the container side unchanged at 8000; `AKASHA_PORT=8000` restores the old mapping.
2. No file in the repository instructs a reader to open `localhost:8000` unless it is describing the
   development server.
3. A running container reports a bounded `LogConfig` under `docker inspect` — a `max-size` and a
   `max-file`, not the unbounded default.
4. A value set for `BOOK_TRACKER_ATTACHMENT_MAX_BYTES` in `.env` changes what the running
   application accepts: an attachment above the configured cap is refused with the documented typed
   error, and one below it succeeds. Proved through the API against a running container, not by
   reading the compose file.
5. `TMDB_READ_TOKEN` and `BOOK_TRACKER_SQLITE_BUSY_TIMEOUT_MS` are visible in the container's
   environment when set in `.env`, and absent when not.
6. `BOOK_TRACKER_ENVIRONMENT` is **not** injected from `.env` into the container: a `.env` copied
   verbatim from `.env.example` still starts a container whose environment is `production`, and
   removing `USER_AGENT_CONTACT` still refuses to start.
7. The healthcheck's start period admits a start that takes longer than 40 s; the container reaches
   `healthy` in the smoke test exactly as it does today.
8. `docker compose -f compose.yaml -f compose.backups-host.yaml up -d` puts `/backups` on the host
   path while `/data` remains the named volume, and a backup written through it lands on the host
   path and verifies.
9. `AKASHA_VERSION=x.y.z docker compose build` tags the image `akasha:x.y.z`, and `up -d` with the
   same variable starts that tag without rebuilding.
10. `SECURITY.md`, `compose.yaml` and the runbook each state that an overlay-network interface is
    reachable under `AKASHA_BIND=0.0.0.0`.
11. `python scripts/validate_project.py` passes, including its link check across every changed
    document.

## Required tests (TDD)

The gate is `scripts/smoke_container.sh`, because the thing under test is the deployed artifact and
its mounts. Extend it, keeping its existing property that it touches nothing the owner owns:

- **The attachment cap arrives.** Start with a deliberately small `BOOK_TRACKER_ATTACHMENT_MAX_BYTES`,
  POST an attachment above it, assert the typed 413; POST one below it, assert it is stored. This is
  the honest proof for deliverable 3 — it exercises a value travelling from `.env` through compose
  into a setting the application reads at runtime.
- **`BOOK_TRACKER_ENVIRONMENT` does not leak.** Assert the running container's environment is
  `production` with a `.env` that sets `development`.
- **The log configuration is bounded.** Assert `docker inspect`'s `HostConfig.LogConfig` carries a
  `max-size`.
- **The port default.** Assert against `docker compose config` with `AKASHA_PORT` unset, rather than
  by binding 4441 on the test machine — the smoke test picks a free random port on purpose and must
  keep doing so.
- **The backups-only overlay.** Bring the stack up with both files against a throwaway host
  directory, write a backup, verify it, and assert `/data` is still a named volume.

No backend or frontend unit tests are owed: no Python or TypeScript changes in this sprint. If any
does change, that is a deviation worth recording, and it pulls `make test` back into the gate.

## Verification

```bash
python scripts/validate_project.py
make check
make smoke-container
docker compose config                 # port mapping, environment block, image tag
AKASHA_VERSION=1.5.1 docker compose build && docker images akasha
```

**This sprint declares a narrowed gate.** Its diff is `compose*.yaml`, `Dockerfile`, `.env.example`,
`scripts/smoke_container.sh` and documentation — nothing under `backend/src/`, `frontend/src/`,
`backend/tests/`, `backend/alembic/versions/` or either lockfile. Under
`docs/agent/TESTING.md`'s "Gate scope by what changed" it therefore owes the three commands above and
**does not owe `make test` or `npm run test:e2e`**: no Python or TypeScript those suites execute has
changed, and no screen or request path has moved.

`make smoke-container` is the gate, not a supplement to one. It builds the image and exercises the
documented deployment with its mounts, which is the only thing that can prove any of this sprint's
criteria.

The narrowing is a claim about the diff, so prove it: paste `git diff --stat` at the freeze point
into the Outcome beside the declaration. **One file under `backend/src/` withdraws the narrowing and
the full gate is owed** — including a one-line fix that felt too small to mention.

## Explicit non-scope

- **Authentication.** Unchanged, and still not on the roadmap. This sprint sharpens the description
  of the boundary; it does not move it.
- **Publishing an image to a registry**, and every question of pull-based upgrades — Sprint 057.
- **Anything about what blocks the event loop** — Sprint 058.
- **Backup retention, pruning and disk-space guards** — Sprint 059. This sprint may move where
  backups are written; it does not change what is written or when anything is deleted.
- Reverse-proxy configuration, TLS, and hostnames. The runbook's existing paragraph stands.

## Commit checkpoints

1. `[CHANGE] Publish on 4441 by default`
2. `[ADD] Bound the container's logs`
3. `[FIX] Pass the documented settings through to the process`
4. `[CHANGE] Give a first migration room before it is called unhealthy`
5. `[ADD] Backups on their own disk without moving the database`
6. `[DOCS] Say that an overlay network is a reachable interface`
7. `[DOCS] Correct the operator runbook and add v1.5.1 release notes`
8. `[DOCS] Close sprint 056 and hand off`

## Risks and decisions to surface

- **Changing a default port breaks an existing install that never set one.** That is the cost of the
  fix, it is one line of `.env` to undo, and it is much cheaper now than after the port is in
  somebody's bookmarks and reverse proxy. Lead the release notes with it.
- **The env-passthrough list is the security boundary of the compose file.** Every variable added is
  one the container may receive. `env_file:` would hand it the whole file, including the example's
  `BOOK_TRACKER_ENVIRONMENT=development`, which turns off the production guard on
  `USER_AGENT_CONTACT`. Acceptance criterion 6 exists to keep a later session from taking that
  shortcut.
- **Deliverable 6 introduces a third compose file.** Three overlays is close to the point where the
  set needs a table in the runbook rather than a paragraph. Write the table.
- The privileged `chown` in deliverable 6 is the only step in the whole deployment that needs root.
  If a way is found to avoid it that does not run the application as root, prefer it and record why;
  otherwise document it as one command with its expected result.

## Outcome

Completed 2026-09-01, same day, one session. All nine deliverables; no application code touched.

**Narrowed gate — held.** `git diff --stat` at the freeze point (`adc4de4..HEAD`) is
`compose.yaml`, `compose.backups-host.yaml`, `Dockerfile`, `.env.example`, `README.md`,
`SECURITY.md`, `scripts/smoke_container.sh` and documentation only — nothing under
`backend/src/`, `frontend/src/`, `backend/tests/`, `frontend/` tests,
`backend/alembic/versions/`, `uv.lock` or `package-lock.json`:

    .env.example 49 +-- | Dockerfile 9 +- | README.md 19 +- | SECURITY.md 5 + | compose.backups-host.yaml 32 +
    compose.yaml 55 +- | docs/README.md 2 +- | release-notes-v1.5.1.md 80 + | runbook.md 93 +--
    state.json 8 +- | 056 sprint file 2 +- | smoke_container.sh 229 +-

**Verification, all green on the final frozen tree:**

- `bash scripts/smoke_container.sh` — **exit 0**, three times this session (RED observed first at
  the port assertion; then two GREEN runs on intermediate states; final run on the frozen tree
  after the commit slicing, all 20 steps). The smoke test was extended with the sprint's five
  required properties and stays hermetic: `COMPOSE_ENV_FILES` points every compose call at
  throwaway env files, so the owner's real `.env` never reaches a run and the random-port
  property is kept.
- `python scripts/validate_project.py` — passed after every slice.
- `make check` — green (ruff, mypy, tsc, OpenAPI drift, validator).
- `docker compose config` — the port default and the environment block asserted resolved
  inside the smoke test (4441 default, `AKASHA_PORT=8000` restore, three pass-throughs
  present-with-value/absent-when-unset); the owner's real `.env` resolves to their own
  overrides as designed.
- `AKASHA_VERSION=1.5.1 docker compose build && docker images akasha` — tags `akasha:1.5.1`.
- `make test` and `npm run test:e2e` — **not owed** under the narrowed gate; no Python or
  TypeScript those suites execute changed. CI's `checks`/`e2e` jobs still run them per push.

**Acceptance criteria, each verified:**

1. Port default — asserted against `docker compose config` with the variable unset: published
   4441, target 8000; `AKASHA_PORT=8000` restores 8000. Never bound 4441 on the test machine.
2. No non-development `localhost:8000` — grep across the repo leaves only the two dev-server
   mentions (CONTRIBUTING.md, README dev section) and the in-container side of the mapping.
3. Bounded logs — `docker inspect`'s `HostConfig.LogConfig` carries `max-size: 10m`,
   `max-file: 5`; overridable via `AKASHA_LOG_MAX_SIZE`/`AKASHA_LOG_MAX_FILE`.
4. Attachment cap travels — with `BOOK_TRACKER_ATTACHMENT_MAX_BYTES=1024` in the env file, a
   2048-byte POST to `/api/items/{id}/attachments` returns 413 with
   `error.code == "attachment_too_large"` and `"...limited to 1024 bytes"`; a 5-byte upload
   stores and reads back (filename, byte_size 5). Proved through the API against the running
   container.
5. `TMDB_READ_TOKEN`/`BOOK_TRACKER_SQLITE_BUSY_TIMEOUT_MS` — present with exactly the sent
   values when set in the env file; **absent from the process environment entirely** when unset
   (bare list-form pass-throughs, which omit rather than pass empty strings).
6. `BOOK_TRACKER_ENVIRONMENT` does not leak — a `.env` copied verbatim from `.env.example`
   (its `development` line included) still starts a container whose environment is `production`;
   `env -u USER_AGENT_CONTACT` with the example-minus-contact file refuses to start, names
   `USER_AGENT_CONTACT` in the error, and leaves the running container undisturbed.
7. Start period — `--start-period=60s` with the reasoning written beside it in the Dockerfile;
   the container reached `healthy` in the smoke test exactly as before.
8. Backups-only overlay — both compose files up against a throwaway host directory: backup
   written through it and verified on the host path, `/data` still a named volume (asserted
   against the resolved config). The `chown` was stood in for with 0777 on the throwaway
   directory (the test must not use root); the mount topology is what was under test.
9. Version tag — `AKASHA_VERSION=<tag> docker compose build` tags `akasha:<tag>`;
   `up -d --no-build` with the same variable starts that tag (asserted via
   `Config.Image` of the running container).
10. Overlay-network sentence — present in `SECURITY.md`, `compose.yaml`'s header and the
    runbook's reverse-proxy section, provider-neutral.
11. Validator passes including the link check (release notes registered in docs/README.md).

**Commits:** d583f6a (4441, state flip rides it), cca3969 (logs), 8518c2b (pass-throughs),
14d6cf4 (start period), 33ac401 (backups overlay), 09fbf55 (version tag), 894430c (overlay
networks), 1266114 (runbook + release notes), 4d36025 (restored slicing-dropped content).

**Deviations and decisions:**

- **Deliverable 5 (the version tag) had no named checkpoint.** It shipped as its own
  `[CHANGE]` commit (09fbf55) between checkpoints 5 and 6, recorded here; the checkpoint list
  in the sprint file names seven implementation commits and this is an eighth of the same kind.
- **The smoke test's cleanup gained a throwaway alpine container** — the overlay drill's host
  backups directory is written by the container as uid 10001, which the host cannot `rm`.
  The cleanup empties it as that uid before `rm -rf` of the workdir. Docker is used for
  container management only, per the house rule.
- **The config.py audit (deliverable 3) found three more dead knobs**: `BOOK_TRACKER_DATA_DIR`,
  `BOOK_TRACKER_CALIBRE_DIR` and `BOOK_TRACKER_DATABASE_URL` were documented in `.env.example`
  but never reach the container (its paths are fixed by the image and mounts). Their
  documentation was replaced with a sentence saying exactly that, rather than kept as knobs
  that do nothing.
- **`GOOGLE_BOOKS_API_KEY` keeps its map-form entry** (`${GOOGLE_BOOKS_API_KEY:-}`): it is a
  string setting where empty-means-absent is today's behaviour, so the always-present form is
  the compatibility-preserving one. The two integer settings and the token use the bare form.
- **The environment block moved from map form to list form** so the three pass-throughs could
  be bare entries; `USER_AGENT_CONTACT`'s `:?` refusal behaviour is preserved verbatim.
- **The example `.env`'s `BOOK_TRACKER_SQLITE_BUSY_TIMEOUT_MS=5000` is an active line and does
  reach the container** (5000 is also the default, so nothing changes); the smoke test asserts
  it rather than assuming absence. `BOOK_TRACKER_ENVIRONMENT` and the commented cap/token do
  not reach it.

**Impact on future sprints:** Sprint 057 builds on `akasha:${AKASHA_VERSION:-local}` exactly as
its file assumes; its "compose carries build:." trap paragraph is unaffected (still true). The
runbook's rollback/restore recipes now carry `AKASHA_VERSION`, which 057's publishing flow will
supersede by pointing at a registry. No sprint 058/059 assumption changed.

**Release notes:** `docs/operations/release-notes-v1.5.1.md`, leading with the port change.
Not tagged, not pushed — the owner's call, as with v1.5.0.
