# Sprint 032 — Import UX and connector extensibility

**Status:** ready
**Depends on:** 031
**Roadmap revision:** 14

## Objective

Make the import flow self-explanatory and self-serving for users, and make the `Importer` contract expressive enough that a future connector can guide its own users without editing shared screens. Two owner-visible defects drive it: Triage is a dead tab unless Import is run first, and neither importer explains itself — Goodreads does not say where the CSV comes from, Calibre says only "relative folder only" with no anchor to the filesystem. A third, architectural, goal follows: the contract must let a connector ship its own help copy, its own input affordances (drag-and-drop, path browsing), and its own custom error vocabulary, so the next importer (Spotify, Steam) is a package, not a package plus a screen patch.

## Required context

- `docs/specs/technical-spec.md` §6.5 (imports), §6.6 (the domain contract), §7.1 (the `/api/import/...` route contract).
- `docs/specs/product-spec.md` §5 (imports), §7 (screens: `/import` and `/triage`).
- `docs/decisions.md`: DEC-078 (the importer boundary as built), DEC-076 (the measured coupling), DEC-025 (walkthrough gate), DEC-028 (one visible feedback surface), DEC-062 (tab default is last domain used).
- Code, read fresh: `backend/src/book_tracker/domain/importers.py`, `application/imports.py`, `api/imports.py`, `domains/book/goodreads.py`, `domains/book/calibre.py`, `frontend/src/pages/ImportPage.tsx`, `frontend/src/pages/TriagePage.tsx`, `frontend/src/api/imports.ts`, `frontend/src/App.tsx`, `frontend/src/components/AppShell.tsx`, `frontend/src/pages/HomePage.tsx` (the Inbox button), `frontend/e2e/import.spec.ts`, `frontend/e2e/triage.spec.ts`, `frontend/src/pages/ImportPage.test.tsx`.
- `docs/guides/adding-a-domain.md` (the importer half of the guide), `README.md` (the *Importing and triage* section).

## Current implementation baseline

Sprint 031 shipped the `Importer` protocol, generic `/api/import/{importer}/preview|commit` routes, and registry-driven tabs on `ImportPage.tsx`. Triage remains a separate top-level route (`/triage`) with its own nav item; it is empty unless an import has landed `unsorted` rows. The Goodreads tab is a bare file input with no guidance on obtaining the CSV. The Calibre tab is a text input whose only help is "Enter a relative folder only" — the user has no way to know what folders exist under the configured mount. `ImportInputSpec` carries only `kind`, `label`, `field`, `accept`, `placeholder`, `help`; there is no declarative way for a connector to publish richer guidance, a drag-and-drop affordance, a browsable path picker, or a typed error with a user-actionable message. `ImportReadError` carries `code`/`message`/`details`, but the API maps it to a flat 422 and the frontend renders only `error.message`.

## Deliverables

1. **Fold Triage into Import.** Remove `/triage` as a top-level route and nav item. The Import screen gains a third tab (or a subscreen) labelled *Triage* that renders the existing `TriagePage` component. The Inbox button on `/` and the post-commit "waiting in Triage" link navigate to `/import?tab=triage` (or equivalent). The `TriagePage` component itself is unchanged except for its route wrapper; its keyboard map, bulk bar, and virtualized table are preserved. E2E specs that `goto("/triage")` are updated to the new path.
2. **Goodreads explains itself.** The Goodreads tab shows a short guide: where the export lives (`goodreads.com/review/import` → Export Library, desktop web only), that it is a snapshot not a sync, and what Akasha does with it (ratings doubled and marked provisional, shelves become tags, everything lands `unsorted`). The file input becomes a drag-and-drop zone that also accepts click-to-browse, with the accepted types (`.csv`) stated.
3. **Calibre explains itself and shows where you are.** The Calibre tab shows what the import does (read-only, fills empty fields only, your edits win, covers copied). The path input is replaced or augmented by a browsable folder picker: the backend exposes a read-only `GET /api/import/calibre/browse?path=` that lists immediate subdirectories of the configured Calibre mount (names only, no file contents, no traversal outside the mount), and the frontend renders a simple breadcrumb + folder list so the user never types a path blind. The current typed-path fallback remains for automation.
4. **Connector-declared guidance and errors.** `ImportInputSpec` gains optional declarative fields so a connector can publish: a `guide` (markdown or ordered steps rendered on its tab), an `empty_state` (what to show when the source is missing), and a `help_url`. `ImportReadError` gains an optional `user_message` and `action` (a short imperative sentence, e.g. "Close Calibre and try again"); the API surfaces them in the 422 payload and the frontend renders the action beside the message. The conformance suite asserts that a registered importer's declared fields are well-formed and that its error codes are a closed set.
5. **Documentation.** `README.md`'s *Importing and triage* section is rewritten to describe the folded flow. `docs/guides/adding-a-domain.md` gains the new declarative fields in its importer example. `docs/specs/technical-spec.md` §6.5 and §7.1 are updated for the browse endpoint and the extended error payload. `docs/specs/product-spec.md` §7 is updated so `/import` describes the folded tabs and `/triage` is no longer a separate screen.

