# Sprint 035 — Ebook attachments on a toggle

**Status:** in_progress
**Depends on:** 034
**Roadmap revision:** 17

## Objective

A Calibre import can bring the ebook files along, on a toggle that is off by default. Turning it on
attaches one file per book to the item it belongs to, sends nothing the library already holds, skips
and names anything over the attachment cap, and leaves undo able to reverse exactly what the import
attached and nothing the owner attached by hand.

## Required context

- `docs/specs/product-spec.md` §1 (the "not an ebook server" non-goal and its v1 list), §5.2
  (Calibre), §5.3 (the shared import pipeline), §7 (`/import`), §9 (LAN-only, unauthenticated).
- `docs/specs/technical-spec.md` §6.5 (imports), §6.6 (the domain contract), §7.1
  (`/api/import/...`), and the attachment endpoints.
- `docs/decisions.md`: **DEC-047** (the attachment cost measurement, the undo guard it demanded, and
  the orphan-file debt), **DEC-048** (content-addressed blobs, the 25 MiB cap, hardlinked backups),
  **DEC-049** (reclamation), **DEC-082** (planning by identity; why the client cannot hash),
  DEC-081 (the folder chooser and `alternate`), DEC-080 (connector-declared input), DEC-078 (the
  importer boundary), DEC-025 (the walkthrough gate).
- Code, read fresh rather than from any summary:
  `backend/src/book_tracker/domain/importers.py` (`NormalizedImportRecord`, `ImportInputSpec`,
  `ImportInventory`, `IncrementalImporter`, `planned_upload`),
  `api/imports.py` (`_bundle_member`, `_bundle`, `_candidates`, the `plan` route,
  `available_importers`), `application/imports.py` (`ImportService.commit` and the cover install
  that runs after it), `application/undo.py` (**the whole file** — the item guard at the
  `entity_type == "item"` branch is the thing this sprint changes),
  `application/library.py` (`record_attachment`, `delete_attachment`, `_attachment_dict`),
  `infrastructure/attachments.py` (`BlobWriter`, `delete_blob_if_unreferenced`),
  `infrastructure/repositories.py` (`_identities`, `existing`, `with_cover`, and the
  `ImportEffectRow` writes inside `commit`), `reclaim.py`, `backup.py` (`_share_attachments`),
  `domains/book/calibre.py` (`_records`, `read`, `stage`, `plan`),
  `frontend/src/features/import/bundle.ts`, `frontend/src/pages/ImportPage.tsx`,
  `frontend/src/features/detail/Attachments.tsx`, `frontend/src/api/imports.ts`.
- Migration `0002_domain_schema` for `attachments(item_id, filename, byte_size, sha256)` and its
  `uq_attachments_item_sha256`; `import_effects(batch_id, record_id, effect_type, entity_type,
  entity_id, before_values, after_values)`.

## Current implementation baseline

Measured and read on 2026-08-21, not inferred.

**Attachments already exist and are sound.** Sprint 021/022 shipped opaque per-item files:
content-addressed at `attachments/{sha256[:2]}/{sha256}`, streamed through `BlobWriter` under a
25 MiB per-file cap (`config.attachment_max_bytes`), served with `Content-Disposition: attachment`,
refcounted on delete, swept by `reclaim.py`, and **hardlinked** rather than copied into every nightly
backup (`_share_attachments`). Nothing in this sprint needs to invent storage; it needs to reach it
from the importer.

**The owner's library, measured at `/home/ibz/Calibre Library`:** 174 MB total — 18 books, 18 epub
(95.4 MB, mean 5.3 MB, **max 14.8 MB**), 14 azw3 (67.4 MB, max 15.3 MB), 18 covers (9.6 MB),
`metadata.db` (0.5 MB). **Nothing in the library exceeds the 25 MiB cap**, so skip-and-report is
built for correctness rather than for this corpus. The live blob store is currently 1.5 MB and the
whole data directory is 2.6 MB.

