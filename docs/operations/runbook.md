# Operator runbook

Everything here has been performed against a running container, not written from
the source. Commands assume the repository checked out on the host and `docker`
with the Compose plugin installed; nothing else is needed.

**Akasha v1 has no authentication.** Anyone who can reach the port can read and
change every rating, note and shelf. Keep it on a trusted LAN.

## First install

```bash
cp .env.example .env      # then edit it
mkdir -p calibre
docker compose up -d
```

`USER_AGENT_CONTACT` is required and startup refuses without it: Open Library
asks callers to identify themselves. `GOOGLE_BOOKS_API_KEY` is optional; without
it search runs on Open Library alone and Spanish-language coverage is poor.

`data` and `backups` are named Docker volumes by default (DEC-075), seeded from
the image with the right ownership already on them — there is nothing to `chown`.
Want either as a real host directory instead (a NAS-backed `BACKUP_DIR`, direct
host access to the sqlite file)? See "Bind-mounting data and backups" below.

Check it came up:

```bash
docker compose ps                     # State should be "healthy"
curl -fsS http://localhost:4441/api/health/ready
```

The published port defaults to **4441**. An install that upgraded from an
earlier version and never set a port: put `AKASHA_PORT=8000` in `.env` to keep
the old address.

## Upgrading

```bash
docker compose pull
docker compose up -d
```

No `git pull`, no toolchain, no build: `docker compose pull` fetches the tag
`AKASHA_VERSION` names from `ghcr.io/mauroibz/akasha` — CI publishes it there
on every version tag — and `up -d` recreates the container from it. Pin the
version rather than trailing `latest`, so an upgrade is a decision you make
instead of one that happens to you on the next restart:

```bash
echo "AKASHA_VERSION=1.5.3" >> .env
docker compose pull
docker compose up -d
```

`AKASHA_VERSION` is read by every later `docker compose` command too — `down`,
`logs`, `scripts/backup.sh` — so keep it in `.env` once it is set. `latest`
always resolves to whatever the newest published tag is, major versions
included; a pinned version is the one you actually reviewed.

Building from source is still available — a fork, a local patch, or an
architecture other than the published `linux/amd64` — through the local-build
overlay:

```bash
git pull
docker compose -f compose.yaml -f compose.build.yaml up -d --build
```

The Dockerfile's two base images are pinned by digest, so a local build never
picks up an unreviewed change either — see the comment above its first `FROM`
line for the one-command refresh procedure, or let Dependabot's `docker`
ecosystem propose the update as a pull request.

Migrations run automatically at startup, and startup takes an online backup
first whenever there are pending revisions (DEC-039). That copy lands in
`/backups/pre-migration-<timestamp>/` and is **never** removed by nightly
retention, because it is the rollback point for that upgrade. If the backup
cannot be written the application refuses to migrate and exits, which is
deliberate: an unprotected schema rewrite on a database full of your own ratings
is worse than downtime.

Migration `0007` rewrites every row in `items`. On a library of a few thousand
books it takes well under a second; the log line to look for is
`pre_migration_backup_written`.

## Rolling back

Alembic here is forward-only, so a rollback is a restore plus an older image.
Published images keep every prior tag available, so the image side of a
rollback is a pull rather than a rebuild.

Docker has no way to rename a volume, so this restores into a fresh one and
flips which volume Compose points at, rather than swapping directories on the
host. The volume `data` is currently attached to is left untouched — it's the
rollback point for the rollback, if this ever needs undoing.

```bash
docker compose down
docker run --rm -v akasha_backups:/backups:ro alpine ls /backups   # find the pre-migration copy
docker volume create akasha_data_rollback
docker run --rm --user 10001 \
  -v akasha_backups:/backups:ro -v akasha_data_rollback:/data \
  ghcr.io/mauroibz/akasha:<the-previous-version> akasha-backup restore /backups/pre-migration-<stamp> --into /data
echo "AKASHA_DATA_VOLUME=akasha_data_rollback" >> .env
echo "AKASHA_VERSION=<the-previous-version>" >> .env   # the image that was running before
docker compose up -d
```

`docker run` pulls an image it does not already have, so naming the previous
version is enough — there is nothing to rebuild. If the previous version
predates the published image (v1.5.2 and earlier), fall back to the old
procedure for that one rollback only — `git checkout <previous-tag-or-commit>
&& docker compose -f compose.yaml -f compose.build.yaml up -d --build`.

