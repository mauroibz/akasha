# Operator runbook

Everything here has been performed against a running container, not written from
the source. Commands assume the repository checked out on the host and `docker`
with the Compose plugin installed; nothing else is needed.

**Akasha v1 has no authentication.** Anyone who can reach the port can read and
change every rating, note and shelf. Keep it on a trusted LAN.

## First install

```bash
cp .env.example .env      # then edit it
mkdir -p data backups calibre
sudo chown -R 10001:10001 data backups
docker compose up -d
```

`USER_AGENT_CONTACT` is required and startup refuses without it: Open Library
asks callers to identify themselves. `GOOGLE_BOOKS_API_KEY` is optional; without
it search runs on Open Library alone and Spanish-language coverage is poor.

**The `chown` matters.** The container runs as uid 10001 and cannot write into a
directory owned by anyone else. Skipping it produces `attempt to write a readonly
database` at startup, which reads like corruption and is only permissions.

Check it came up:

```bash
docker compose ps                     # State should be "healthy"
curl -fsS http://localhost:8000/api/health/ready
```

## Upgrading

```bash
git pull
docker compose up -d --build
```

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

```bash
docker compose down
ls backups/                                   # find the pre-migration copy
docker run --rm --user 10001 \
  -v "$PWD/backups:/backups:ro" -v "$PWD/data-restored:/data" \
  akasha:local akasha-backup restore /backups/pre-migration-<stamp> --into /data
mv data data-broken && mv data-restored data
git checkout <previous-tag-or-commit> && docker compose up -d --build
```

Restore refuses to write into a directory that is not empty, so it cannot
silently overwrite a database you meant to keep.

## Nightly backups

Schedule from the host, not from inside the container — the application is one
process and is not a cron daemon.

```cron
15 3 * * *  cd /srv/akasha && ./scripts/backup.sh >> /var/log/akasha-backup.log 2>&1
```

`scripts/backup.sh` requires the stack to be running: an online backup reads a
live database through SQLite's backup API rather than copying a WAL file out
from under a writer. Each run writes a directory containing `books.db`,
`covers.tar.gz`, `imports.tar.gz`, `manifest.json` and `checksums.sha256`,
verifies its own output with `PRAGMA integrity_check`, and then deletes the
oldest `nightly-` backups beyond `BACKUP_RETENTION` (default 7).

Backups live on their own mount, outside the data volume (DEC-040). Point
`BACKUP_DIR` at a NAS share if you have one; a backup on the same disk as the
database does not survive losing that disk.

Check one by hand at any time:

```bash
docker compose exec akasha akasha-backup verify /backups/nightly-<stamp>
```

## Restoring

```bash
docker compose down
mkdir data-restored
docker run --rm --user 10001 \
  -v "$PWD/backups:/backups:ro" -v "$PWD/data-restored:/data" \
  akasha:local akasha-backup restore /backups/nightly-<stamp> --into /data
mv data data-old && mv data-restored data
docker compose up -d
```

Restore verifies every checksum and re-runs `integrity_check` before writing
anything. It needs no configuration at all — not even `USER_AGENT_CONTACT` —
because the restore path deliberately does not build the application.

## Reverse proxy

Nginx Proxy Manager on the same LAN, e.g. `books.home.lan` → `http://<host>:8000`.
Do not expose that hostname beyond the LAN, do not forward a port to it, and do
not put it behind a proxy that terminates on a public address. There is no login
to stop anyone who arrives.

Set `AKASHA_BIND=127.0.0.1` if the proxy runs on the same machine, so the
container port is not reachable from the network directly.

## When something is wrong

| Symptom | Cause |
|---|---|
| `attempt to write a readonly database` | `data/` is not owned by 10001 |
| Startup exits with `Refusing to migrate without a backup` | `backups/` is missing or not owned by 10001 |
| `/api/health/ready` returns 503 `schema_not_current` | migrations have not finished, or failed; check the logs |
| Search finds nothing and the UI says degraded | no `GOOGLE_BOOKS_API_KEY`, or no outbound network |
| The backup script says the service is not running | start the stack; an online backup needs a live database |

Logs are JSON, one object per line: `docker compose logs -f akasha`. Notes,
review text, import rows and API keys are redacted before they are written.
