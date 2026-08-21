# Sprint 033 — Calibre without a mount

**Status:** completed
**Depends on:** 032
**Roadmap revision:** 15

## Objective

Import a Calibre library by choosing its folder in the browser, with covers, with no `CALIBRE_DIR`, no container restart and no read against a library another process is holding open. The mount-backed picker and the typed path survive as secondary affordances on the same tab.

## Required context

- `docs/specs/technical-spec.md` §6.5 (imports, incl. the 032 additions), §7.1 (`/api/import/...`), §6.6 (the domain contract).
- `docs/specs/product-spec.md` §5.2 (Calibre), §7 (the `/import` screen as 032 left it).
- `docs/decisions.md`: DEC-080 (connector-declared guidance, the closed error set, the browse endpoint), DEC-078 (the importer boundary), DEC-025 (walkthrough gate), DEC-040/DEC-075 (data and mounts).
- Code, read fresh: `backend/src/book_tracker/domain/importers.py`, `api/imports.py` (`_source`, `MAX_IMPORT_BYTES`), `application/imports.py`, `domains/book/calibre.py` (`CalibreAdapter.confine`/`browse`/`read`/`_cover`/`stage`), `infrastructure/covers.py` (`prepare_uploaded_cover`), `frontend/src/pages/ImportPage.tsx`, `frontend/src/features/import/{ConnectorGuide,FolderPicker,SourceDropZone}.tsx`, `frontend/src/api/imports.ts`, `backend/tests/test_generic_imports.py`, `test_calibre_import.py`, `test_domain_conformance.py`, `frontend/e2e/import.spec.ts`, `frontend/e2e/seed.ts` (`stubImporters`).
- `docs/guides/adding-a-domain.md` (the importer half).

## Current implementation baseline

Sprint 032 left `ImportInputSpec` with a single `kind` of `upload | path`, plus `guide`/`empty_state`/`help_url`/`browsable`. `browsable` is the only precedent for one spec producing two affordances: the Calibre tab already renders a mount-backed folder picker *and* a typed path from one `kind="path"` spec. `ImportSource` carries `data`/`filename`/`path` — one file or one path, never a set. `_source()` in `api/imports.py` branches on `input.kind` and buffers an upload in memory against a global `MAX_IMPORT_BYTES` of 5 MiB. `CalibreAdapter` is constructed with a root `Path` and reads `metadata.db` plus `<book path>/cover.jpg` off that root; `stage` copies each `cover_source` through `prepare_uploaded_cover`. Everything the reader knows about a library it learns from a directory on disk.

Measured on the owner's libraries: `/home/ibz/Calibre Library` is 2 books, 416 KB of `metadata.db`, 3 `cover.jpg` files of which **one is `.caltrash/b/1/cover.jpg`, a deleted book**, and 32 MB total because of the `.epub` files. `/mnt/zima/large/data/media/calibre-library` is 21 books, 448 KB, 8.2 MB of covers, 95 MB total, 19% ISBN coverage. Both matter: the trash cover is why a cover filter cannot be a `cover.jpg` glob, and the low ISBN coverage is why covers cannot simply be dropped and refilled by enrichment.

Verified in Chromium via Playwright before planning: `<input webkitdirectory>` is driven in tests by passing a real directory path; `webkitRelativePath` is populated; **its first segment is the picked folder's own name**; hidden directories and ebooks are both included in the file list, so client-side filtering is what keeps the payload small.

## Deliverables

