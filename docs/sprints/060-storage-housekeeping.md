# Sprint 060 — The disk stops filling quietly

**Status:** ready
**Depends on:** 056

**Roadmap revision:** 30

## Objective

Every place this application writes bytes has something that eventually removes them, or a documented
reason it does not — and the application refuses a write it cannot complete instead of discovering
the disk is full halfway through one.

Three growth paths have no collector at all today, and none of them is visible to the person whose
disk it is.

## Required context

- `backend/src/book_tracker/backup.py` — `create_backup`, `ARCHIVED_DIRECTORIES`,
  `_share_attachments`, `enforce_retention`.
- `backend/src/book_tracker/reclaim.py` — the existing reclaimer, and the ethic it establishes:
  report by default, act only on `--apply`, never touch a blob younger than the grace window.
- `backend/src/book_tracker/application/imports.py:271` — where a batch is staged.
- `backend/src/book_tracker/domains/book/calibre.py`'s `stage`, which writes one prepared JPEG per
  book into that directory.
- `backend/src/book_tracker/api/imports.py:339-366` — the upload branch of `_source`.
- `backend/src/book_tracker/main.py`'s `_back_up_before_migrating`, and the readiness route.
- `docs/decisions.md`: DEC-039 (the pre-migration backup and why it is never pruned), DEC-040
  (backups outside the data volume), DEC-047 (attachments are hardlinked, not tarred, with the
  measurement), DEC-048 (the attachment cap bounds one file, not the total).
- `docs/operations/runbook.md`'s "Nightly backups" and "Reclaiming attachment space".

## Current implementation baseline

To be re-confirmed at activation. As observed 2026-09-01:

- **Staged import batches are never removed.** `ImportService` writes each batch to
  `/data/imports/<batch_id>`, and the Calibre connector stages one prepared cover per book into it.
  Nothing deletes that directory: not commit, not the expiry of the 24-hour undo window, not
  `akasha-attachments reclaim`, which only knows about `attachments/`. After a commit the staged
  covers are duplicates of what now lives in `/data/covers`.
- **`covers.tar.gz` and `imports.tar.gz` are rebuilt in full on every backup.** `ARCHIVED_DIRECTORIES`
  is `("covers", "imports")` and each is re-archived from scratch. DEC-047 solved exactly this
  problem for attachments by hardlinking them between backups, with the measurement that made the
  case; covers never got the same treatment. Seven nightly backups therefore hold seven complete
  copies of a cover set that changes by a handful of files a week — and each one also holds a
  complete copy of the staged imports that should not be growing in the first place.
- **`pre-migration` backups accumulate for ever, by design and with no exit.** Retention is scoped by
  label so that nightly housekeeping can never delete the rollback point for an upgrade (DEC-039),
  which is right. But nothing else deletes them either, and there is no command that does, so one
  full copy per schema change stays on the disk indefinitely.
- **There is no free-space check anywhere in the codebase.** No `statvfs`, no `disk_usage`, no
  handling of `ENOSPC`. An import, an attachment upload or a nightly backup on a full disk fails
  wherever it happens to be.
- **The upload branch of `_source` ignores the connector's declared cap.** It bounds the read with the
  module constant `MAX_IMPORT_BYTES` and hardcodes "5 MiB" in the refusal, where the directory branch
  correctly reads `spec.max_bytes`. No upload connector declares a larger cap today, so this is
  latent rather than live — the first one that does would be silently overridden. Its refusal also
  offers "import it from a mounted path instead", which only the Calibre connector has.

## Deliverables

### 1. Staged import batches are collected

A batch's staging directory has a lifetime: it is needed until the batch is committed and its undo
window has passed, and it is dead weight afterwards. Give it that lifetime.

The undo window is the constraint that makes this safe, and it is what decides whether collection can
be automatic. Removing a directory whose batch can still be undone would break undo, so establish
first — from the code, not from this file — what undo actually reads back, and let that determine
whether the collector runs on its own or follows `reclaim`'s report-then-`--apply` shape. Record the
reasoning either way.

Whichever shape it takes, it belongs beside the existing reclaimer rather than in a second place with
its own vocabulary.

### 2. A backup stops re-archiving what has not changed

Two separate questions, and they may have different answers:

- **Covers.** DEC-047's hardlink approach exists, is measured, and is already implemented for
  attachments in `_share_attachments`. Extend the same sharing to covers, or record why covers are
  different. A tarball cannot be shared, so this likely means covers stop being a tarball — which is
  a manifest and restore change, and the restore path must keep verifying every checksum exactly as
  it does now.
- **Staged imports.** Ask whether `/data/imports` belongs in a backup at all. It holds derived,
  short-lived staging for a batch that is either committed — in which case the durable result is in
  the database and `covers/` — or abandoned. If it does not belong, removing it from
  `ARCHIVED_DIRECTORIES` is a manifest-version change and must be handled as one, with a restore that
  still reads an older backup written by an older version.

Do not guess at the saving. Measure a backup before and after on a realistic library, as DEC-047 did.

### 3. Pre-migration backups get an explicit, never-automatic prune

A command that lists the `pre-migration` backups with their revisions, ages and sizes, and deletes
only those the operator asks for. It must never run on a schedule, never be called from startup, and
never be reachable from nightly retention — DEC-039's guarantee is the reason those copies exist, and
this deliverable must not weaken it. The safe default is refusing to delete the newest one and the
one matching the current schema revision.

Same ethic as `akasha-attachments reclaim`: report by default, act on an explicit flag, and say what
was kept and why.

### 4. A write that cannot complete is refused before it starts

