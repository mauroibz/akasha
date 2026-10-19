# Sprint 086 — Drop ebook files

**Sprint:** 086
**Status:** ready
**Roadmap revision:** 44
**Depends on:** 085
**Owner:** Mauro

## Objective

The owner's 2026-10-19 report, verbatim: "a simple UX flow i want and cannot do: open akasha,
click Add, drag 3 epub files from my downloads folder and have them processed and added to the
library/triage." After this sprint that flow works: EPUB files dropped on the Add screen are read
for their embedded metadata, previewed, committed into Triage with their cover, and attached to
the book they describe. Ships as v2.3.0 and is installed on the owner's ZimaBoard.

## Required context

- `AGENTS.md`, `docs/agent/WORKFLOW.md`, `docs/agent/TESTING.md`.
- Product spec §1 (the "not an ebook server" non-goal and its importer paragraph) — this sprint
  amends it (DEC-164).
- Technical spec §6.6 (domain contract) and the importer sections; `docs/guides/adding-a-domain.md`
  for how connectors register.
- DEC-083 (importer-owned attachments, the export bundle's server-side attachment), DEC-081
  (alternates and bundle kinds), DEC-080 (declared guidance), DEC-008 (enrichment fills empty
  fields only).
- `backend/src/book_tracker/domain/importers.py` (the contract), `domain/registry.py`,
  `domains/book/calibre.py` (the `export` kind reader and `stage` with `attachment_source`),
  `api/imports.py` (`_export`, `_bundle_member`, catalog response),
  `application/imports.py` (attachment install on commit).
- `frontend/src/pages/AddPage.tsx`, `frontend/src/pages/ImportPage.tsx`,
  `frontend/src/features/import/ExportPicker.tsx`, `frontend/src/api/imports.ts`.

## Current implementation baseline

Measured 2026-10-19 in this worktree:

- **Add** (`AppShell.tsx:47` → `/add`) is the manual-entry form only; it has no upload surface.
- No connector reads a loose ebook. EPUBs enter only through the Calibre importer, as attachments
  of books that `metadata.db` already describes.
- The `export` input kind (Calibre's export bundle) is already a flat multi-file upload: the route
  streams each declared member to `<export>/parts/<name>` (`api/imports.py` `_export`), and a
  reader that sets `attachment_source` gets the file copied by `stage` and attached on commit
  (`application/imports.py`). This is the whole pipeline the new connector needs.
- `ExportPicker.tsx` hardcodes Calibre: `accept=".calibre-data"`, the testid, and the
  "doesn't look like part of a Calibre export" check — a shared component that names a connector.
- Product spec §1 forbids "format parsing"; ROADMAP's attachment section names "reading an
  uploaded epub's OPF as another metadata provider" as the natural next step, left out on purpose.
- The owner's real file (DDIA 2nd edition, O'Reilly, 6.5 MB) carries: an unschemed hyphenated
  ISBN `978-1-098-11906-5` as `dc:identifier`; a `dc:title` with a personalization stamp
  ("Designing Data-Intensive Applications (for …)") beside a clean `dcterms:title` meta; one
  `dc:creator` naming both authors joined by "and"; a PNG cover declared both ways
  (`properties="cover-image"` and `<meta name="cover">`).

## Deliverables

### D1 — An "Ebook files" connector (backend)

1. `domains/book/epub.py`: `EpubImporter`, name `epub`, label "Ebook files", targets `book`,
   identity kinds `{"isbn"}`, input `kind="export"`, `field="files"`, `accept=".epub"`,
   `members=("*.epub", "*.EPUB")`, a declared guide and empty state, `max_files=100`,
   `max_bytes=2 GiB`. Registered in `REGISTERED_IMPORTERS`.
2. The reader opens each file as a ZIP, follows `META-INF/container.xml` to the OPF, and reads
   title (a `dcterms:title` meta wins over `dc:title` when present), creators (EPUB2 `opf:role`
   and EPUB3 `refines` roles: authors only when roles are given; one creator string joined by
   "and", "&" or ";" splits), publisher, language, date → year, description (tags stripped),
   subjects, ISBN (any `dc:identifier` that normalizes as an ISBN, `urn:isbn:` prefix accepted),
   series (`calibre:series` or EPUB3 `belongs-to-collection`).
3. The cover is found by EPUB3 `cover-image`, then EPUB2 `<meta name="cover">`, and handed to
   the shared cover pipeline; the EPUB itself becomes the record's attachment.
4. A file that is not a readable EPUB becomes **one** errored row named after the file — it
   never fails the batch. Bounded reads: container/OPF capped at 1 MiB, cover at the cover cap,
   a DTD with entities refused.
5. Fingerprint is a digest of every file's bytes, so dropping the same files twice replays.

### D2 — Shared surfaces stop naming Calibre, and the Add screen gets a door

1. `ImportInputSpec.quick_add: bool` — a connector declares it may be offered on the Add screen.
   Published on the catalog and in OpenAPI. Only the EPUB connector sets it.
2. `ExportPicker` renders from its declaration: `accept`, testid from the importer id, and the
   "unexpected file" line from the declared extensions.
3. `AddPage` renders a drop zone (and a multiple file input) for every importer whose input
   declares `quick_add`. Dropping or choosing files opens the Import screen on that connector with
   the files already chosen and the preview already running.
4. The import route's "no parts" refusal copy stops saying "export".

### D3 — Spec, docs, release, install

1. Product spec §1 amended (DEC-164); technical spec importer list and `quick_add` documented.
2. Release v2.3.0 (version surfaces, notes, tag, images, GitHub Release).
3. The ZimaBoard runs `AKASHA_VERSION=2.3.0`.

## Acceptance criteria

1. Three EPUBs dropped on Add reach a preview with three rows: title, creators, ISBN where
   present, cover staged, attachment staged.
2. Commit lands them in Triage (unsorted) with the EPUB attached to each item and the cover
   installed.
3. The owner's DDIA file reads as "Designing Data-Intensive Applications", creators
   ["Martin Kleppmann", "Chris Riccomini"], ISBN 9781098119065, publisher "O'Reilly Media, Inc.",
   language en, year 2024, a cover.
4. A broken file among good ones yields one errored row and the rest still import.
5. A book already in the library by ISBN matches rather than duplicates.
6. Re-dropping the same set replays the existing batch.
7. A non-EPUB member is refused by the shared route before a byte is written.
8. No shared layer branches on the connector: conformance suite green, `ExportPicker` has no
   connector name in it.

## Required tests (TDD)

- Backend unit (`tests/test_epub_import.py`): metadata extraction on built EPUB2 and EPUB3
  fixtures, the `dcterms:title` rule, creator splitting and role filtering, ISBN normalization,
  cover discovery both ways, broken file → errored row, entity DTD refused, fingerprint stability.
- Backend API: preview → commit → item in Triage with attachment and cover; ISBN match against an
  existing item; replay; undeclared member refused; `quick_add` on the catalog.
- Vitest: `ExportPicker` from declaration; `AddPage` renders the quick-add zone and hands files
  to Import; `ImportPage` consumes handed files and previews.
- Playwright: Add → drop → preview → commit → Triage, with the API stubbed the way the import
  specs do.

## Verification

- `make check`, `make test`, `npm run test:e2e` (from `frontend/`), `make smoke-container`,
  `python scripts/validate_project.py`, `git diff --check`.
- Walkthrough: fresh data dir via `scripts/walkthrough.py`, the owner's DDIA EPUB plus two
  generated EPUBs dropped on Add in a real browser, committed, checked in Triage and on the detail
  page (cover, attachment).

## Explicit non-scope

- Formats other than EPUB (azw3, mobi, pdf) — no open metadata container to read reliably.
- A reader, reading progress, or any format-aware file UI (product spec §1 stands on these).
- Dropping files anywhere in the app outside Add and Import.
- Writing metadata back into the EPUB.

## Commit checkpoints

1. `[ADD]` the EPUB connector with its tests.
2. `[MOD]` the shared export picker reads its declaration; `[ADD]` the Add-screen drop zone.
3. `[DOCS]` spec amendment and docs; `[DOCS]` close and hand off; version bump and notes.

## Risks and decisions to surface

- **Spec amendment** (DEC-164): reading an EPUB's embedded metadata is the format parsing §1
  forbade. The owner asked for the flow directly; the amendment is scoped to an importer reading a
  file's own metadata, and the file surface stays format-agnostic.
- **Creator splitting on "and"** can split a name that legitimately contains it. Rare in creator
  fields; editable after import.
- **`dcterms:title` preference** follows the owner's real file; a publisher that puts a worse
  value there would lose. The detail page edits either way.

## Outcome

_Not started._
