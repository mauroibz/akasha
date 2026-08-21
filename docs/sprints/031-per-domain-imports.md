# Sprint 031 — Per-domain imports

**Status:** completed
**Depends on:** 030
**Roadmap revision:** 13

## Objective

Import stops being book-shaped above the readers. One `Importer` contract beside the `Provider`
protocol, registered per domain; one generic preview/commit service and `/api/import/{importer}/...`
routes; Calibre and Goodreads re-expressed against that boundary with **no behavior change**; manual
entry honours the domain (DEC-067 row 6); and the README plus `docs/guides/adding-a-domain.md` tell
the import/triage story so a contributor can build a connector from the guide alone. The last sprint
in the plan: when it closes, the project goes `complete` per `WORKFLOW.md`'s final-sprint rule.

## Required context

- `docs/specs/technical-spec.md` §6.6 (the domain contract) and §6.5 (import/undo semantics).
- `docs/decisions.md`: DEC-076 (the measured coupling — five named places), DEC-069 (readers belong
  to their domain), DEC-067 row 6 (manual entry honours the domain), DEC-073 (why `/add` names one
  domain today), DEC-077 (entry depth: an importer creates flat entries and provider `rows`
  metadata, never child entities — the boundary is unaffected by depth).
- `docs/entry-depth-verdict.md` — the Sprint 030 verdict 031 was impact-reviewed against.
- Code, read fresh, not from DEC-076's summary: `backend/src/book_tracker/application/imports.py`,
  `api/imports.py`, `infrastructure/repositories.py` (`ImportRepository.commit`),
  `application/add.py`, `domains/book/goodreads.py`, `domains/book/calibre.py`,
  `domain/providers.py` (the protocol the `Importer` contract sits beside),
  `frontend/src/pages/ImportPage.tsx`, `frontend/src/api/imports.ts`,
  `frontend/src/pages/AddPage.tsx`.
- Tests: `backend/tests/test_goodreads_import.py`, `test_calibre_import.py`,
  `test_domain_conformance.py`, `test_undo.py`.
- `README.md` (the one bullet that names import today) and `docs/guides/adding-a-domain.md`.

## Current implementation baseline

Re-derive at activation; DEC-076's measurement (2026-08-20) is the map, not the territory. As of
Sprint 030's close: the batch/record/effect tables are keyed by an opaque `normalized_payload` and
a `kind` string; undo, fingerprint idempotency and triage are domain-agnostic end to end. The book
shape lives in five places: `api/imports.py` (per-source routes, book-typed preview record),
`application/imports.py` (two service classes, `first_author=` in the match call, ISBN/`calibre_uuid`
identity only), `ImportRepository.commit` (reads `payload["isbn"]`, fixed book metadata key list,
`type=DEFAULT_DOMAIN.item_type` on created items, writes book entry fields), `ImportPage.tsx` /
`api/imports.ts` (hardcoded tabs and typed fields), and `AddService.add` (manual payload bound to
`DEFAULT_DOMAIN`). Sprint 030 changed none of this — it was a documentation-only sprint and its
verdict leaves this contract intact.

## Deliverables

1. **The `Importer` contract** beside the `Provider` protocol in `domain/`, registered per domain,
   with conformance checks in `test_domain_conformance.py` so an importer is held to the contract
   by existing.
2. **The generic pipeline**: one preview/commit service replacing the two copy-pasted ones, and
   `/api/import/{importer}/...` routes replacing the per-source ones. The set of available importers
   is published over the API the way `GET /api/item-types` publishes domains; `ImportPage.tsx`
   renders its tabs from that data. Normalized records are validated against the target domain's
   own declaration — metadata against `fields`, entry values against `entry_fields`, using the
   validators `AddService` already uses.
3. **Calibre and Goodreads re-expressed** against the boundary with no behavior change; their
   existing suites are the regression net.
4. **DEC-067 row 6**: `AddService.add` takes the manual payload's domain from the client and
   validates against that domain's field spec; `/add` gains the domain chooser back, truthfully.
5. **The documentation**: a real *Importing and triage* section in `README.md` (what triage is,
   when a re-run is relevant — Calibre re-sync fills empty fields only and your edits always win —
   and that committed rows land `unsorted` where the default library hides them), and the importer
   half of `docs/guides/adding-a-domain.md` beside the provider steps.

## Acceptance criteria

1. An `Importer` contract exists beside the `Provider` protocol; both book importers are registered
   against it, and `test_domain_conformance.py` holds importers to it.
2. `/api/import/{importer}/...` routes serve both existing importers; the per-source routes are
   gone or delegate. The available-importer set is published over the API and `ImportPage.tsx`
   renders tabs from it, not from literals.
3. `ImportRepository.commit` (or its successor) reads identity and metadata from the domain's
   declaration, never from a book key list; no `DEFAULT_DOMAIN` binding remains in the import or
   manual-add paths.
4. `test_goodreads_import.py` and `test_calibre_import.py` pass **unmodified** — no behavior change
   is the regression net — plus new tests for the generic validation against a domain's own
   `fields`/`entry_fields`.
