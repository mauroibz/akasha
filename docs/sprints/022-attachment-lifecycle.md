# Sprint 022 — Attachment lifecycle: reclaim, rename, and the edges Sprint 021 left

**Status:** ready
**Depends on:** 021
**Roadmap revision:** 9

## Objective

Every byte an attachment writes can be accounted for and reclaimed, and the flows around a file —
rename, replace, remove — behave the way the rest of the application already behaves.

Sprint 021 shipped the storage design and the happy path. This closes the lifecycle around it. It is
deliberately small and carries **no new feature surface**: an attachment remains an opaque file, and
nothing here parses, renders or reads one.

## Required context

1. `AGENTS.md`
2. `docs/decisions.md`: **DEC-047** (why the store is shaped this way and what it costs), **DEC-048**
   (content addressing, refcounted deletion, the backup's link chain), DEC-040 (backup retention)
3. `docs/specs/product-spec.md` section 7 *Interaction notes* — "Confirmation dialogs are limited to
   delete and explicit provider refresh overwrite" — and open question 2, which this sprint answers
   the second half of
4. `backend/src/book_tracker/infrastructure/attachments.py`
5. `backend/src/book_tracker/application/library.py` — `add_attachment`, `delete_attachment`, and
   `delete_entry`'s orphan behaviour
6. `backend/src/book_tracker/application/undo.py` — the attachment guard, and the `CASCADE` it guards
7. `backend/src/book_tracker/api/library.py` — the upload and download endpoints
8. `frontend/src/features/detail/Attachments.tsx`
9. Sprint 021 Outcome and `docs/agent/HANDOFF.md`

## Current implementation baseline

Re-derive at activation. As of Sprint 021's close, all of the following were read out of the shipped
code rather than assumed:

- **`delete_blob_if_unreferenced` has exactly one caller**, `LibraryService.delete_attachment`. No
  other path reclaims a blob.
- `attachments.item_id` is `ON DELETE CASCADE`. Deleting an item therefore drops its attachment rows
  **and leaks their blobs**. The undo guard makes that unreachable today; it is not a fix.
- `store_blob` writes before the row is inserted, on purpose. A crash between the two leaves an
  unreferenced blob, which nothing collects.
- Deleting an entry leaves its item, and so its attachments, in place by design.
- Upload does `await file.read(cap + 1)` and download does `target.read_bytes()`: **whole file in
  memory**, up to 25 MiB per concurrent request, on a machine where a cover is 39 KB.
- The download carries `Cache-Control: private, max-age=31536000, immutable` and no validator, while
  the row's `filename` is mutable.
- There is no rename endpoint and no replace endpoint.
- The Remove button has no confirmation, while *Delete entry* on the same page has one.
- `disabled={remove.isPending}` is on every Remove button, so removing one disables all of them.
- The file input is `sr-only` but focusable and shares its accessible name with the visible button,
  giving two tab stops that do the same thing.

## Deliverables

1. **A reclaim path for orphaned blobs.** The only true gap: today a blob can exist with nothing
   pointing at it and no way to find it. Prefer a maintenance action that is safe to run at any time
   over a background sweep — a routine that deletes by walking the filesystem is the shape that
   eventually deletes something it should not, which is why `enforce_retention` only touches
   directories carrying an Akasha manifest.
2. **Rename**, which is a database write and nothing else, since the filename is already metadata.
3. **Replace**, if and only if it is meaningfully different from remove-then-attach once rename
   exists. Decide it explicitly rather than building it by default.
4. **A confirmation on remove**, matching the convention the product spec already states.
5. **Streamed upload and download**, so a 25 MiB file is not a 25 MiB allocation.
6. The small UI corrections named in the baseline: per-row pending state, one tab stop.

## Acceptance criteria

1. A blob with no referencing row is reclaimable, and the reclaim reports what it removed and what it
   left. It must never remove a blob a backup is the only remaining holder of — check what the
   hardlink chain in DEC-048 actually guarantees before assuming this is free.
2. Deleting an item reclaims its blobs, or provably defers them to the reclaim path. Pick one and say
   which; silently leaking is what this sprint exists to stop.
3. Renaming an attachment changes the name shown and the name a fresh download saves as. Note the
   caching wrinkle: the current `immutable` header means an already-downloaded file keeps its old
   name for a year, so the header and the rename have to be reconciled.
4. Removing a file asks first, and cancelling leaves the file attached.
5. A 25 MiB upload and download do not hold the whole file in memory. Measure it; do not assert it.
6. Attachment surfaces still pass the axe gate, with one tab stop per action.

## Required tests (TDD)

- A blob orphaned by each route that can orphan one — item delete, crash between blob and row, last
  reference removed — is found and reclaimed.
- Reclaim does **not** remove a blob that any live row references, including one shared by two items.
- Rename round-trips and does not disturb the digest, the row identity, or the backup.
- Remove asks first; cancelling is a no-op.
- Streaming: a file larger than the buffer is served correctly, byte-identical.
- Axe on the attachments surface, unchanged.

## Verification

```bash
python scripts/validate_project.py
make format && make check && make test
cd frontend && npm run test:e2e
cd .. && docker build -t akasha:local . && make build && make smoke-container
git diff --check
```

Plus a walkthrough **against the container** — `make build` does not rebuild the image — exercising
attach, rename, remove-with-confirm, and a reclaim run against a library that has deliberately been
made to hold an orphan. Report the memory figures for the streaming criterion.

## Explicit non-scope

- **Any reader, preview, thumbnail, or format parsing.** The line from Sprint 021 holds.
- Reading an uploaded epub's OPF as a metadata provider under DEC-008. Still the natural next step,
  still not this sprint.
- Multiple-file selection, drag-and-drop, and upload progress bars. Real UX improvements, but they
  are additive polish rather than lifecycle correctness; schedule them separately if they are wanted.
- The orphaned **cover** file, which predates attachments. If the reclaim path generalizes to it for
  free, say so; do not build a second mechanism.
- Range requests and resumable uploads.

## Commit checkpoints

1. `feat: reclaim attachment blobs nothing references`
2. `feat: rename an attached file`
3. `fix: confirm before removing an attached file`
4. `perf: stream attachments instead of buffering them whole`
5. final `docs(sprint-022): close sprint and hand off`

## Risks and decisions to surface

- **Reclaim is the dangerous deliverable in this sprint.** It deletes data by inference. The refcount
  is authoritative and the filesystem is not; anything that walks blobs and deletes what looks
  unreferenced must be reasoned about against a concurrent upload that has written its blob but not
  yet committed its row.
- Whether replace is a real operation or rename plus attach is a product question, not an
  implementation one. Ask before building it.
- Reconciling `immutable` caching with a mutable filename may be better solved by removing the
  filename from the cached response than by weakening the cache.

## Outcome

_Not started. On completion record delivered behavior, commands and actual results, commit IDs,
deviations/decisions, and impact on every future sprint._
