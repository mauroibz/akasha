# Handoff — current reality

**Last completed:** Sprint 022 (attachment lifecycle), 2026-08-14.
**Next:** Sprint 023 (creator sort names) — status `ready`, file at
`docs/sprints/023-creator-sort-names.md`.

## Read this first

**Attachments are content-addressed and the lifecycle around them is now closed** (DEC-048,
DEC-050). A blob lives at `data/attachments/{sha256[:2]}/{sha256}` and the uploaded filename is held
in the database, never on disk. Four things follow and all four are load-bearing: identical bytes
cost one blob; the path is the digest, so integrity is free; the backup's hardlink sharing is correct
by definition; and **traversal is structural, not filtered** — no caller-supplied string reaches the
filesystem, which is why the `%2e%2e` tests pass without a filter to maintain. Do not "simplify" this
to `{item_id}/{filename}`.

**`akasha-attachments reclaim` is the only routine here that deletes data by inference**, and it is
built defensively on purpose. Three rules, none of them decoration:

1. **It reads the filesystem before it reads the database.** An upload writes its blob and then
   commits its row, so walking first and asking about references second can only be too generous.
   Reversed, a blob whose row landed between the two reads reads as an orphan and is deleted — a file
   the owner attached seconds earlier. A test fails if the two are swapped; that was verified by
   swapping them, not assumed.
2. **A blob younger than an hour is never a candidate**, which covers the same window for an upload
   still in flight during both reads.
3. **It reports and removes nothing without `--apply`**, and files under `attachments/` that it did
   not write are named and left alone — the same rule that keeps `enforce_retention` to directories
   carrying our own manifest.

**A blob a backup holds survives the reclaim**, because the backup has its own directory entry
against the same inode. Verified in the container rather than reasoned about.

**Item deletion defers to that sweep rather than reclaiming inline**, and this is deliberate. The
only path that deletes an item is undo, and undo retains an item carrying an attachment (DEC-047), so
an inline reclaim there would be unreachable code. Note also that **`entries.item_id` has no
`ON DELETE CASCADE`**: an item cannot be deleted at all while an entry references it.

**The download is no longer `immutable`, and must not go back.** The blob cannot change, but the
response is not the blob — it carries the filename, which is now editable. `max-age=0,
must-revalidate` with an ETag over digest **and** name: an untouched file is a 304 with no body, a
renamed one cannot match and is refetched under its new name.

**Uploads and downloads stream.** `BlobWriter` hashes and writes a chunk at a time; the per-file cap
is enforced as bytes arrive rather than after buffering. Measured on a 25 MiB file: peak RSS delta
went from +29.9 MiB to +2.6 MiB on upload and +24.9 MiB to +0.0 MiB on download.

**An attachment is an opaque file, or it is a reader.** That line held through two sprints: no format
parsing, no in-browser reading, no reading progress, no device sync. Reading an uploaded epub's OPF as
a metadata provider is named in DEC-047/048/050 as the natural next step precisely so it is recognised
rather than smuggled in. **Replace was considered and deliberately not built** (DEC-050): with rename
in place it is remove plus attach.

## Sprint 023 — what it walks into

`sort_author` is `Computed("json_extract(metadata, '$.authors[0]')")`, so "Gabriel García Márquez"
sorts under G. The trap the roadmap names is real: splitting on the last space gets *Márquez* and
*Llosa* wrong while getting *Rulfo* right, so the shape is a stored sort name seeded by a heuristic
and **correctable by the owner**, not a cleverer split.

**Sprint 022 added no migration**, so the head is still `0010_attachments`, pinned by literal in
`test_migrations.py` (twice) and `test_backup.py`. `sort_author_normalized` is maintained by a
`before_insert`/`before_update` mapper event (DEC-036) precisely so a new write path cannot forget it;
whatever replaces `sort_author` inherits that requirement. Name the column for **creators**, not
authors — an album has an artist and a game has a studio.

## Known and left, in the order they are likely to bite

- **`HEAD` on any route returns 405.** Application-wide, not attachment-specific. It cost me a
  confusing debugging detour: `curl -sI` returned no ETag, which made a working 304 look like a 200.
- **The orphaned cover file is still not collected.** The reclaim is scoped to the attachment store
  on purpose: a cover is re-fetchable cache and does not deserve a second delete-by-inference
  mechanism. Product spec open question 2 records this.
- **"Replace cover" on the detail page is a raw unstyled `<input type=file>`**, showing the browser's
  default "Choose File / No file chosen". It looks unfinished beside the Files panel.
- **The quoted publisher string** (`"O'Reilly Media, Inc."`) is still visible on the detail page.
- Multiple-file selection, drag-and-drop and upload progress bars are unbuilt and were named
  explicit non-scope in Sprint 022 — additive polish, not lifecycle correctness.

## State

Worktree clean, all commits local on `main`, nothing pushed.
