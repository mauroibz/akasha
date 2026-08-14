# Sprint 021 — Attachments: viability, then a narrow slice

**Status:** in_progress
**Depends on:** 020
**Roadmap revision:** 8

## Objective

A measured verdict on whether attaching arbitrary files to an item is affordable — chiefly against
backup growth — and then whatever that verdict plus an explicit owner go-ahead justifies building.

**This sprint is gated.** DEC-042 adopted the assess-then-build shape as the default for any item
whose cost is unknown, and this is one. Phase A concluding that the feature is not worth its cost is
a legitimate, complete outcome. Sprint 020 is the worked example: its Phase A concluded *no* to the
larger feature, shipped a defect repair, and that was a complete sprint.

**The scope boundary is one sentence: an attachment is an opaque file, or it is a reader.**
Everything that expands this feature past its usefulness follows from crossing that line.

## Required context

1. `AGENTS.md`
2. `docs/sprints/ROADMAP.md`, the Sprint 021 section — the gate and the owner's framing are stated
   there and this file does not replace them
3. `docs/decisions.md`: DEC-035 and DEC-042 (the gate shape), DEC-039 and DEC-040 (backups, which
   are the cost centre here), DEC-044 (Sprint 020's verdict, as the model for what a Phase A
   deliverable looks like)
4. `backend/src/book_tracker/backup.py`, especially `ARCHIVED_DIRECTORIES`
5. `backend/src/book_tracker/infrastructure/covers.py` — the existing validated binary pipeline, and
   the closest thing to prior art for serving user files
6. `backend/src/book_tracker/api/library.py`, the cover upload and serving endpoints
7. Sprint 020 Outcome and `docs/agent/HANDOFF.md`

## Current implementation baseline

Re-derive at activation. As of Sprint 020's close: `ARCHIVED_DIRECTORIES = ("covers", "imports")`
tars both into every backup; nightly backups are retained seven deep and label-scoped, so
pre-migration backups are never pruned (DEC-040). Covers are normalized to a 600px JPEG and measured
at a **38.8 KB mean** across the sample in DEC-044. There is no attachment concept anywhere in the
schema, the API, or the UI.

## Phase A — viability and impact assessment

No product change ships in this phase. The deliverable is a written verdict in `docs/decisions.md`
with measurements behind every claim, answering:

- **Backup growth, which is the decision that scopes the feature.** Covers are ~39 KB; an epub is
  1–5 MB and a comic or audiobook far more. Measure what seven nightly backups cost against a few
  hundred attached files. Either attachments go into the tar under a size cap, or they are excluded
  with a documented separate story — say which, with the numbers behind it.
- **Where an attachment hangs**: item or entry. An epub is a property of the edition; an annotated
  personal copy is a property of your entry. Item is the default and matches the metadata-first
  framing, but state the consequence for undo and for import.
- **Serving an opaque blob safely.** Covers have a host allowlist, a pixel bound and a byte cap. An
  arbitrary file has none of those, so size limits, content-type handling and
  `Content-Disposition: attachment` are requirements rather than options. Say what the threat model
  is for a LAN-only, unauthenticated v1 (product spec section 9).
- **Restore.** A backup that no longer round-trips is not a backup. Whatever the storage decision,
  demonstrate the restore path still works, because `scripts/backup.sh` and the smoke test both
  assert it today.

## Phase B — build what Phase A justified

Scope is set by Phase A's verdict and an explicit owner go-ahead, not by this document. If it
proceeds, the narrow slice is: one or more opaque files per item, uploaded manually, size-capped,
listed with filename and size, downloadable from the detail page.

## Acceptance criteria

1. Phase A's verdict is recorded in `docs/decisions.md` with the measurements that support it,
   including the ones that argue against building.
2. The backup question is answered with a number, not a preference, and the restore path is shown to
   still work under whatever the answer is.
3. If Phase B proceeds: uploads are size-capped and content-type handled, downloads carry
   `Content-Disposition: attachment`, and no attachment is reachable outside its item.
4. If a surface ships: reachable from the detail page, never blocks the page it lives on, and passes
   the axe gate like every other surface.

## Required tests (TDD)

- Backup and restore round-trip under the storage decision Phase A makes, including the size cap
  boundary.
- Upload rejects what the cap and the content-type rules say it rejects.
- Path traversal on any attachment filename, remembering that **httpx normalizes `/../x` to `/x`
  before sending**, so the obvious test proves the client normalizes and nothing about the server —
  use `%2e%2e` / `..%2f`.
- If a surface ships: unit coverage, an e2e path through the detail page, and an axe check.

## Verification

```bash
python scripts/validate_project.py
make format
make check
make test
cd frontend && npm run test:e2e
cd .. && make build
make smoke-container
git diff --check
```

Plus, recorded in the Outcome: the Phase A measurements in full, and a walkthrough against the
container (not `make dev`) if anything user-visible shipped.

## Explicit non-scope