1. **A connector may declare a second way in.** `ImportInputSpec` gains `kind="directory"` and `alternate: ImportInputSpec | None`, rendered below the primary. Depth is exactly one — an `alternate` may not itself carry an `alternate` — and the two specs must use different `field` names. `ImportInputSpec` also gains `max_bytes: int | None` and `max_files: int | None`, defaulting to today's global limits, so a connector that needs a bigger envelope declares it instead of the shared route raising the ceiling for everyone.
2. **A source may be a folder.** `ImportSource` gains `directory: Path | None`, a materialized bundle at `<directory>/library/<relative path>` — **not** a `Mapping[str, bytes]`, which would put peak memory at the size of the library rather than of one cover and contradict AC5. `_source()` in `api/imports.py` grows a `directory` branch that **streams parts to a temporary file rather than buffering them in memory** (a 256 MiB ceiling buffered on a ZimaBoard is not acceptable), enforces the declared byte and file caps, and refuses any relative path that is absolute, contains `..`, starts a segment with `.`, or is not `metadata.db` or `*/cover.jpg`.
3. **The reader does not learn a second way to read.** `CalibreImporter.read` materializes an uploaded bundle into a temporary directory at its declared relative paths and points the **existing** `CalibreAdapter` at it. `confine`, `_records`, `_cover` and `stage` are untouched, so an uploaded library and a mounted one normalize through exactly the same code and `test_calibre_import.py` stays the net. The temporary directory is removed after `stage` has copied what it needs.
4. **The Calibre tab leads with the folder.** A new `features/import/DirectoryPicker.tsx`: an `<input webkitdirectory>`, a client filter that strips the leading path segment, drops any path with a dot-segment and keeps only `metadata.db` plus `*/cover.jpg`, and a summary of what will be sent (`"2 books · 2 covers · 2.4 MB"`) before anything uploads. Below it, the 032 mount picker and typed path render from `input.alternate` unchanged. A library whose selection has no `metadata.db` is refused in the browser with the connector's own copy, before any request.
5. **Conformance and documentation.** The suite rejects a nested `alternate`, an `alternate` sharing the primary's `field`, `max_bytes`/`max_files` that are not positive, and `kind="directory"` on a connector whose reader cannot take `files`. README's *Importing and triage*, `docs/guides/adding-a-domain.md`, technical spec §6.5/§7.1 and product spec §5.2/§7 all follow.

## Acceptance criteria

1. With **no `CALIBRE_DIR` configured and no mount present**, choosing `/home/ibz/Calibre Library` in the Calibre tab previews 2 books with 2 covers staged, and committing lands them in Triage with those covers. No container restart is involved at any point.
2. The client sends `metadata.db` and the two book covers and **nothing else**: not the `.epub`, not `metadata.opf`, not `metadata_db_prefs_backup.json`, and not `.caltrash/b/1/cover.jpg`. Asserted on the request, not on the screen.
3. The mount-backed picker and the typed path still work from `input.alternate`, unchanged, against a configured `CALIBRE_DIR`. `test_calibre_import.py` passes unmodified.
4. The upload route refuses, with the connector's own 422 and without writing anything: an absolute member path, one containing `..`, one whose segment starts with `.`, a member that is neither `metadata.db` nor `*/cover.jpg`, a bundle with no `metadata.db`, a bundle over the declared `max_bytes`, and one over `max_files`.
5. Peak process memory during a directory import stays proportional to the largest single member rather than to the bundle, demonstrated against a bundle at least 10x `MAX_IMPORT_BYTES`.
6. Conformance rejects each malformed declaration in deliverable 5. The frontend renders the primary and the alternate, and the existing 032 guidance and error-action behavior is unchanged.
7. The walkthrough gate passes: import `/home/ibz/Calibre Library` through the browser with the mount absent, confirm the covers are real, triage the result, undo it, then re-run against a configured mount to prove the alternate still works.

## Required tests (TDD)

- Backend: each refusal in AC4; a bundle materializing to a temp dir that the existing adapter reads identically to the same library on disk; the temp dir removed after staging; the streaming memory bound in AC5; per-connector caps honoured over the global default.
- Conformance: nested `alternate`, colliding `field`, non-positive `max_bytes`/`max_files`, `directory` without file support.
- Frontend: the filter keeps exactly `metadata.db` + `*/cover.jpg` and strips the leading segment; the summary counts and sizes; a selection with no `metadata.db` is refused before any fetch; the alternate renders below the primary.
- E2E: drive `<input webkitdirectory>` with a real fixture directory containing an ebook and a `.caltrash` cover, assert the multipart body carries three parts and their names.

## Verification

```bash
python scripts/validate_project.py
make format && make check && make test
cd frontend && npx playwright test
git diff --check
```

Plus the walkthrough gate in AC7, recorded in `docs/agent/worklog.md`.

## Explicit non-scope

- **Removing the mount, `CALIBRE_DIR` or the browse endpoint.** The owner chose to keep them as secondary affordances on the same tab; deleting them is a separate decision.
- **A directory import for Goodreads.** Goodreads is one file and stays `kind="upload"`.
- **Re-sync scheduling.** Still no scheduler; an import is still something you trigger.
- **Reading ebooks, `metadata.opf`, or Calibre custom columns.** The bundle is `metadata.db` plus covers.

## Commit checkpoints

1. `feat(sprint-033): a connector may declare a second way in`
2. `feat(sprint-033): accept a calibre bundle without a mount`
3. `feat(sprint-033): choose a calibre folder in the browser`
4. `docs(sprint-033): calibre without a mount`
5. final `docs(sprint-033): close sprint and hand off`