**The import path stops at covers.** `CalibreImporter.stage` prepares a cover per record and
`ImportService.commit` installs it after the batch commits; there is no equivalent for any other
file, and `NormalizedImportRecord` has no way to say which files belong to a record.
`_bundle_member` hardcodes the Calibre bundle shape — `metadata.db` at the root and `*/cover.jpg`
below it — in a shared route, which is the one place this sprint is forced to generalise.

**Undo currently treats every attachment as the owner's.** `UndoService` counts
`AttachmentRow` for a batch-created item and **retains the item** if there are any (DEC-047).
That guard is correct for a hand-uploaded file and would be exactly wrong for a file the import
itself attached: every imported book would become permanently un-undoable. The ledger knows five
entity types — `entry`, `entry_shelf`, `item`, `item_identifier`, `shelf` — and no sixth.

## Deliverables

1. **A record may name the files that belong to it.** `NormalizedImportRecord` gains
   `source_files: tuple[str, ...]` — relative paths under the source root, declared by the connector
   at read time and carried on the stored payload beside `cover_stage`. Calibre fills it from each
   book's directory. This is what lets a shared route resolve an uploaded path to a record without
   knowing what a Calibre library looks like.
2. **A connector declares what its bundle may contain.** `ImportInputSpec` gains
   `members: tuple[str, ...]` of `PurePosixPath.match` patterns. `_bundle_member` keeps its
   traversal guard unchanged — no absolute path, no `\`, no `..`, no dot-prefixed segment — and
   matches the connector's declared patterns instead of Calibre's two hardcoded ones. Calibre
   declares `("metadata.db", "*/cover.jpg", "*/*.epub", "*/*.azw3", "*/*.mobi", "*/*.pdf",
   "*/*.cbz", "*/*.cbr", "*/*.txt")`. The refusal message stops naming Calibre.
3. **The inventory answers a third question.** `ImportInventory.attached(kind, values) ->
   Mapping[str, frozenset[str]]` — for each identity value, the attachment filenames the library
   already holds against that item. Implemented on `DomainRepository` over `item_identifiers` joined
   to `attachments`, chunked at 500 like `_identities`, never one query per book.
4. **Calibre plans files as well as covers.** `CalibreImporter.plan` wants an offered ebook unless
   the item behind its `calibre_uuid` already holds an attachment of that filename. Deleting the
   attachment in Akasha makes the next import want it again, which is the same escape hatch AC3 of
   Sprint 034 established for covers.
5. **A committed batch accepts its files, one request each.**
   `POST /api/import/{importer_name}/batches/{batch_id}/files` takes `path` and one `file`.
   It validates `path` with `_bundle_member`, resolves it to a record through `source_files`, streams
   the body through `BlobWriter` under `attachment_max_bytes`, records the row against the record's
   `matched_item_id`, and writes an `ImportEffectRow`. **One file per request is the design, not an
   implementation detail:** it bounds every request by the attachment cap rather than by the size of
   the library, so a 600-book shelf works exactly as an 18-book one does, a bad file costs one book
   instead of the import, and the screen can count progress honestly. Refusals: 404 for an unknown
   batch, importer or path; 409 for a batch that is not `committed` or whose undo window has closed;
   413 for a file over the cap, named rather than swallowed; 422 for a path the connector does not
   declare.
6. **Undo knows about attachments.** A sixth `entity_type`. An attachment effect carries the row id,
   the `sha256` and the `filename`. On undo it is reversed **before** its item's create effect —
   which falls out of descending `effect_id` order, since it is written later — and only when the
   row still matches what the import recorded; a renamed or replaced attachment is *retained*, like
   any hand-edited field. The blob is dropped through `delete_blob_if_unreferenced` with the count
   taken after the row is gone, so an epub attached to two books survives undoing one of them. The
   existing DEC-047 guard stays exactly as it is for attachments the ledger does not claim.
7. **The toggle.** A checkbox beneath the Calibre folder input: *"Also attach the ebook files"*, off
   by default, with the count and total size of what it would add stated before anything is sent.
   With it on, `calibreBundle` adds **one file per book** in preference order — `epub`, `azw3`,
   `mobi`, `pdf`, `cbz`, `cbr`, `txt` — files over the published cap are listed and not sent, and
   after commit the client posts each wanted file to the batch route with visible progress and a
   named list of any that failed. The toggle is purely a client-side decision about what to offer;
   the server answers about what it was offered and never about what it was not.
8. **The cap is published.** `attachment_max_bytes` on the importers registry response, so the
   client can refuse a too-large file before spending the upload rather than after.
9. **Documentation.** README's *Importing and triage*, `docs/guides/adding-a-domain.md`, technical
   spec §6.5/§7.1, product spec §5.2/§5.3, and one clarifying sentence on the §1 non-goal: Akasha is
   still not an ebook server and its file surface stays file-type agnostic; what changed is that the
   importer can put a file where the owner could already have put it by hand.

## Acceptance criteria

1. With the toggle **off**, the bytes on the wire and the rows in `attachments` are identical to
   Sprint 034's — asserted, not assumed, because a default that quietly changed would be the worst
   outcome of this sprint.
2. With the toggle **on**, importing `/home/ibz/Calibre Library` attaches one file to each of the 18
   items, epub where a book has both formats, and each is downloadable from its detail page.
3. **A second import with the toggle on sends no ebook at all** — `metadata.db` and nothing else —
   and the screen says how many files it skipped because the library already holds them.
4. Deleting an attachment in Akasha makes the next import want that one file again, and only it.
5. A file over `attachment_max_bytes` is **named and skipped**, the other books still attach, and the
   import completes. Asserted with a fixture over the cap, since the owner's library has none.
6. Undoing an import made with the toggle on removes the attachments it created, drops the blobs
   nothing else references, and then deletes the items — so undo returns the library to where it
   was rather than retaining every book forever.
7. Undo **retains** an attachment the owner renamed or replaced after the import, and retains its
   item with it. A file the owner attached by hand to an imported item still blocks that item's
   deletion exactly as DEC-047 requires.
8. The batch file route refuses every path `_bundle_member` refuses, refuses a path the connector
   does not declare, refuses an uncommitted, undone or expired batch, and never writes a row for a
   file it did not fully store.
9. The inventory answers in a bounded number of queries regardless of library size — asserted by
   counting statements over a several-hundred-book manifest, not by timing.
10. Backup and restore still round-trip with attachments present, and the second nightly backup adds
    no second copy of the blobs — asserted on inode sharing, which is DEC-047's whole reason for
    choosing this storage strategy.
11. `reclaim` collects a blob left behind by a batch that was previewed and abandoned, and collects
    nothing that a row still points at.
12. The walkthrough gate passes: import the owner's real library with the toggle on, open a book and
    download the file it attached, re-import unchanged and observe that no ebook moves, delete one
    attachment and observe only that file return, then undo an import and confirm both the rows and
    the blobs are gone.

## Required tests (TDD)

- **Backend, route:** attach one file to its record; 404 for unknown batch and unknown path; 409 for
  a preview-state batch, an undone batch and an expired window; 413 over the cap with no row and no
  blob left behind; 422 for an undeclared path; a second identical upload is idempotent through
  `uq_attachments_item_sha256`.
- **Backend, plan:** wants every offered file on an empty library; wants none on an unchanged one;
  wants exactly the file whose attachment was deleted; wants an ebook for an item that has a cover
  but no file.
- **Backend, undo:** removes a batch-created attachment and its blob; keeps a blob a second item
  still references; retains a renamed attachment and its item; retains an item carrying a
  hand-attached file (the DEC-047 regression); reverses attachment effects before item creates;
  a second undo is a no-op.
- **Backend, inventory:** `attached` returns the right filenames per identity; bounded statement
  count over 1200 values.
- **Backend, member validation:** `_bundle_member` accepts each declared pattern and refuses
  traversal, dot-segments, backslashes and undeclared extensions, per connector.
- **Backend, backup/reclaim:** restore round-trips with attachments; the second backup hardlinks;
  reclaim collects an abandoned preview's blob.
- **Conformance:** a connector declaring `members` patterns that are absolute or contain `..` is
  rejected; a record naming a `source_file` outside its declared members is rejected.
- **Frontend:** the toggle is off by default and the bundle is unchanged when off; when on the
  summary counts and sizes the files; over-cap files are listed and not sent; the post-commit phase
  posts one request per wanted file and reports failures by name without failing the import.
- **E2E:** import with the toggle on, assert one attachment request per book; re-import and assert
  none; assert the toggle-off body is byte-for-byte the Sprint 034 shape.

## Verification

```bash
python scripts/validate_project.py
make format && make check && make test
cd frontend && npx playwright test --workers=1
git diff --check
```

Plus the walkthrough gate in AC12, recorded in `docs/agent/worklog.md`, and a `du -sh data` before
and after so the disk cost is a number in the worklog rather than an estimate.

## Explicit non-scope

- **Reading an ebook in Akasha.** No reader, no format parsing, no progress. The file is opaque and
  stays opaque; product spec §1 is unchanged.
- **A file-type-aware file UI.** The owner settled this: the detail page's attachment list stays
  simple and file-type agnostic. No format badges, no "open in reader", no per-format grouping.
- **Attaching both formats.** One file per book. A second format is one manual upload away and the
  UI for it already exists.
- **Calibre write-back, OPDS, device sync.** Product spec §9, unchanged.
- **A total disk quota.** DEC-047 recorded that no disk budget exists anywhere in this repository;
  this sprint states the cost and does not invent a ceiling. If the owner wants one it is its own
  work.
- **Incremental Goodreads.** A CSV has no files.

## Commit checkpoints

1. `feat(sprint-035): a record names the files that belong to it`
2. `feat(sprint-035): a batch accepts its files after it commits`
3. `feat(sprint-035): undo reverses what an import attached`
4. `feat(sprint-035): attach the ebooks on a toggle`
5. `docs(sprint-035): ebook attachments`
6. final `docs(sprint-035): close sprint and hand off`

## Risks and decisions to surface

- **Undo is the risk, not the upload.** DEC-047 made "this item has an attachment" mean "the owner
  did something deliberate here, do not delete it". This sprint creates attachments that mean the
  opposite. Getting the distinction wrong in one direction destroys a file the owner uploaded; in
  the other it makes every imported book permanently un-undoable. The ledger is the only thing that
  can tell them apart, which is why the sixth entity type is deliverable 6 and not a refinement.
- **A changed file under an unchanged identity is not detected**, exactly as DEC-082 accepted for
  covers. Re-converting an epub under the same name will not re-upload it. The escape hatch is AC4.
- **The disk curve, stated rather than bounded.** 95 MB for this library; the blob store is 1.5 MB
  today. At the mean measured here a 600-book library is roughly 3.2 GB, and DEC-047's strategy E
  keeps backups at ~1.0 effective copies **only while `BACKUP_DIR` shares a filesystem with the
  data directory** — on a NAS share it degrades to a full copy per backup, which DEC-040 allows.
  The owner should see that number before this ships, not after.
- **Akasha becomes the only copy that is backed up.** The owner is retiring
  calibre-web-automated, so after this ships the files exist in the Calibre folder on their machine
  and in Akasha's blob store, and only the second one is in the nightly backup. That raises the
  stakes on the undo path above and on AC10's restore round-trip: they are no longer belt-and-braces
  over another service that also holds the bytes.
- **Generalising `_bundle_member` touches the path validator every upload goes through.** The
  traversal guard must not be rewritten while the shape check is being made declarative; change the
  tail, keep the head, and pin both with the existing tests before touching either.

## Outcome

_Not started. On completion record delivered behavior, commands and actual results, commit IDs,
deviations/decisions, and impact on every future sprint._
