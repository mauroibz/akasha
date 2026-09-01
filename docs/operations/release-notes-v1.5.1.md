# Akasha v1.5.1 — release notes

The deployment-defaults release: configuration and operator documentation only, from
Sprint 056. Nothing inside the application changed — no migration, no screen, no request
path — and the version surfaces (`backend/pyproject.toml`, `frontend/package.json`, the
FastAPI version, the generated OpenAPI contract) stay at `1.5.0`, because a patch release
of configuration carries no new API. The image and the data handling are unchanged; what
changed is what the shipped configuration does out of the box.

## Read this first if you already run Akasha

**The published port moved from 8000 to 4441.** This is the one change that breaks an
existing install that never set `AKASHA_PORT`: after `docker compose up -d --build`, the
address you had bookmarked stops answering. The remedy is one line of `.env`:

```
AKASHA_PORT=8000
```

Everything else in this release is either a fix to a default you never noticed or a
correction to documentation you can read at leisure.

## What's new since v1.5.0

- **The port default is 4441.** 8000 is among the most contended ports on a machine that
  runs anything else. The container still listens on 8000 internally; only the host side
  of the mapping moved.
- **Container logs are bounded.** Docker's `json-file` default has no size limit, and the
  access log is on. The service now ships a `logging:` block — 10 MiB × 5 files, a 50 MiB
  ceiling — overridable with `AKASHA_LOG_MAX_SIZE` and `AKASHA_LOG_MAX_FILE`.
- **Every documented setting now reaches the process.** `BOOK_TRACKER_ATTACHMENT_MAX_BYTES`,
  `BOOK_TRACKER_SQLITE_BUSY_TIMEOUT_MS` and `TMDB_READ_TOKEN` are explicit pass-throughs in
  `compose.yaml`. A value set in `.env` is now honoured, and unset settings stay absent from
  the container rather than arriving as something the application has to interpret.
  `TMDB_READ_TOKEN` is documented for the first time, in `.env.example` and the README's
  configuration table.
- **The healthcheck tolerates a slow first start.** The start period grows from 10 s to 60 s:
  a start with pending revisions takes a pre-migration backup first — one that tars every
  cover — and then a migration that may rewrite every row. On a slow disk that is minutes,
  and the container used to be declared unhealthy while doing exactly what it was told to.
- **A rollback starts an image instead of rebuilding one.** `image:` is now
  `akasha:${AKASHA_VERSION:-local}`: build with `AKASHA_VERSION=1.5.1` and the tag exists to
  roll back to. The runbook's rollback and restore recipes carry the variable.
- **Backups can live on their own disk without moving the database.** A third opt-in overlay,
  `compose.backups-host.yaml`, binds only `/backups` to a host path and leaves `/data` the
  named volume it is by default — the two-disk shape the backup decision has asked for since
  it was made, which the bind-mount tier previously made you give up the named-volume default
  to get. The runbook documents it, including the one `chown` it needs.
- **The exposure boundary names overlay networks.** A host joined to a VPN or mesh network
  carries an extra interface, and `AKASHA_BIND=0.0.0.0` publishes on that one too — an
  unauthenticated port reachable from outside the building without anyone having forwarded
  anything. `SECURITY.md`, `compose.yaml`'s header and the runbook now all say so, and the
  remedy (bind `AKASHA_BIND` to one address) was already there.
- **Operator documentation corrections.** The nightly-backup cron example no longer writes its
  log to `/var/log`, which is not writable on every host; and `BACKUP_RETENTION` is now
  documented where it works — the crontab line or the environment, never `.env`, which cron
  does not source and the backup script therefore silently ignored.

## Upgrading

Pull and rebuild:

```bash
git pull
AKASHA_VERSION=1.5.1 docker compose up -d --build
```

Nothing migrates. If you had set none of the variables above, the two visible differences
are the port (see the top of these notes) and bounded logs. If you want your install pinned
to a version tag from now on, keep `AKASHA_VERSION` in `.env` — every later
`docker compose` command reads it, and the next rollback becomes a variable change rather
than a rebuild from an old commit.

## What this release deliberately does not do

- **Authentication.** Unchanged, and still not on the roadmap. The overlay-network sentence
  sharpens the description of the boundary; it does not move it.
- **A published image.** Compose still builds locally; an image you pull is the next release.
- **Backup retention changes, pruning, or disk-space guards.** Backups can now be written to
  a different disk; what is written, and when anything is deleted, is unchanged.
