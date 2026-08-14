# Sprint 024 — Export

**Status:** completed
**Depends on:** 020
**Roadmap revision:** 10

## Objective

The library leaves this application in a format the owner can read without it: entities as JSON,
plus a Goodreads-shaped CSV. Nothing the owner typed by hand is missing from the dump.

## Required context

1. `AGENTS.md`
2. `docs/sprints/ROADMAP.md`, the Sprint 024 section — it names the one open question and the one
   binding format constraint
3. `docs/specs/product-spec.md` section 9, "Scheduled — Export", and section 5.1 for the Goodreads
   column list the CSV has to mirror
4. `docs/decisions.md`: DEC-048 (attachments, which left the export question open), DEC-050 (the
   attachment filename is owner data), DEC-051 (so is the creator sort name), DEC-039/DEC-040
   (backup and its manifest, the closest prior art for a generated artifact), **DEC-052** (the
   domain seams, and why an opaque `metadata` object is the right bet)
5. `docs/domain-architecture-proposal.md` section 4, seam 3 — the field spec this export's
   human-readable half should be described in terms of
6. `backend/src/book_tracker/backup.py` — how a whole-library artifact is currently produced,
   verified and streamed; reuse its shape rather than inventing a second one
7. `backend/src/book_tracker/application/library.py`, `_item_dict` and `_entry_dict` — the existing
   serialization of exactly the two entities being exported
8. `backend/src/book_tracker/api/library.py` — `ItemResponse`/`EntryResponse` and the streaming
   response pattern already used by attachment downloads
9. `backend/src/book_tracker/infrastructure/models.py` — which columns are owner data and which are
   derived
10. Sprint 023 Outcome and `docs/agent/HANDOFF.md`

## Current implementation baseline

Re-derive at activation. As of Sprint 023's close: no export code exists. The migration head is
`0011_creator_sort_names`, pinned by literal in `test_backup.py` and listed in `test_migrations.py`
(twice). Attachments are content-addressed blobs under `data/attachments/{sha256[:2]}/{sha256}`
with the uploaded filename held in the database. `items` carries two owner-edited fields that are
**not** derivable from anything else in the row — `creator_sort_override` and each attachment's
`filename` — plus derived columns (`sort_author`, `title_normalized`, `sort_author_normalized`,
`creator_sort`, `creator_sort_normalized`) that rebuild themselves on write.

## Deliverables

1. `GET /api/export` returning the entity shape as JSON: `type`, identifiers, and an opaque
   `metadata` object. **Not a book-specific schema** — the database is already domain-agnostic, and
   a book-shaped format needs a v2 the moment Sprint 025 lands.
2. A Goodreads-shaped CSV, allowed to stay book-only, mirroring the columns product spec 5.1 lists.
   Frame it in code and docs as **one domain's export view**, not as the export's only shape: DEC-052
   accepted a per-domain field spec (seam 3), and the CSV is the book domain's instance of it. The
   JSON stays opaque and entity-shaped — seam 3 confirms that bet rather than threatening it, which
   is why this sprint runs before the domain work rather than after.
3. An answer to the attachment question, implemented rather than implied.
4. Streaming, not buffering. The JSON dump of a full library is the same class of object the
   attachment download already streams (Sprint 022), and the deployment target is a ZimaBoard.

## Acceptance criteria

1. Every field the owner typed survives the round trip: scores, notes, dates, shelves, reread
   counts, **corrected creator sort names**, and **attachment filenames**. Derived columns are
   absent from the export by design — assert their absence, so a later reader cannot mistake them
   for authority.
2. The JSON is entity-shaped: an item carries `type`, identifiers and opaque `metadata`, and
   nothing in the format assumes the type is `book`.
3. The CSV opens in a spreadsheet with the Goodreads columns product spec 5.1 names, and a library
   containing quotes, commas, newlines and non-ASCII names survives it intact.
4. Attachments are handled as decided, and the decision is recorded in `docs/decisions.md` with its
   reasoning — bytes, references, or neither, not left to omission.
5. Memory stays flat with library size: measured, as Sprint 022 measured streaming, not asserted.

## Required tests (TDD)

- Round trip of an item carrying a corrected `creator_sort_override` and an attachment with a
  renamed file; both appear, both derived columns do not.
- An item whose `type` is not `book` exports without special-casing.
- CSV escaping: a title with a comma, a note with a newline and a quote, an author with an accent.
- An empty library exports a valid, empty artifact rather than failing.
- Peak-RSS measurement over a library large enough to distinguish streaming from buffering.

## Verification

```bash
python scripts/validate_project.py
make format && make check && make test
cd frontend && npm run test:e2e
cd .. && make build && make smoke-container
git diff --check
```

Plus a walkthrough against the container with a real library: download both artifacts, open the CSV
in a spreadsheet, and confirm by reading — not by test assertion — that a book you corrected by hand
still carries your correction.

## Explicit non-scope

- Import of the exported JSON. Export is a one-way portability story here; a round-trip importer is
  its own sprint with its own conflict rules.