On `compose.bind-mounts.yaml` (a real `backups/` directory), replace both
`-v akasha_backups:/backups:ro` above with `-v "$PWD/backups:/backups:ro"`, and
`ls backups/` works directly — `akasha-backup restore` itself doesn't care
which kind of mount either side is.

Restore refuses to write into a directory that is not empty, so it cannot
silently overwrite a database you meant to keep. To undo the rollback later,
remove the `AKASHA_DATA_VOLUME` line from `.env` and `docker compose up -d`
again — the volume it names is still there, untouched.

## Nightly backups

Schedule from the host, not from inside the container — the application is one
process and is not a cron daemon.

```cron
15 3 * * *  cd /srv/akasha && BACKUP_RETENTION=7 ./scripts/backup.sh >> backups/akasha-backup.log 2>&1
```

Write the log somewhere you choose — the example uses the checkout's own
`backups/` directory because a host with a read-only root filesystem (several
appliance distributions ship one) has no writable `/var/log`.

`BACKUP_RETENTION` is read by `scripts/backup.sh` from the **process
environment**, and cron does not source `.env`: a value in `.env` is silently
ignored. Set it in the crontab line, as above, or in the environment that
launches cron — the same is true wherever that variable is documented,
including `.env.example`.

`scripts/backup.sh` requires the stack to be running: an online backup reads a
live database through SQLite's backup API rather than copying a WAL file out
from under a writer. Each run writes a directory containing `books.db`,
`covers.tar.gz`, `imports.tar.gz`, `manifest.json` and `checksums.sha256`,
verifies its own output with `PRAGMA integrity_check`, and then deletes the
oldest `nightly-` backups beyond `BACKUP_RETENTION` (default 7).

Attached files are carried as **hardlinks**, in an `attachments/` directory
alongside the tarballs, and the manifest lists each blob's digest and size.
They are not tarred and not compressed: an epub is already a ZIP, so gzip
measured a ratio of 1.0003 on them while costing ten times the runtime, and a
tar shares no bytes with the one written the night before (DEC-047). Sharing is
why seven nights of attachments cost about one copy instead of seven. Deleting
an expired backup only decrements a link count, so it can never take a blob
another backup still needs — and a backup keeps an attachment recoverable after
you delete it from the library, which is the point of having one.

If `BACKUP_DIR` is on a different filesystem from the data volume — which is the
normal Compose setup — blobs are linked from the previous backup instead, so
sharing still holds. A copy is only paid on the very first backup to a fresh
disk.

Backups live on their own mount, outside the data volume (DEC-040). Point
`BACKUP_DIR` at a NAS share if you have one; a backup on the same disk as the
database does not survive losing that disk.

Check one by hand at any time:

```bash
docker compose exec akasha akasha-backup verify /backups/nightly-<stamp>
```

## Reclaiming attachment space

A blob whose last row goes away is removed with it. A few routes leave one behind
anyway — an item deleted outside the application, a crash between writing the file
and recording the row — and nothing else collects those. This finds them:

```bash
docker compose exec akasha akasha-attachments reclaim
```

It **reports and removes nothing** by default: what it would delete, what it kept
because a row still points at it, and anything under `attachments/` it did not
put there and will not touch. Read that list, then run it again to act on it:

```bash
docker compose exec akasha akasha-attachments reclaim --apply
```

Safe to run at any time, including while the stack is serving. A blob written in
the last hour is never touched, which is what keeps it away from an upload whose
file has landed but whose database row has not been committed yet; pass
`--grace-seconds` if you ever need to narrow that window. A blob a backup has
linked survives this — the backup holds its own reference to the same inode, so
reclaiming the live copy cannot reach the bytes.

There is no schedule for it and it deliberately does not run itself. It deletes
by inference, and inference belongs behind a person.

## Restoring

As with a rollback, this restores into a fresh volume and flips which one
Compose points at, rather than swapping directories on the host — the volume
`data` is currently attached to is left alone.

```bash
docker compose down
docker volume create akasha_data_restored
docker run --rm --user 10001 \
  -v akasha_backups:/backups:ro -v akasha_data_restored:/data \
  ghcr.io/mauroibz/akasha:${AKASHA_VERSION:-latest} akasha-backup restore /backups/nightly-<stamp> --into /data
echo "AKASHA_DATA_VOLUME=akasha_data_restored" >> .env
docker compose up -d
```

On `compose.bind-mounts.yaml`, replace `-v akasha_backups:/backups:ro` above
with `-v "$PWD/backups:/backups:ro"` — `akasha-backup restore` doesn't care
which kind of mount either side is.

