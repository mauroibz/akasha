# Handoff — current reality

**Last completed:** Sprint 026 (statuses, formats and tracklists — seam 5b), 2026-08-15.
**Next:** Sprint 027 (library shell and shelves) — status `ready`, file at
`docs/sprints/027-library-shell-and-shelves.md`. Plan revision **11**.

## Do this first

**You are on branch `sprint-025-albums`, not `main`.** Sprints 025 *and* 026 ran and closed there.
Eighteen commits are local and nothing has been pushed. **Merging back is the owner's decision** —
that is the entire reason the branch exists (DEC-053, amended for 026 by DEC-061). Ask before
merging, and cut Sprint 027's branch from whatever the owner settles on.

**Sprint 027 opens with a question, not with code.** Its tab strip needs a default: all domains, or
the last one used. Put it to the owner with a recommendation before building it.

**Music is finished as a domain.** Do not re-litigate DEC-057 (an album's status is possession) or
DEC-059 (format is an independent, entry-level, multi-valued, per-domain tag). Both are built.

## Read this first

**`Domain` is now the whole per-domain contract**, in
`backend/src/book_tracker/domain/domains.py`. It carries `item_type`, `label`, `identity`, `fields`,
`enriches`, `recognize` — and, since this sprint, `statuses`, `default_status`, `entry_fields`,
`formats` and `entry_panel_label`. `GET /api/item-types` publishes all of it and every screen renders
from that. There is no `type === "album"` branch anywhere, and adding one is the thing to catch in
review.

**Three rules the code now depends on:**

- **A write is validated against the item's own domain**, in `LibraryService._validated`, and refused
  with a 422 naming the domain. A bulk write spanning domains is refused *whole*: half-applying it
  leaves nothing showing which half landed, and the undo ledger does not cover a manual edit.
- **`_filter_key` must list every filter.** It is what a keyset cursor is bound to. Sprint 027 adds a
  `type` filter and has to add it there too; forgetting is a silent paging bug, not a test failure.
- **The published unions (`EntryStatus`, `EntryFormat`) are spelled out and pinned to the registry by
  a test.** A dynamically built `StrEnum` is opaque to mypy, so the drift assertion is the safety
  net rather than the construction.

## What Sprint 026 left behind

- **`facets.status_counts_by_type`** groups the counts by item type beside the whole-library
  `status_counts` the inbox badge uses. **Sprint 027's tab strip is half-built by this** — what does
  not exist yet is a `type` *filter* on `GET /api/entries`.
- **Migration `0013_entry_formats`** adds the join table and **rebuilds `entries`** to widen a CHECK
  constraint that listed the six book statuses. Note for any future rebuild: SQLAlchemy does not
  reflect SQLite CHECK constraints, so `copy_from` with the table spelled out is the only safe form —
  a reflected rebuild drops every check silently.
- **A `rows` field type** — an ordered list of structured rows, with columns declared the way a field
  is. Only `album.tracklist` uses it. It is deliberately **not editable** in the metadata dialog.
- **Formats are exported** (owner data, DEC-054's rule). The Goodreads CSV is unchanged and still
  book-only.
- **The Goodreads suggestion map is stated against `BOOK`**, with a test, rather than being book-only
  by the accident that books are the only domain with an importer.

## Known and left, in the order they are likely to bite

- **The dev library at `data/` is books plus two albums again**: item 13 *Discovery* and item 14
  *Kind of Blue*, both `owned`, with formats and covers. The three albums from Sprint 025 were
  **deleted** at the owner's instruction ("just delete the albums, this is a test db"); the backup is
  `backups/pre-sprint026-20260815T142246Z`. The 0012→0013 auto-migration wrote
  `backups/pre-migration-20260815T145406Z`.
- **`README.md` still describes a book-only product.** The album domain has never been released or
  merged, so advertising it there would describe something no user can run; the copy that would have
  contradicted the code was fixed, the rest waits on the merge decision.
- **`data/covers/` holds two stale `cover-*.jpg.tmp` files.** Interrupted cover installs from an
  earlier session; harmless, uncollected, and not this sprint's to sweep.
- **The container cannot run a walkthrough against the dev checkout.** `docker compose` runs as uid
  10001 and `data/` is owned by the host user, so it dies with `attempt to write a readonly
  database`. Use `make smoke-container` for the container gate and run the app directly
  (`BOOK_TRACKER_STATIC_DIR=../frontend/dist`) for a library walkthrough.
- **"Choose a cover" still appears on an album and can only say no** — the chooser is Open Library's
  work-editions path. Unchanged from Sprint 025.
- **Release selection is still arbitrary between same-day originals**, stable but not meaningful.
- One dev-library item has **`OL14454691A` as its creator**; item 7 stores `"O'Reilly Media, Inc."`
  **with the quotes**. Both pre-existing.
- The list API takes repeated `status=`, `shelf=` and now `format=`; an unknown parameter is ignored
  silently, while an unknown *value* for `status` or `format` is a 422.
- `HEAD` on any route returns 405, application-wide.
- "Replace cover" on the detail page is still a raw unstyled `<input type=file>`.
- The orphaned cover file is still not collected; the reclaim is scoped to attachments on purpose.

## State

Migration head `0013_entry_formats`. Worktree clean; all commits local on `sprint-025-albums`,
nothing pushed.