- Scheduled or automatic export. Backups already cover the durability story (DEC-039/DEC-040).
- The domain generalization itself, and the `authors` → `creators` rename, both of which are
  Sprint 025.

## Commit checkpoints

1. `feat: export the library as entity-shaped JSON`
2. `feat: export a Goodreads-shaped CSV`
3. `feat: carry attachments in the export` (or the decided alternative)
4. final `docs(sprint-024): close sprint and hand off`

## Risks and decisions to surface

- **The attachment question is the sprint's only real decision** and it is a fork, not a detail:
  bytes make the export a multi-gigabyte archive rather than a file. Put it to the owner at
  activation rather than settling it quietly, as Sprints 021 and 022 did with theirs.
- A book-shaped format is the tempting shortcut and the one thing the roadmap forbids. Sprint 025
  will find it immediately.

## Outcome

**Completed 2026-08-14.**

### Delivered

`GET /api/export` streams the whole library as one JSON document — `kind`, `version`,
`generated_at`, then `items` and `entries`. An item is `type`, `title`, `subtitle`, `year`,
`creator_sort_override`, an opaque `metadata` object, `identifiers`, `sources` and `attachments`.
`?format=csv` returns the Goodreads-shaped CSV. Two commits: `01bfce1`, `afb1902`.

### Acceptance criteria

1. **Owner data survives, derived columns are absent.** Verified by test and again by reading a real
   export: a hand-corrected `creator_sort_override` and a renamed attachment both appear, and all
   five derived columns (`sort_author`, `creator_sort`, `title_normalized`,
   `sort_author_normalized`, `creator_sort_normalized`) are asserted absent.
2. **Entity-shaped.** An item whose `type` is `album`, carrying `{"creators": [...], "label": ...}`,
   exports through the same path with no branch and its metadata untranslated.
3. **CSV.** All seventeen product-spec 5.1 columns in Goodreads' order. A title with a comma, a note
   with an embedded quote *and* a newline, and accented names round-trip through `csv.DictReader`.
   Then opened for real in LibreOffice (`soffice --headless --convert-to xlsx`): 17 headers,
   `Carlos Ruiz Zafón` intact.
4. **Attachments decided and recorded** — references plus digest, DEC-054. Verified beyond the test:
   the exported sha256 resolved to `data/attachments/85/8565c3d…` and `sha256sum` matched, which is
   the property that makes omitting the bytes safe rather than merely cheap.
5. **Memory flat, measured.** 200 items vs 2000 items: output x10.0, peak **x1.07 (JSON)** and
   **x1.66 (CSV)**.

### Verification

`python scripts/validate_project.py` pass · `make format` · `make check` pass (ruff, mypy 39 files,
eslint, tsc, OpenAPI contract + frontend type check) · `make test` — **358 backend passed**, **99
frontend passed** · `npm run test:e2e` — **79 passed, 2 skipped** · `make build` · `make
smoke-container` pass · `git diff --check` clean.

Walkthrough against the real dev library: both artifacts downloaded with correct
`Content-Disposition` and content types; corrected a creator sort name by hand through
`PATCH /api/items/3` and confirmed by reading the re-exported JSON that
`García Márquez, Gabriel José` survived while `sort_author` kept the display name; attached a
1.5 MB epub, renamed it, and confirmed the export carried the **renamed** filename with its digest
and no inlined bytes.

### Deviations

- **Commit checkpoints 1 and 3 merged.** Attachment references are a field of the item payload, so
  "carry attachments in the export" had no separate slice to be. No broken state was committed.
- **The memory criterion needed a different instrument than planned.** An absolute bound on peak was
  written first and was wrong: peak is dominated by roughly 1 MB of fixed SQLAlchemy statement
  compilation that does not grow with the corpus, so a *small* library failed a bound the large one
  passed. Replaced with a comparison across two library sizes, which is what "flat" actually claims.
- **Two streaming defects the measurement caught**, both invisible to the functional tests: selecting
  mapped entities held the whole library in the `Session` identity map however small the batch, and
  `yield_per` did not fix it because SQLite's driver has no server-side cursor and materializes the
  result set regardless. Both paths now select columns and walk in keyset batches.
- **CSV formula neutralization was added and is not in the sprint plan.** A note beginning `=` is a
  formula to a spreadsheet, and the artifact exists to be opened in one. It alters bytes, so it is
  confined to the CSV; the JSON stays lossless and a test pins both halves.
- **`My Rating` halves the stored score** (round-half-up), inverting the import's doubling, so an
  odd hand-set score loses half a point in the CSV. The exact 1–10 value is in the JSON. `wishlist`,
  `dropped` and `unsorted` have no Goodreads spelling and are written verbatim rather than flattened
  into a neighbouring shelf.

### Impact on future sprints

Sprint 025 is unaffected and its seam 3 is confirmed rather than contradicted: `metadata` is passed
through untransformed, so nothing in the export learns a domain's field names and the album work
needs no format v2. The `test_export.py` case that exports an `album` item is already in place as
the regression that will catch it if that changes.
