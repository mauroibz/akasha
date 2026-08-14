# Handoff — current reality

**Last completed:** Sprint 023 (creator sort names), 2026-08-14.
**Next:** Sprint 024 (export) — status `ready`, file at `docs/sprints/024-export.md`.
**Plan revision 10** as of 2026-08-14 (DEC-052) — see the section below before touching Sprint 025.

## Read this first

**`items` now carries two different names for a creator and they are not interchangeable.**
`sort_author` is still the generated `json_extract(metadata, '$.authors[0]')` — the name **as
written** — and it is what the detail page and the grid display and what the `q` search filter
matches. `creator_sort_normalized` is what the library **orders** by. Sorting moved; search
deliberately did not, because a reader types "gabriel garcia" and must still find a row that sorts
as "garcia marquez gabriel" (DEC-051). If you find yourself pointing both at one column, that is
the regression this split exists to prevent.

**Of the three new columns only `creator_sort_override` is real data.** `creator_sort` and
`creator_sort_normalized` are derived as `override or creator_sort_name(first_author)` by the same
`before_insert`/`before_update` mapper event DEC-036 introduced, so they cannot be forgotten by a
new write path — and they must never be written directly. Migration head is
`0011_creator_sort_names`, pinned by literal in `test_backup.py` and listed twice in
`test_migrations.py`.

**The heuristic is wrong on purpose and correcting a row is the supported answer.** It treats the
first token as the given name and everything after as the surname, so it gets the Spanish double
surnames right — García Márquez, Bioy Casares, Vargas Llosa — and gets two-given-name English names
wrong: "Jorge Luis Borges" becomes "Luis Borges, Jorge". Measured at **14 of 16** on the
walkthrough library. Do not tune it. The edit surface ("Sorts as" in the metadata dialog) and the
Calibre seed are the design's answer, and a tuned heuristic would silently rewrite names the owner
has already fixed.

**Calibre's `authors.sort` is read where it exists and stored as the override**, which is to say as
owner data, not cache. That is what stops a refresh or a re-import recomputing over it. The column
is optional — `REQUIRED_TABLES` guarantees the `authors` table, not its columns — so the reader
checks with `PRAGMA table_info` and falls back. Undo knows this field: an import that seeded it can
be undone, while a name corrected after the import is retained.

**`CursorState.v` is 2.** Bump it whenever a stored projection a cursor compares against changes
meaning; a stale cursor then fails as `400 invalid_cursor`, which `HomePage.tsx` already renders,
instead of comparing an old value against a new column and skipping or repeating a page.

## The plan changed on 2026-08-14 — read DEC-052 before Sprint 025

`docs/domain-architecture-proposal.md` is accepted. The album mapping was validated against live
MusicBrainz and Cover Art Archive responses rather than reasoned about, and two measurements
rejected the shortcut of casting albums into book fields: **MusicBrainz only inverts people's sort
names** (`Daft Punk` stays `Daft Punk`, so DEC-051's heuristic would file it under P), and **a
barcode is not a unique edition key** (one observed on three distinct releases), so cross-provider
identity does not exist for albums.

Consequences for anyone reading an older doc: Sprint 025 is **no longer a gated blind pilot** but
six named seams; **Sprint 026 is new** (status vocabulary, seam 5b); games and series renumbered to
**027** and **028**; roadmap is plan revision **10**; `FINAL_SPRINT` is **28**. Sprint 024 is
unchanged and still runs first.

## Sprint 024 — what it walks into

**There are now two owner-edited fields that no algorithm can reconstruct**: an attachment's
`filename` (DEC-050) and `creator_sort_override` (DEC-051). An export that omits either loses
something the owner typed. The derived columns are the opposite case and should be left out
entirely; they rebuild themselves.

The sprint's one real decision is **whether an export carries attachment bytes, references, or
neither** — a fork, not a detail, since bytes make the export an archive rather than a file. Put it
to the owner at activation, the way Sprints 021 and 022 put theirs.

The binding format constraint: **export the entity shape** — `type`, identifiers, opaque
`metadata` — not a book-specific schema. DEC-052's seam 3 **confirms this bet** rather than
threatening it: storage stays opaque and a per-domain field spec carries readability. The only
change to this sprint is one paragraph in deliverable 2 framing the Goodreads CSV as one domain's
export view.

`backup.py` is the closest prior art for producing a whole-library artifact, and the attachment
download is the prior art for streaming one.

## Known and left, in the order they are likely to bite

- **One dev-library item has `OL14454691A` as its author** — an Open Library author key that reached
  `metadata.authors` as if it were a name, so it sorts under O. Pre-existing, unrelated to Sprint
  023, and it will show up in any author-sorted list.
- **The list API takes repeated `status=`, not `statuses=`.** An unknown parameter is ignored
  silently, so a wrong guess looks like missing rows — the default excludes `unsorted`, which is
  where imports land.
- **`HEAD` on any route returns 405.** Application-wide, not route-specific.
- **"Replace cover" on the detail page is a raw unstyled `<input type=file>`**, showing the
  browser's default "Choose File / No file chosen" beside the styled Files panel.
- **The quoted publisher string** (`"O'Reilly Media, Inc."`) is still visible on the detail page.
- The orphaned cover file is still not collected; the reclaim is scoped to attachments on purpose.

## State

Worktree clean, all commits local on `main`, nothing pushed.
