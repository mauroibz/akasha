# Akasha v1.5.6 — release notes

**The first published image since v1.5.4.** `v1.5.5` (Sprint 059) shipped release notes but
was never tagged, so this release carries both Sprint 059's and Sprint 060's changes — read
[`release-notes-v1.5.5.md`](release-notes-v1.5.5.md) for the event-loop fix in full; the
short version is below. If you are upgrading from `v1.5.4` or earlier, both sections apply.

## From Sprint 059: nothing blocks the event loop

A large import commit no longer freezes the application for everyone else. Measured on
hardware constrained to 2 CPUs, a 5,000-row commit held the first library page's latency at
just over five seconds against a 500 ms budget, with real request timeouts; it now moves onto
a worker thread through one seam, and the same measurement shows 78 ms with zero errors. Moving
work off the loop is also the first time this application can have two real threads writing to
SQLite at once — a write that loses that race now surfaces as a typed, retryable error instead
of an unhandled one, if `PRAGMA busy_timeout` still expires. No behavior visible to a person
changed.

## From Sprint 060: the disk stops filling quietly

Three growth paths with no collector, a migration rollback point with no prune, and no guard
against a write landing on a full disk — all closed. No screen changed and no request shape
changed for anything already working; the new behavior is entirely about what happens near the
edges (a full disk, an old backup, a finished import).

## What changed

- **A committed import's staging directory is collected on its own.** After a batch's
  24-hour undo window passes, `/data/imports/<batch_id>` — duplicates of covers already
  moved into `/data/covers` — is removed automatically. Nothing in the application reads
  that directory back after commit, so this needed no `--apply` flag the way the existing
  attachment reclaimer does.
- **A backup shares covers instead of tarring them fresh every night.** Hardlinked from the
  live store, the same trick DEC-047 already used for attachments. Measured: two backups of
  an unchanged 11-cover library cost 350 KB total, against 700 KB for two full copies.
  `/data/imports` is no longer backed up at all — it holds nothing a restore could use.
  Backups written by v1.5.5 and earlier still restore correctly.
- **An explicit prune for pre-migration backups.** `akasha-backup prune-pre-migration` lists
  every one with its revision, age and size; naming one for deletion still only reports
  until `--apply` is added, and the newest backup and the one matching the live database's
  schema revision are refused even when named. Never automatic.
- **A write that would grow the disk refuses before it starts.** Below
  `AKASHA_MIN_FREE_BYTES` (default 500 MB) of free space, an attachment upload, an import
  preview or commit, a cover replace, or a backup is refused with a typed error rather than
  failing partway through. `/api/health/ready` now reports free space, but a low reading
  never makes the application look down — a full disk can still read.
- **An upload connector's own declared size cap is honoured**, not just the shared module
  default — closes a latent gap no connector had hit yet, but the next one to declare a
  larger cap would have had it silently overridden.

## What this release deliberately does not do

- **No retention policy change for nightly backups.** `BACKUP_RETENTION` is unchanged.
- **No quotas per domain, item or user.** There is one user.
- **No compression or re-encoding of covers or attachments.** DEC-047 already measured that
  ground.

## Upgrading

```bash
echo "AKASHA_VERSION=1.5.6" >> .env
docker compose pull
docker compose up -d
```

Nothing migrates. The backup format moves to version 2 on the next nightly run — no action
needed, and every restore path reads both versions.