5. Manual add honours the chosen domain end to end: a manually added album validates against album
   fields and lands as an album.
6. The README's *Importing and triage* section and the guide's importer half exist and match the
   implemented routes and contract.
7. Undo, fingerprint idempotency and triage are untouched in behavior: `test_undo.py` passes
   unmodified.

## Required tests (TDD)

- Conformance: an importer missing a contract member fails `test_domain_conformance.py`.
- Generic routes: preview/commit round-trips through `/api/import/{importer}/...` for both book
  importers, replaying the committed reader fixtures.
- Validation: a normalized record carrying a field the target domain does not declare is refused;
  entry values are checked against `entry_fields`.
- Manual add: a payload naming `album` validates against `ALBUM_FIELDS` and lands with
  `type="album"`; a payload naming no domain fails rather than silently defaulting.
- The existing import and undo suites, unmodified, as the no-behavior-change net.

## Verification

```bash
python scripts/validate_project.py
make format && make check && make test
git diff --check
```

Plus the walkthrough gate: run the app against realistic data, import from both book sources
through the generic routes, triage the `unsorted` results, undo one batch inside its window, and
record what was exercised and observed in the worklog. Add a manual album through `/add`.

## Explicit non-scope

- **A second importer.** `spotify → music` and `steam → games` are future epics (DEC-058); building
  one here would be the epic this sprint exists to make possible.
- **Entry depth.** DEC-077 settled it: flat entries, per-domain progress, provider `rows`. An
  importer creates exactly those.
- **Enrichment.** Domains declare `enriches=False` or own it; the import boundary does not redraw
  the provider one.

## Commit checkpoints

1. `feat(sprint-031): the Importer contract and conformance checks`
2. `feat(sprint-031): generic import routes and pipeline`
3. `feat(sprint-031): manual entry honours the domain`
4. `docs(sprint-031): importing and triage, in the README and the domain guide`
5. final `docs(sprint-031): close sprint and hand off` — with the project `complete` per
   `WORKFLOW.md`'s final-sprint rule.

## Risks and decisions to surface

- **The contract's shape is a real decision.** What an `Importer` must declare (reader, match
  strategy, identity kinds, target domain) decides how plug-and-play a future connector is. Surface
  the chosen shape in the sprint outcome; a contributor reads it before the guide.
- **Route compatibility.** If anything external scripts the per-source routes, removing them is a
  breaking change; the walkthrough establishes whether anything does.
- **The final-sprint rule.** Closing this sprint sets the project `complete` — no tag, push or
  deploy without the owner asking (WORKFLOW.md).

## Outcome

Completed 2026-08-21. The shared import layer now depends on an `Importer` protocol declaring
`name`, `label`, `item_type`, `input`, `identity_kinds`, `read`, `stage`, and `match`. Goodreads
and Calibre register through the book domain; one neutral service validates their normalized
metadata and entry values against the target domain and commits through a repository with no book
key list or default-domain binding. The generic routes are `/api/import/{importer}/preview` and
`/commit`, with `GET /api/importers` driving the UI. The existing source URLs remain those generic
URLs instantiated with `goodreads` and `calibre`, so compatibility was preserved.

Manual entry now requires `item_type`, renders the selected domain's declared fields, validates
them server-side, and creates the selected type; an album was exercised end to end. README and the
domain guide now explain importing, triage, resync semantics, and connector registration. DEC-078
records the boundary and payload decision. Commits: `5d908bb` (contract), `a6666c8` (pipeline),
`4877447` (manual entry), `aeb19f0` (documentation), and `a9f10f0` (isolated browser flows).

Verification evidence: validator, formatting, static checks, OpenAPI drift, and `git diff --check`
passed. Focused backend import/conformance/job coverage passed (97 tests), the manual-add
neighbourhood passed (43), frontend Import/Add component coverage passed (16), and the two changed
Playwright flows passed (12). The realistic-data walkthrough passed: both readers previewed and
committed through the generic routes, one batch was undone, the remainder was triaged until the
inbox was clear, and `/add` created an owned Album with album metadata. The isolated walkthrough
also surfaced an expected non-blocking Open Library `provider_unreachable` warning after Calibre
queued enrichment. The sprint named `test_undo.py`, but that file does not exist; the unchanged
undo regression coverage is distributed through `test_jobs.py` and `test_enrichment.py`, with
`test_jobs.py` included in the green focused run.

The final combined `make test` was **not completed**: its backend run collected 482 tests and was
interrupted while progressing through `test_export.py`; the frontend portion was not reached. The
owner explicitly waived that remaining slow run on 2026-08-21 and asked for close-out. This is a
verification deviation, not a claimed pass; all focused, static, browser, and walkthrough gates
above were green before closure. No future numbered sprint is affected: the plan ends here, and
the Games, Series, Spotify, and Steam work remains in unnumbered future epics on top of this
boundary. No tag, push, or deployment was performed.