A free-space guard at the boundaries that write bulk: attachment upload, import staging, cover
install and backup creation. Below a configurable threshold, refuse with a typed error that says what
is wrong, rather than failing partway through a write.

Surface it on `/api/health/ready` as well — degraded rather than down, in the same spirit as the
provider-health route, which deliberately does not make a missing key look like an outage. The
readiness contract must keep meaning "can this serve", so decide carefully whether low space is a
503 or a separate signal, and write the reasoning into the decision.

The threshold is configuration, in the shape DEC-045 and DEC-048 established, and it must reach the
container through Sprint 056's passthrough list.

### 5. The upload path honours the connector's declared cap

`_source`'s upload branch reads `spec.max_bytes` and `spec.max_files` like the directory branch does,
and its refusal names the actual limit and offers the alternate input only when the connector
declares one. A connector-level test proves a declared cap is respected in both directions.

### 6. Release notes for v1.5.6

`docs/operations/release-notes-v1.5.6.md`, and the runbook's "Nightly backups" and "Reclaiming
attachment space" sections updated to describe every collector the application now has, in one place.

## Acceptance criteria

1. After a committed import and the expiry of its undo window, the batch's staging directory is gone
   — automatically, or through the documented command, per deliverable 1's recorded decision.
2. Undo still works for the full 24-hour window, proved on a batch whose staging was eligible for
   collection at the moment undo was exercised.
3. Two consecutive backups of an unchanged library consume measurably less than two full copies of
   the cover set, with before-and-after sizes recorded.
4. A backup written by this version verifies and restores; a backup written by the previous version
   still verifies and restores, proved against a real older backup directory rather than a
   hand-edited manifest.
5. The pre-migration prune lists what it would delete, deletes nothing without an explicit flag,
   refuses to delete the copy matching the current schema revision, and is reachable from no
   automatic path.
6. Nightly retention still never deletes a `pre-migration` backup.
7. Below the configured free-space threshold, an attachment upload, an import preview and a backup
   each refuse with a typed error naming the cause, and nothing is left half-written.
8. `/api/health/ready` reports low disk space distinctly from a database failure, and a full disk
   never makes a healthy application look like a broken one.
9. A connector declaring an upload cap above the default has it honoured, and the refusal message
   names that cap.
10. `akasha-attachments reclaim` is unchanged in behaviour.

## Required tests (TDD)

- **Staging lifetime.** A committed batch inside its undo window keeps its directory; the same batch
  past the window does not; an undone batch restores correctly either way.
- **Backup sharing.** Two backups of an unchanged library share cover storage; a changed cover is
  present in both and correct in both; deleting the older backup leaves the newer one complete —
  the same property `_share_attachments` already has tests for.
- **Backward compatibility.** Restore a backup fixture written in the previous manifest version.
- **Prune safety.** The current revision's copy is refused; the flagless run deletes nothing; nightly
  retention with a full `pre-migration` set removes none of them.
- **Free space.** Each guarded boundary refuses below threshold with its typed error, and passes
  above it. Inject the free-space reading at a seam rather than filling a disk.
- **Declared caps.** A connector with a larger declared upload cap accepts a file above the module
  default and refuses one above its own.

## Verification

```bash
python scripts/validate_project.py
make check
make test
make smoke-container
```

The container gate matters here more than usual: backups, restore and the reclaimers are exercised
through `scripts/smoke_container.sh`, which already performs a backup, a verify, an in-container
restore and the named-volume restore drill. Extend it with a restore of a previous-version backup.

A walkthrough is owed on the import flow if deliverable 1 changes anything a person sees, and on a
real backup-and-restore cycle regardless: run it, read the sizes, and report what you saw.

## Explicit non-scope

- **Backup encryption, off-host copying, or scheduling from inside the container.** The application
  is one process and does not become a cron daemon; the runbook's host scheduler stands.
- **A retention policy for nightly backups beyond the existing `BACKUP_RETENTION`.**
- **Quotas per domain, per item or per user.** There is one user.
- **Compressing covers or re-encoding attachments.** DEC-047 measured that ground already.
- Anything from Sprints 056, 058 or 059.

## Commit checkpoints

1. `[FIX] Collect a staged import batch when it stops being needed`
2. `[CHANGE] A backup shares what has not changed`
3. `[ADD] An explicit prune for pre-migration backups`
4. `[ADD] Refuse a write the disk cannot take`
5. `[FIX] Honour the connector's declared upload cap`
6. `[DOCS] Every collector in one place, and release notes for v1.5.6`
7. `[DOCS] Close sprint 060 and hand off`

## Risks and decisions to surface

- **Deliverable 2 changes the backup format.** That is the highest-risk change in these four sprints:
  a backup that cannot be restored is worse than a backup that is large. The old-version restore test
  is not optional, and if the sharing cannot be done without breaking it, ship the staging fix alone
  and record why.
- **Deliverable 1 deletes files by inference**, which is precisely what `reclaim.py`'s header says
  belongs behind a person. Follow that precedent unless the undo contract makes automatic collection
  provably safe, and record which was chosen.
- **A free-space guard can refuse a write that would have succeeded.** Choose the threshold so that a
  normally-full home disk is not permanently refused, and make it configuration so an operator can
  disagree.
- **DEC-039 must survive this sprint intact.** Every change to retention or pruning is one step away
  from deleting the rollback point of an upgrade that is currently failing. Criterion 6 is the guard;
  keep it.

## Outcome

_Not started. On completion record delivered behavior, commands and actual results, commit IDs, deviations/decisions, and impact on every future sprint._