- **Any format parsing, in-browser reader, reading progress, or device sync.** This is the line the
  objective names.
- **Reading an uploaded epub's OPF as another metadata provider** filling empty fields under DEC-008.
  Genuinely cheap and on-brand, and named here so it is recognized as the natural next step rather
  than smuggled into the first slice.
- Authentication, public exposure, multi-user support.

## Commit checkpoints

1. `feat: measure backup growth against attached files`
2. `docs: record the Phase A attachments verdict`
3. Phase B checkpoints, named once the verdict and the owner's go-ahead exist
4. final `docs(sprint-021): close sprint and hand off`

## Risks and decisions to surface

- The gate itself: do not start Phase B without an explicit owner go-ahead recorded in
  `docs/decisions.md`.
- Backup growth is the owner's disk, not the agent's. A feature that quietly multiplies nightly
  backup size by twenty is a cost the owner has to accept knowingly.
- An unauthenticated LAN service that stores and serves arbitrary user files is a wider surface than
  one that stores validated images. That is a security judgement the owner should see stated.

## Outcome

**Phase A complete; Phase B not started and not authorized.** The sprint remains `in_progress` at
the gate DEC-035 requires: the verdict is recorded, the owner has not yet decided.

### Delivered

- `scripts/assess_attachment_cost.py` — costs seven storage strategies side by side against real
  `create_backup` / `restore_backup`, on a grid of 100/300/500 attachments at 2.5 MB. Reports bytes
  per backup, bytes across the seven-night window, gzip ratio, effective copies, and backup and
  restore wall time, plus what each strategy loses. Writes JSON.
- `backend/tests/test_attachment_cost.py` — 14 tests pinning the two numbers that would otherwise be
  quietly wrong (unique-inode accounting, incompressible corpus), the size-cap boundary, and a
  restore round-trip per strategy including that F and G name what they did not carry.
- **DEC-047**, the Phase A verdict.

### Measured (2026-08-14, NVMe workstation, faster than the ZimaBoard)

Seven-night window against the same library's current backup:

| strategy | 500 files (1.25 GB) | vs today | backup time |
|---|---|---|---|
| today, no attachments | 130.9 MB | 1x | 1.3 s |
| A in the tar, nightly | 8.68 GB | **67.9x** | 20.4 s |
| B size cap only | 8.68 GB | 67.9x | 20.6 s |
| C separate label, keep 2 | 2.57 GB | 20.1x | 20.6 s |
| D weekly cadence | 1.35 GB | 10.6x | 20.5 s |
| E loose, deduplicated | 1.35 GB | 10.5x | **2.0 s** |
| F excluded, manifest | 130.9 MB | 1.0x | 1.3 s |
| G Calibre reference | 130.9 MB | 1.0x | 1.3 s |

Multipliers are independent of corpus size at 100, 300 and 500 files. Measured gzip ratio on the
attachment corpus is **1.0003** — the archive is fractionally larger than the raw bytes, so the
compression the current design pays for buys nothing and blocks deduplication.

### Acceptance criteria

1. **Met.** DEC-047 records the verdict with the measurements behind it, including the ones that
   argue against building — 67.9x for the naive design, and the fact that F's near-zero cost buys a
   weaker recovery promise.
2. **Met.** The backup question is answered with numbers, and restore was shown to round-trip under
   every one of the seven strategies.
3. **N/A** — Phase B not authorized.
4. **N/A** — no surface shipped.

### Verification

`python scripts/validate_project.py` passed. `make check` passed. `make test` backend **258** /
frontend **85**. `npm run test:e2e` **77 passed / 2 skipped** across both projects. `make build`
clean. `make smoke-container` passed. `git diff --check` clean. The instrument was run for real on
NVMe rather than tmpfs, because `/tmp` here is a RAM disk and would have made every wall-time figure
fiction.

No walkthrough was required: Phase A ships no user-visible change. The restore drill inside the
instrument and the container smoke test cover the operational path.

### Deviations

- The instrument costs **seven** strategies rather than the two the sprint file implied ("either
  attachments go into the tar under a size cap, or they are excluded"). At the owner's direction
  during planning, the deliverable is a comparison table to choose from rather than a single
  measured path — the two named options turned out to be the most expensive and the cheapest of a
  wider set, with four useful shapes between them.
- The Calibre zero-copy reference was assessed as strategy G, also at the owner's direction. It was
  not in the sprint file's Phase A list.
- Phase A found two defects in adjacent code and **left both unfixed** because they belong to Phase
  B's scope: undo deletes an item without regard for attachments it may carry, and no cover file is
  ever unlinked when an item is deleted. Both are recorded in DEC-047.

### Impact on future sprints

- **022 (creator sort names), 023 (export), 024-026 (domains):** no impact. Sprint 021 touches no
  shared contract.
- If Phase B proceeds, **023 export** inherits a question this entry does not answer: whether an
  export carries attachment bytes, references, or neither.
