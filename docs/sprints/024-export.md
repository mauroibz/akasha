# Sprint 024 — Export

**Status:** ready
**Depends on:** 020
**Roadmap revision:** 9

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
   (backup and its manifest, the closest prior art for a generated artifact)
5. `backend/src/book_tracker/backup.py` — how a whole-library artifact is currently produced,
   verified and streamed; reuse its shape rather than inventing a second one
6. `backend/src/book_tracker/application/library.py`, `_item_dict` and `_entry_dict` — the existing
   serialization of exactly the two entities being exported
7. `backend/src/book_tracker/api/library.py` — `ItemResponse`/`EntryResponse` and the streaming
   response pattern already used by attachment downloads
8. `backend/src/book_tracker/infrastructure/models.py` — which columns are owner data and which are
   derived
9. Sprint 023 Outcome and `docs/agent/HANDOFF.md`

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

_Not started. On completion record delivered behavior, commands and actual results, commit IDs,
deviations/decisions, and impact on every future sprint._