Restore verifies every checksum and re-runs `integrity_check` before writing
anything. It needs no configuration at all — not even `USER_AGENT_CONTACT` —
because the restore path deliberately does not build the application. To go
back, remove the `AKASHA_DATA_VOLUME` line from `.env` and `docker compose up
-d` again — the old volume is still there.

### Bind-mounting data and backups

Prefer `./data` and `./backups` as real host directories — a NAS-backed
`BACKUP_DIR`, direct host access to the sqlite file? Opt into
`compose.bind-mounts.yaml`, which brings back the pre-DEC-075 mounts and their
one extra requirement:

```bash
mkdir -p data backups
sudo chown -R 10001:10001 data backups   # the container runs as uid 10001
docker compose -f compose.yaml -f compose.bind-mounts.yaml up -d
```

Use the same two `-f` flags on every subsequent `docker compose` command for
this stack — upgrades, `down`, `logs`, all of it.

### Backups on their own disk

DEC-040 says a backup on the same disk as the database does not survive losing
that disk — and on the default named volumes, both land under the same Docker
data root. `compose.backups-host.yaml` is the shape that closes the gap: it
binds **only** `/backups` to a host path and leaves `/data` the named volume
`compose.yaml` gives it, so the database keeps the seed-with-ownership default
(DEC-075) while backups go to a second disk, a NAS share, anywhere that is not
the database's disk.

```bash
mkdir -p /mnt/second-disk/akasha-backups
sudo chown 10001:10001 /mnt/second-disk/akasha-backups   # the one privileged command this deployment needs
BACKUP_DIR=/mnt/second-disk/akasha-backups docker compose -f compose.yaml -f compose.backups-host.yaml up -d
```

The `chown` prints nothing and exits 0. Compose would create a missing
directory as root:root, which the container's uid 10001 cannot write into —
that is the failure the `mkdir` + `chown` pair exists to prevent, and it fails
at 3am as `attempt to write a readonly database` if skipped.

The compose files, as a set:

| Tier | Files | `/data` | `/backups` | One-time setup |
|---|---|---|---|---|
| 1 — default | `compose.yaml` | named volume | named volume | none |
| 2 — both on host paths | `+ compose.bind-mounts.yaml` | host directory | host directory | `mkdir` + `chown` both |
| 3 — backups on their own disk | `+ compose.backups-host.yaml` | named volume | host directory | `mkdir` + `chown` the backups directory only |

Each overlay is opt-in, invoked explicitly, and never merged in by accident —
none is named `docker-compose.override.yml`. Use the same `-f` flags on every
subsequent `docker compose` command for the stack.

## Reverse proxy

Nginx Proxy Manager on the same LAN, e.g. `books.home.lan` → `http://<host>:4441`.
Do not expose that hostname beyond the LAN, do not forward a port to it, and do
not put it behind a proxy that terminates on a public address. There is no
login to stop anyone who arrives.

Set `AKASHA_BIND=127.0.0.1` if the proxy runs on the same machine, so the
container port is not reachable from the network directly. And note what
`0.0.0.0` publishes on: a host that has joined a VPN or mesh network
(WireGuard, Tailscale, ZeroTier and the like) carries an extra interface, and
`AKASHA_BIND=0.0.0.0` publishes on that one too — an unauthenticated port
reachable from outside the building without anyone having forwarded anything.
The way to exclude it is to bind `AKASHA_BIND` to one address rather than to
everything. The property belongs to overlay networks generally, not to any
particular one.

## When something is wrong

| Symptom | Cause |
|---|---|
| `attempt to write a readonly database` | on `compose.bind-mounts.yaml` only: `data/` is not owned by 10001 |
| Startup exits with `Refusing to migrate without a backup` | on `compose.bind-mounts.yaml` or `compose.backups-host.yaml`: `backups/` is missing or not owned by 10001 |
| `/api/health/ready` returns 503 `schema_not_current` | migrations have not finished, or failed; check the logs |
| Search finds nothing and the UI says degraded | no `GOOGLE_BOOKS_API_KEY`, or no outbound network |
| The backup script says the service is not running | start the stack; an online backup needs a live database |

On the default named-volume mounts, neither ownership row above is reachable —
there's no host directory to get wrong. Bring a host directory in for either
mount (`compose.bind-mounts.yaml`, or `compose.backups-host.yaml` for backups
only) and its row becomes reachable for that mount.

Logs are JSON, one object per line: `docker compose logs -f akasha`. Notes,
review text, import rows and API keys are redacted before they are written.