## Risks and decisions to surface

- **Streaming multipart.** FastAPI/Starlette's `request.form()` buffers to memory by default; `max_part_size` and spooled files need checking against AC5 rather than assumed. If Starlette cannot stream at the needed granularity, the fallback is a documented lower `max_bytes`, not a silent buffer.
- **`webkitdirectory` support.** Confirmed present in current Chromium and driveable from Playwright. It is not in the HTML standard proper; if a target browser lacks it, the alternate is the mount — which is precisely why the owner kept it.
- **Bundle size on a real shelf.** 8.2 MB for 21 books extrapolates to roughly 400 MB for 1000. `max_bytes` must be a considered number with a clear refusal, not a hopeful one.
- **Temp directory lifetime.** A failed preview must not leave a bundle on disk; a fingerprint replay must not need it to still be there.

## Outcome

**Completed 2026-08-21.** Commits: `1f5ad81` (contract and bundle route), `a0ea09b` (the folder
chooser and the alternate), `18105c4` (documentation), and the closing state commit.

### Acceptance criteria

1. **Imported with no mount.** Walked against `/home/ibz/Calibre Library` with `CALIBRE_DIR` pointed
   at an empty directory: 18 books previewed, **18 of 18 covers staged**, committed into Triage, no
   restart anywhere. The library had grown from the 2 books measured at planning time to 18, which
   made the walkthrough a better test than the plan expected.
2. **Only the database and the covers travel.** Of 71 files the browser handed over, 2 were sent —
   `metadata.db` and 18 covers totalling 10.0 MB, with 52 left behind. Asserted on the multipart
   body in `import.spec.ts` against a fixture library containing an ebook, a `metadata.opf`, a prefs
   backup and a `.caltrash` cover, and on the FormData in `ImportPage.test.tsx`.
3. **The alternate still works.** Re-ran against a configured mount: the picker browsed to
   `Estantería/Calibre Library`, confirmed it held a library, previewed 18 rows and staged 18 covers.
   `test_calibre_import.py` passes unmodified.
4. **Every refusal covered.** Absolute member, `..`, mid-path `..`, hidden directory, hidden file, an
   `.epub`, a `metadata.opf`, and a `metadata.db` below the root are each refused 422 with nothing
   written outside the bundle; a bundle with no database and one over each declared cap are refused
   too, the latter 413 naming the alternate.
5. **Streaming holds.** A 60 MiB bundle (12x the shared cap) previews at a **1.8 MiB Python peak**,
   asserted with a bound of 8 MiB, plus a direct test that the spool threshold is 1 rather than 0 —
   `SpooledTemporaryFile` treats 0 as *never roll*, which is the trap that would silently restore the
   in-memory behavior.
6. **Conformance rejects each malformed declaration**, and the screen renders the primary with the
   alternate beneath it.
7. **Walkthrough passed**, both arms, recorded in `docs/agent/worklog.md`.

### Verification

`python scripts/validate_project.py` (pass), `make format` (no drift), `make check` (green),
`make test` (**backend 522 passed**, **frontend 171 passed**), `npx playwright test`
(**96 passed, 2 skipped**), `git diff --check` (clean).

### Deviations and decisions

- **`ImportSource` carries `directory`, not `files: Mapping[str, bytes]`.** Deliverable 2 as planned
  contradicted AC5 in the same document: a mapping of bytes puts peak memory at the size of the
  library. Caught while implementing; the plan text was corrected in place and the contract carries a
  materialized bundle directory instead. This is also what let deliverable 3 be literally true —
  the connector points the existing adapter at the bundle and `CalibreAdapter` is unchanged.
- **`accepts_files` was added** beyond the planned fields, so `kind="directory"` is a promise about
  the reader rather than only about the screen, and conformance can refuse the mismatch.
- **The alternate is a controlled disclosure, not `<details>`.** jsdom does not toggle native
  `details` on a summary click, and an explicit `aria-expanded` button is both testable and clearer
  to announce.
- **`_chosen_input` picks by content type.** With two inputs on one route, the declaration can no
  longer say which is in use; the request does. The browse endpoint likewise now consults the
  alternate, since `browsable` moved off the primary.

### Impact on future work

The numbered plan ends here again. The unnumbered epics inherit `alternate`, `kind="directory"` and
per-input envelopes. Two things a future connector should know: `ImportInputSpec.kind` is now
`upload | path | directory` and an OAuth handshake is still none of them, which the Spotify epic will
meet first; and `alternate` is one level deep by contract, so a source with three ways in needs a
different shape rather than a longer chain.
