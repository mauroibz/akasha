# Handoff — Sprint 032 planned and ready

Plan revision 14. Sprint 031 closed the per-domain import boundary on 2026-08-21; the owner used it and reported two UX defects plus one architectural gap, all scheduled as **Sprint 032 — Import UX and connector extensibility** (DEC-079). The sprint file exists at `docs/sprints/032-import-ux-and-connector-extensibility.md`, status `planned`; state.json points at it as `ready`. The project is no longer `complete`; FINAL_SPRINT in `scripts/validate_project.py` moved 31 → 32.

What 032 delivers: Triage folded into Import as a tab (the `TriagePage` component moves unchanged; `/triage` stops being a top-level route, with a redirect recommended); Goodreads guidance plus drag-and-drop; Calibre guidance plus a browsable folder picker backed by a new read-only, mount-confined `GET /api/import/calibre/browse` endpoint; and declarative extensions to the importer contract (`ImportInputSpec.guide`/`empty_state`/`help_url`, `ImportReadError.user_message`/`action`) with conformance checks. The reader suites are the no-behavior-change net. The walkthrough gate applies.

Open decisions recorded in the sprint file's risks section: whether `/triage` redirects or 404s (redirect recommended); the browse endpoint returns names only, never absolute paths; guide rendering as plain ordered steps vs markdown (steps recommended); the Import screen's default tab should remember the last source used, mirroring DEC-062.

Known and left, in the order they are likely to bite:

1. Sprint 031's final combined `make test` was waived by the owner mid-run (482 backend tests collected, interrupted in `test_export.py`; frontend stage not reached). It is recorded as **not completed**, not green. 032's Verification section requires the full run.
2. `ImportPage.test.tsx` and the e2e specs stub `/api/importers` with the current `ImportInputSpec` shape; extending the spec means extending those fixtures.
3. The e2e specs `goto("/triage")` in eleven places (`frontend/e2e/triage.spec.ts`, `accessibility.spec.ts`, `import.spec.ts`, `editorial.spec.ts`) and must move to the folded path.
4. `frontend/src/pages/HomePage.tsx:537` (Inbox button) and `ImportPage.tsx:320` (post-commit link) navigate to `/triage` and must follow.

No tag, push, release, or deployment has been performed for this work.
