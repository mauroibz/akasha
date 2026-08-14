# Handoff — current reality

**Last completed:** Sprint 024 (export), 2026-08-14.
**Next:** Sprint 025 (albums — the six seams) — status `ready`, file at
`docs/sprints/025-second-domain-albums.md`. Plan revision **10**.

## Do this first

**Cut a branch from `main` before writing any Sprint 025 code (DEC-053).** The domain line runs on
a branch because its architecture could fail spectacularly and `main` is what it is abandoned back
to. Nothing else in the protocol changes: state and handoff advance as usual, the worktree ends
clean, nothing is pushed, and merging back is the owner's call at close. `AGENTS.md` says commits
stay local on *the current branch* — it forbids pushing, not branching, so nothing is being bent.

## Read this first

**The plan changed on 2026-08-14. Read DEC-052 before anything else.**
`docs/domain-architecture-proposal.md` is accepted. The album mapping was validated against the live
MusicBrainz and Cover Art Archive APIs rather than reasoned about, and two measurements rejected the
shortcut of casting albums into book fields:

- **MusicBrainz only inverts a *person's* sort name.** `Miles Davis` is type `Person` and sorts
  `Davis, Miles`; `Daft Punk` is type `Group` and does not invert; `Various Artists` is type `Other`.
  DEC-051's heuristic assumes a person's name and would file Daft Punk under P. Seam 1 generalizes
  the Calibre seed: a source that knows the sort name seeds the override, and the heuristic runs
  only when nothing knew.
- **A barcode is not a unique edition key.** `888837168625` was observed on three distinct releases.
  ISBN's global uniqueness is the only reason `merge_and_rank` can group across providers by it, so
  seam 2 is a strategy — `identity_key() -> str | None`, `None` meaning never merge — not a
  configurable identifier field. It lives in `domain/providers.py` and is the **least-proven seam**.

Sprint numbering moved: albums **025**, status vocabulary **026**, games **027**, series **028**.
`FINAL_SPRINT` is 28.

**The core is already neutral.** `items` has been `type`/`title`/`subtitle`/`year`/`cover_path`/
`identifiers`/opaque `metadata` since Sprint 002. Everything book-shaped sits in the layers above
it. Do not "generalize the core" — there is nothing there to generalize.

**`item_type` is declared on the `Provider` protocol and read nowhere in `src/`.** Treat the
provider registry as unbuilt, not as present-but-unused.

## What Sprint 024 left behind

`GET /api/export` streams entity-shaped JSON; `?format=csv` streams the Goodreads CSV. Two rules in
it are load-bearing for Sprint 025:

- **`metadata` is passed through untransformed.** The moment the export learns a field name it needs
  a v2 for the second domain. `test_export.py` already exports an `album`-typed item as the
  regression that catches this.
- **The JSON is the lossless artifact and the CSV is the convenience view.** The CSV neutralizes
  leading `=`/`+`/`-`/`@` so a spreadsheet reads a note as text, and halves the score to Goodreads'
  1–5. Both alter bytes, so both are confined to the CSV.

**Attachments export as references plus sha256, never bytes (DEC-054).** The digest is the whole
mechanism: a blob's path *is* its digest, so a reference resolves against any backup with no running
instance.

**Two streaming traps, both invisible to functional tests.** `yield_per` / `stream_results` does not
bound memory on SQLite — the driver has no server-side cursor and materializes the whole result. And
selecting **mapped entities** defeats any batching, because the `Session` identity map retains every
instance for the session's life. Export selects columns and walks in keyset batches; copy that shape
rather than rediscovering it. Only the memory measurement caught either one.

**There is no export button in the UI.** The route is the surface. No screen in product spec 7 asks
for one, so this was left rather than invented — but the owner has to know the URL to use it.

## Known and left, in the order they are likely to bite

- **One dev-library item has `OL14454691A` as its author** — an Open Library author key that reached
  `metadata.authors` as if it were a name, so it sorts under O. It is visible in any exported or
  creator-sorted list. Pre-existing and **not** Sprint 025's defect; note it, do not chase it.
- **The quoted publisher string.** Item 7 stores `"O'Reilly Media, Inc."` with the quotes as part of
  the value, so it exports as `"""O'Reilly Media, Inc."""`. The CSV escaping is correct; the stored
  data is wrong.
- **The dev library at `data/` was walked through on 2026-08-14** and carries residue: item 3 has a
  hand-set `creator_sort_override` of `García Márquez, Gabriel José` and a 1.5 MB attachment named
  `Cien años de soledad (Diana, 2012).epub`. Both are intentional walkthrough artifacts. The same
  session auto-migrated that database 0006 → 0011, writing
  `backups/pre-migration-20260814T163152Z` first.
- **The list API takes repeated `status=`, not `statuses=`.** An unknown parameter is ignored
  silently, so a wrong guess looks like missing rows — the default excludes `unsorted`, which is
  where imports land.
- **`HEAD` on any route returns 405.** Application-wide, not route-specific.
- **"Replace cover" on the detail page is a raw unstyled `<input type=file>`**.
- The orphaned cover file is still not collected; the reclaim is scoped to attachments on purpose.
- `statusLabels` is duplicated verbatim in `features/library/labels.ts` and `pages/TriagePage.tsx:42`.
  Sprint 025's deliverable 1 collapses it **first**, because a per-domain label map against two
  copies is how the book vocabulary silently survives on one screen.

## State

Migration head `0011_creator_sort_names`. Worktree clean, all commits local on `main`, nothing
pushed.