## Acceptance criteria

1. `/triage` is no longer a top-level route or nav item. The Import screen contains a Triage tab that renders the existing triage surface; the Inbox button and post-commit link land on it. All existing triage keyboard shortcuts, bulk operations, and virtualized behavior work unchanged under the new path.
2. The Goodreads tab renders connector-declared guidance that includes the export location and the snapshot/provisional-score semantics, and its file input accepts drag-and-drop as well as click-to-browse.
3. The Calibre tab renders connector-declared guidance and a browsable folder picker rooted at the configured mount; the user can navigate into a subfolder and preview without typing a path. The browse endpoint refuses paths that escape the mount and returns only directory names.
4. A connector can declare `guide`, `empty_state`, `help_url`, and custom `user_message`/`action` on its errors; the conformance suite rejects a malformed declaration. The frontend renders the declared guidance and the custom error action.
5. `test_goodreads_import.py` and `test_calibre_import.py` pass unmodified (no behavior change in the readers). New tests cover the browse endpoint's confinement, the extended 422 payload, and the conformance checks.
6. The walkthrough gate passes: import from both sources through the folded UI, use the folder picker, triage the results inside the Import screen, and record what was exercised and observed.

## Required tests (TDD)

- Backend: browse endpoint returns only directories, refuses `..` and absolute paths, and stays inside the mount; extended `ImportReadError` fields appear in the 422 JSON; conformance rejects an importer with an undeclared error code or malformed guide.
- Frontend: ImportPage renders the Triage tab; Goodreads tab shows guidance and drop zone; Calibre tab shows breadcrumb and folder list; error surface renders `action` when present.
- E2E: update `import.spec.ts` and `triage.spec.ts` to the folded path; add a flow that browses into a Calibre subfolder and previews.

## Verification

```bash
python scripts/validate_project.py
make format && make check && make test
git diff --check
```

Plus the walkthrough gate: run the app against realistic data, import from both book sources through the folded UI, use the Calibre folder picker, triage the `unsorted` results inside the Import screen, undo one batch inside its window, and record what was exercised and observed in the worklog.

## Explicit non-scope

- **A second importer.** Spotify/Steam remain future epics; this sprint only makes their connector self-describing.
- **Triage feature changes.** No new filters, grouping, or bulk actions; the surface is moved, not redesigned.
- **Calibre write-back or live sync.** Still read-only.

## Commit checkpoints

1. `feat(sprint-032): fold triage into import`
2. `feat(sprint-032): goodreads guidance and drag-and-drop`
3. `feat(sprint-032): calibre folder browse and guidance`
4. `feat(sprint-032): connector-declared guidance and custom errors`
5. `docs(sprint-032): import ux and connector extensibility`
6. final `docs(sprint-032): close sprint and hand off`

## Risks and decisions to surface

- **Route compatibility.** `/triage` is a public URL; removing it breaks bookmarks and the Inbox button. The sprint must decide whether to keep a redirect from `/triage` to `/import?tab=triage` (recommended) or let it 404.
- **Browse endpoint shape.** A naive directory list leaks host filesystem layout. The endpoint must return only names, never absolute paths, and must resolve confinement the same way `CalibreAdapter.read` does.
- **Guide rendering.** Markdown in `ImportInputSpec` is the cheapest way to let a connector write its own help, but it introduces a rendering dependency. Plain ordered steps (list of strings) is safer and sufficient; decide before implementation.
- **Tab default.** DEC-062 settled the library tab default as "last domain used". The Import screen's default tab (Goodreads vs Calibre vs Triage) needs the same treatment; recommend remembering the last import source used.

## Outcome

_Not started. On completion record delivered behavior, commands and actual results, commit IDs, deviations/decisions, and impact on every future sprint._
