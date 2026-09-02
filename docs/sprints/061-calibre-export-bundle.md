# Sprint 061 — Drag Calibre's own export bundle into the Calibre tab

**Status:** completed
**Depends on:** 033, 035
**Roadmap revision:** 32

## Objective

A third way into the Calibre tab, beside the folder picker and the mount: drop the
`part-NNNN.calibre-data` files Calibre's own *Export/import all calibre data* feature
produces, and get the same preview/commit/undo experience every other Calibre path
already has — including automatic ebook attachment, since the export's bytes are
already local once uploaded.

## Required context

- `docs/decisions.md` DEC-081 (the folder chooser and its one-deep `alternate`),
  DEC-082 (planning by identity), DEC-083 (importer-owned ebook attachment), DEC-124
  (this sprint's own decision — read it in full; the entries below assume it).
- `docs/specs/technical-spec.md` §6.5 (imports, as this sprint left it) and §7.1.
- `docs/specs/product-spec.md` §5.2.
- Code, read fresh: `backend/src/book_tracker/domain/importers.py`,
  `api/imports.py` (`_chosen_input`, `_multipart_form`, `_bundle`, `_export`),
  `domains/book/calibre.py` (`CalibreAdapter`, `CalibreImporter`,
  `_materialize_export` and the module-level `_decode_export_manifest` /
  `_export_library_key` / `_export_slice` helpers), `application/imports.py`
  (`_capped_attachment`, the `commit` attachment-install block),
  `frontend/src/api/imports.ts`, `frontend/src/pages/ImportPage.tsx`,
  `frontend/src/features/import/ExportPicker.tsx`.
- The owner's own two real export files were used throughout to verify the format
  against ground truth (`./exports/part-0001.calibre-data`,
  `./exports/part-0002.calibre-data` — gitignored, local-only, never committed; see
  "Explicit non-scope").

## Current implementation baseline

Sprint 033 left `ImportInputSpec.alternate` as a single optional nested spec, exactly
one level deep, and Calibre using it for the mount/typed-path input beneath the primary
folder-picker (`kind="directory"`). Sprint 035 added importer-owned ebook attachment as
an opt-in, always-second-upload flow, because a folder upload never has ebook bytes on
disk to begin with. `_chosen_input`/`_bundle` in `api/imports.py` assumed exactly one
multipart-shaped input per connector — true for every registered connector until this
sprint.

## Deliverables

1. **`ImportInputSpec.alternate: ImportInputSpec | None` generalizes to
   `alternates: tuple[ImportInputSpec, ...]`.** Still one level deep; every `field`
   across the primary and all alternates now pairwise distinct. Every caller
   (`api/imports.py`, the frontend `ImportInputSpec`/`ImportPage.tsx`, every fixture
   and conformance test) updated to the tuple shape — no compatibility shim.
2. **A fourth `ImportInputSpec.kind`, `"export"`**, for a small set of opaque files a
   source's own export feature produced. `ImportSource.export` is the materialized
   directory of raw, unread parts; `_export()` in `api/imports.py` validates filenames
   against a flat `members` pattern and streams them there, owning the directory's
   lifetime exactly as `_bundle` already owns a `directory` bundle's.
3. **`_multipart_form`** replaces the assumption that a connector has at most one
   multipart-shaped input: it parses the body once against the widest cap among the
   candidates and picks the one whose declared `field` the body actually carries,
   re-checking that candidate's own cap immediately after.
4. **`CalibreImporter._materialize_export`** reconstructs a library on disk from an
   uploaded export bundle: locates the manifest by content across the uploaded parts,
   verifies every extracted byte range's SHA-1 and part membership, confines every
   write path, and rebuilds `metadata.db` plus each book's cover and preferred ebook
   file at exactly the paths the **existing, unchanged** `CalibreAdapter` already
   expects. Calibre gains a third `ImportInputSpec` alternate, `kind="export"`,
   `field="parts"`.
5. **Automatic ebook attachment for the export path only.** `NormalizedImportRecord`
   gains `attachment_source`/`attachment_name`/`attachment_stage`; `CalibreImporter`
   populates the first two only when export-reconstructed bytes are actually on disk
   (a mount or folder upload never sets them); `stage` copies them into the batch
   directory; `ImportService` enforces `attachment_max_bytes` against the staged copy
   and installs a surviving one through the same `store_blob`/`record_file` path a
   manual `/batches/{id}/files` attachment already uses.
6. **`ExportPicker.tsx`**, a new multi-file drag-and-drop/click-to-choose component;
   `ImportPage.tsx` renders one independently-toggleable disclosure per alternate
   instead of a single one.

## Acceptance criteria

1. Dropping a real Calibre export's `part-*.calibre-data` files previews the same
   books, covers, ratings and shelves a mount or folder-picker import of the same
   library would, and additionally stages an ebook attachment automatically —
   verified against the owner's own 18-book export locally during development
   (`CalibreImporter().read(...)` against copies of the real files: 18 records, 18
   covers, 18 ebook files reconstructed, `attachment_source` set on every one).
2. Every extracted byte range is checked against its manifest SHA-1 before being
   trusted; a missing referenced part, a corrupted checksum, or a manifest naming a
   book path outside the library are each refused with `invalid_calibre_export`
   before anything unsafe is written.
3. The manifest is found by content, not by a fixed filename or upload position — the
   real export's own manifest lives in its second, smaller part, not its first.
4. The existing mount and folder-picker paths are unaffected: their own tests pass
   unmodified, and neither gains automatic ebook attachment (only the export path's
   reconstruction ever puts real ebook bytes where `CalibreAdapter._attachment` can
   find them).
5. `alternates` generalization breaks no existing single-alternate connector; every
   conformance rule that applied to a lone `alternate` now applies N-way.

## Required tests (TDD)

- Backend: a synthetic two-part export builder (`build_calibre_export` in
  `test_calibre_import.py`) mirroring the real verified structure — happy path,
  automatic attachment, manifest found regardless of upload order, missing part,
  corrupted checksum, malicious book-path traversal, undeclared member, over the
  declared file cap, and byte-for-byte record equality against an equivalent mount
  import (`test_a_calibre_export_and_a_mount_normalize_the_same_book_identically`).
- Conformance: N-way alternates (still one level deep, now pairwise distinct
  fields), `kind="export"` requiring `accepts_files` and `members`.
- Frontend: `ExportPicker` FormData assertion for a multi-file selection, both
  alternates rendering and toggling independently, `previewImport`'s `export` branch.
- E2E: a new spec drives the real `<input type="file" multiple>` with two in-memory
  files and asserts the multipart body carries exactly those two parts under field
  `parts` (written and reviewed; **not executed** — see Outcome).

## Verification

```bash
python scripts/validate_project.py
make format && make check
cd backend && uv run pytest   # 1225 passed
cd frontend && npm run typecheck && npm run lint && npm run test   # 196 passed
```

`npx playwright test` was not run — see Outcome.

## Explicit non-scope

- Reading `notes.db`, Calibre custom columns, or `config_dir`/plugin entries from the
  export.
- Multi-library exports — the manifest format assumes exactly one library path key;
  more than one is refused rather than guessed at.
- Re-deriving an export back out of Akasha.
- Committing `./exports/*.calibre-data` (the owner's real 181 MB + 15 KB export) as a
  test fixture — it stayed local, gitignored, used only for manual verification during
  development; the automated suite uses hand-built synthetic bundles matching the same
  verified structure.

## Outcome

Backend fully implemented, tested, and verified against the owner's real export data
(`CalibreImporter._materialize_export` run directly against copies of
`./exports/part-0001.calibre-data` and `part-0002.calibre-data`: 18 records, 18 covers,
18 ebook files reconstructed correctly, automatic attachment resolved). 1225 backend
tests pass (`pytest`), `ruff format`/`ruff check`/`mypy` clean. Frontend: `ExportPicker`
and the generalized alternates UI implemented; 196 frontend unit/component tests pass,
`tsc -b`/`eslint` clean; `frontend/openapi.json` regenerated and `api:check` passes.

**E2E was not run.** `frontend/node_modules/.vite/deps` is owned by `root` in this
environment (a pre-existing artifact, not caused by this sprint's changes), which
blocks Vite's dev server — and therefore Playwright's `webServer` auto-launch — from
writing to its own dependency cache. Asked the owner; agreed to skip live E2E
execution for this pass rather than attempt a privileged workaround. The new E2E spec
(`import.spec.ts`, "a Calibre export's part files are dropped in together and sent as-is")
is written and reviewed against the exact pattern of the already-passing folder-picker
E2E test, but is unexecuted. The DEC-025 walkthrough gate — dragging the owner's real
export into the running application — is likewise outstanding for the same reason and
should be the first thing whoever next has a working dev server runs.

No product or scope deviation from the plan the owner approved. The `alternate` field
name in prose during planning was "archive"; renamed to "export" during implementation
to avoid colliding with `ImportSnapshot.archive_name`/`archive_data`, which already mean
something unrelated (retaining a connector's original uploaded file for storage).
