# Work log

Append-only, one entry per working session, newest at the bottom. This is the
agent's cross-session memory *within* a sprint: what was actually done, what was
verified and how, what diverged, and the exact next step. `HANDOFF.md` is the
current-state pointer; this file is the running history that keeps a later
session from re-deriving or silently redoing what an earlier one already learned.

Rules:

- Never edit or delete a prior entry. Correct the record by appending a new one.
- Terse and factual; this is for agents, not a narrative.
- Durable architecture decisions still go in `docs/decisions.md`; per-sprint
  delivered behavior still goes in the sprint `Outcome`. This file is the
  session-level layer between them.

Entry format:

```markdown
## YYYY-MM-DD — Sprint NNN (in progress | complete | blocked | interrupted)
- Done: steps completed; migrations/commits involved.
- Verified: each acceptance behavior touched and exactly how (command, browser
  session, migrated DB) — not "looks good".
- Deviations: anything that diverged from the docs and why; where it was recorded.
- Blocked/open: none, or what and why.
- Next: the very next concrete step for whoever picks this up.
```

---

## 2026-07-21 — Planning baseline (complete)
- Done: established canonical specs, roadmap revision 2, execution protocol, and
  machine-readable state. No application code yet.
- Verified: `python scripts/validate_project.py` passes.
- Deviations: none.
- Blocked/open: four product questions carry authorized defaults (DEC-006); the
  owner may override before the affected sprint activates.
- Next: claim Sprint 001 per `AGENTS.md` and build the reproducible foundation.

## 2026-07-21 — Sprint 001 (complete)
- Done: delivered backend migration/health/SQLite foundation (`29e2ad1`), frontend health view and unified contract/tooling (`e355640`), and CI/production container proof (`4ceebba`). Repaired the validator's generated-directory traversal and recorded the lock strategy in DEC-014.
- Verified: 7 backend tests and 2 frontend component tests pass; required bootstrap/format/check/test/build commands pass; Compose config renders; scripted Docker recreation proves ready health, SPA routing, persisted probe, non-root UID, and no Node; `git diff --check` passes.
- Deviations: no product or sprint scope deviation. The container uses a non-editable uv environment created at `/opt/venv` because copied editable/relocated environments failed the smoke proof.
- Blocked/open: none.
- Next: claim Sprint 002 and implement the complete domain migration and repositories in acceptance order.

## 2026-07-22 — Sprint 002 (complete)
- Done: delivered the complete domain migration (`d45f365`), normalization and matching contracts
  (`19ea28d`), and transactional mapped repositories (`ca21ca6`). Expanded Sprint 003 from the
  roadmap using the implemented paths.
- Verified: 25 backend and 2 frontend tests pass; real file-backed migration empty/previous-head
  round trips and a focused two-thread ISBN-equivalence race pass. `make format`, `make check`,
  `make test`, `make build`, project validation, and `git diff --check` pass.
- Deviations: none.
- Blocked/open: none.
- Next: claim Sprint 003 and add application/API contracts in acceptance order, beginning with
  failing entry and shelf mutation tests.

## 2026-07-22 — Sprint 003 (complete)
- Done: delivered typed library CRUD, normalized filter/facet/list queries, all-sort opaque keyset
  pagination, atomic bulk/suggested mutations, list indexes, and generated OpenAPI (`7c8435b`);
  fixed deterministic generated-contract formatting (`26c5c4f`); expanded Sprint 004.
- Verified: 49 backend and 2 frontend tests pass; focused ASGI tests cover CRUD/domain errors,
  static route precedence, bulk rollback, all six asc/desc sorts, duplicate/null/deleted cursor
  cases, normalized search, and query-plan index use. Required format/check/test/build/project
  validation and `git diff --check` pass.
- Deviations: deterministic connection-level SQLite normalization replaces the vague stored
  normalization/collation wording; technical spec section 7.2 and DEC-015 record the contract.
- Blocked/open: none.
- Next: claim Sprint 004 and begin with failing typed library loading/empty/error/populated component
  tests before adding the application shell and virtualization.

## 2026-07-22 — Sprint 004 (complete)
- Done: delivered typed library states (`2c38bec`), cursor-aware server controls and fixed-size
  virtual grid/table views (`01d0cdf`), optimistic edits/keyboard behavior (`fc44dff`), and isolated
  browser artifacts (`01e031e`), and guarded focus restoration (`22eb2ec`); expanded Sprint 005
  against current paths.
- Verified: 49 backend and 9 frontend tests pass; two Chromium checks prove keyboard guards,
  reduced motion, and fewer than 20 mounted entries in a deterministic 5,000-entry library.
  Required format/check/test/build/project-validation and `git diff --check` commands pass.
- Deviations: no product/scope deviation. Grid cards use fixed-height virtual rows rather than
  masonry; the `/add` route is a non-functional scope-boundary notice until Sprint 006.
- Blocked/open: none. The sandboxed isolated Python build could not resolve hatchling; the required
  approved `make build` rerun with network access passed.
- Next: claim Sprint 005 and begin with failing provider model/merge plus independent partial-failure
  search tests before implementing HTTP adapters.

## 2026-07-22 — Sprint 005 (complete)
- Done: delivered provider/search/resolve contracts (`61c8371`) and bounded cached add/cover
  orchestration (`24106d9`); regenerated OpenAPI and expanded Sprint 006 against the real boundary.
- Verified: 73 backend and 9 frontend tests pass. Focused mocked tests cover timeout/partial/429/
  malformed/oversized provider behavior, work-edition and URL/ISBN resolution, double submit,
  identity validation/conflict, write-lock timing, and cover byte/type/pixel/install/failure paths.
  Required format/check/test/build/project-validation and `git diff --check` commands pass.
- Deviations: no product deviation; consolidated implementation checkpoints into two green commits.
  The isolated build's sandbox DNS failed to fetch Hatchling; the approved network rerun passed.
- Blocked/open: none.
- Next: claim Sprint 006 and begin with failing typed add-page tests for provider, resolution,
  manual, exact-duplicate, and advisory near-match states.

## 2026-07-22 — Sprint 006 (complete)
- Done: delivered provider/manual/work-edition add (`513fd61`), cached detail and metadata editing
  (`465ea20`), cover replacement/confirmed refresh (`fc36831`), browser and near-match coverage
  (`b3a25b1`), and predictable focus transitions (`2aa8da2`); expanded Sprint 007.
- Verified: 76 backend and 13 frontend tests pass; five Chromium flows cover manual/work-edition add,
  exact duplicate, cached detail/edit, refresh/cover failures, mobile/reduced-motion/keyboard behavior,
  and the 5,000-entry regression. Required validation/format/check/test/build/diff checks pass.
- Deviations: no product or scope deviation; one corrective focus commit supplemented the planned
  checkpoints. Added `python-multipart` for the bounded multipart cover contract.
- Blocked/open: none.
- Next: claim Sprint 007 and begin with failing migration/parser fixtures for durable Goodreads
  preview records and armored/empty ISBN, malformed-date, UTF-8, and missing-column behavior.

## 2026-07-22 — Sprint 007 (complete)
- Done: delivered bounded Goodreads parsing and durable exact-plan preview/commit (`9216f27`), typed
  keyboard/mobile import UI (`4110481`), and safe retry/fill-empty/manual-preservation coverage
  (`0682b79`); expanded Sprint 008 against the shared import boundary.
- Verified: 82 backend and 15 component tests pass. File-backed migrated SQLite tests cover parser
  edge cases, preview isolation, atomic/idempotent commit, ambiguity, ordered effects, fill-empty,
  and manual preservation. Eight Chromium flows pass, including valid import, malformed/oversized
  recovery, ambiguity, keyboard focus, and mobile layout. Required format/check/test/build/project
  validation and `git diff --check` pass.
- Deviations: no product/scope deviation. Sprint 002 already created the audit tables, so Sprint 007
  added planning/effect indexes and the operational repositories rather than duplicate schema.
- Blocked/open: none.
- Next: claim Sprint 008 and begin with synthetic Calibre schema fixtures plus confined read-only and
  `query_only` adapter tests with source hash proof.

## 2026-07-22 — Sprint 008 (complete)
- Done: inserted the metadata sprint before Calibre; delivered normalized edition/work/author and
  optional same-ISBN provider merging, typed editable metadata, publisher migration, secure cached
  cover fallbacks/serving, metadata-rich search/library/detail UI, and live smoke automation in
  `62861fa`, `85bcc86`, and `2e9ff12`.
- Verified: 85 backend and 15 component tests pass; eight normal Chromium flows pass (two live tests
  skip by default). Explicit live add/offline runs selected Cien años de soledad (2012), Harry Potter
  (2015), and La sombra del viento (2005), cached every cover, restarted with provider proxies
  disabled, and rendered every detail. Validation, format/check/test/build and diff checks pass; the
  sandboxed build DNS failure passed on the approved network rerun.
- Deviations: official cover redirects required narrow `archive.org`/`*.us.archive.org` allowlisting;
  missing nested search data requires one bounded leading-work editions lookup. DEC-016 records the
  sprint insertion; Sprint 008 Outcome records live-discovered behavior.
- Blocked/open: none.
- Next: claim Sprint 009 and begin with synthetic Calibre read-only/query-only/path-confinement tests.

## 2026-07-22 — Sprint 009 (complete)
- Done: specified the editorial UI completion Sprint 010 before implementation (`79f1fdc`), then
  delivered confined read-only Calibre preview/commit (`0b7896b`), its typed keyboard/mobile UI
  (`73ee89d`), synchronized contracts (`4c88c91`), and UUID provenance on ISBN matches (`b3c89a4`).
- Verified: 91 backend and 16 component tests pass; nine normal Chromium flows pass and two opt-in
  live-provider flows skip without credentials. Source hash/read-only/query-only, staged-cover
  stability, safe paths, optional schemas, fill-empty re-sync, and Goodreads regressions are covered.
  Project validation, format/check/test, build, and diff checks pass; build needed the approved network
  rerun to resolve cached-missing Hatchling.
- Deviations: no product/scope deviation; the first two backend checkpoints were one coherent commit.
- Blocked/open: none.
- Next: claim Sprint 010 and start with its visual inventory plus shell/navigation tests, then deliver
  clickable detail, deletion, shelf management, and the specified editorial redesign.

## 2026-07-22 — Sprint 010 (complete)
- Done: delivered the editorial UI redesign in four implementation commits (`6159b30`, `7256117`,
  `d8da7c7`, `2ff1c04`) plus this closure. AppShell with desktop/mobile nav, 404, ErrorBoundary;
  virtual library rows navigate to detail by pointer/Enter with inline controls independent; URL-backed
  filters reload-stable; segmented ScorePicker 1-10 in add/detail/library; CoverImage with skeleton;
  DetailPage redesign with personal-reading and edition-facts regions; confirmed entry deletion with
  DELETE API, cache invalidation, and toast; ShelvesPage with create/rename/delete and entry_count;
  backend ShelfResponse extended with entry_count; stale-search cancellation in AddPage; new entries
  return to `/` with highlight, exact duplicates open detail with toast.
- Verified: `make test` -- 92 backend + 37 frontend component tests pass. `npx playwright test
  --project=chromium` -- 19 e2e pass (2 skipped non-chromium). `make check` -- format, lint, typecheck,
  OpenAPI check, project validation pass. `make build` -- Vite production build succeeds. `git diff
  --check` -- clean.
- Deviations: exact-duplicate e2e toast assertion changed from sessionStorage to visible role=status
  (DetailPage consumes toast on mount). Shelf rename e2e simplified to create+delete (rename covered
  by component tests). Manual-add e2e navigates to `/` then detail for metadata edit verification.
  All deviations are test-only; no product behavior changed.
- Blocked/open: none.
- Next: claim Sprint 011 (durable jobs, enrichment, safe undo) and expand its sprint file from
  TEMPLATE.md.

## Session 2026-07-22 — Sprint 011 (durable-enrichment-undo)

**Done:**
- Implemented durable job runner (`infrastructure/jobs.py`): enqueue, claim with polling,
  complete, fail with retry caps and exponential backoff, cancel, cancel_batch_jobs,
  reclaim_expired.
- Implemented clock-injected rate limiting (`RateLimiter`) for provider calls.
- Implemented enrichment handler (`application/enrichment.py`) that fills only empty
  item fields from providers, records import effects for undo coverage, and skips
  undone batches (late-job guard).
- Implemented safe undo (`application/undo.py`) with 24-hour window, field-matching
  semantics, shared-item/pre-existing-entry preservation, partial retention reporting,
  and repeated undo harmlessness.
- Added API endpoints: `GET /api/import/jobs/{id}` for progress, `DELETE /api/import/batches/{id}` for undo.
- Added undo UI with confirmation step and result display.
- Added e2e tests for undo flow and expired-undo error.
- Set `undo_expires_at` to 24h after commit in `repositories.py`.
- Added `fetch_by_isbn` to OpenLibraryProvider and GoogleBooksProvider.

**Verified:**
- `backend/tests/test_jobs.py`: 30 tests, all pass.
- `make test` (backend + frontend): 122 + 37 = 159 passed.
- `npx playwright test`: 21 passed, 2 skipped (pre-existing).
- `make check`, `make build`, `git diff --check`: all pass.

**Deviations:**
- Sprint checkpoint commits 2 and 3 were combined into checkpoint 1 due to tight coupling.
- Job runner shares FastAPI event loop (no separate process); recorded as DEC-018.
- Undo field-matching semantics recorded as DEC-019.

**Next:** Sprint 012 (bulk-first triage) — sprint file does not yet exist; needs to be
expanded from the roadmap before implementation can begin.

## Session 2026-07-22 — Sprint 012 (bulk-first-triage)

**Done:**
- Built triage page (`frontend/src/pages/TriagePage.tsx`): virtualized dense
  table with @tanstack/react-virtual, 56px rows, checkbox selection, shift-range
  selection, Ctrl/Cmd+A select-all-matching with exclusions, bulk action bar
  (status, score, clear provisional), accept-suggested button.
- Keyboard shortcuts: j/k + ArrowUp/Down navigation, status hotkeys
  (r/t/w/d/g/u), score 1-9/0, Enter (open detail or advance), Escape (clear
  selection). All guarded by isEditableTarget except Ctrl/Cmd+A which is
  allowed from any target.
- Frontend API: `bulkUpdateEntries` and `acceptSuggestedStatuses` in
  `frontend/src/api/library.ts`.
- Added /triage route and Triage nav item with icon in AppShell.
- HomePage Inbox button now navigates to /triage instead of toggling filter.
- 6 e2e tests in `frontend/e2e/triage.spec.ts` covering all 4 ACs.
- Updated editorial e2e tests for new inbox navigation and 5-item nav.
- Fixed focus management bug: useEffect was bailing because document.activeElement
  was still the old row when focusedId changed via keyboard. Fixed by checking
  if active element IS the target row or inside it before bailing.

**Verified:**
- `make check` → passed (tsc, eslint, prettier, ruff, mypy, OpenAPI types, validate_project)
- `make test` → 37/37 frontend unit tests, 122/122 backend tests
- `npx playwright test` → 27 passed, 2 skipped (pre-existing), 0 failed
- `make build` → 342 KB JS (104 KB gzip), 17 KB CSS

**Deviations:**
- Backend bulk API already existed from Sprint 010 — no backend changes needed.
- Planned commit checkpoints consolidated into one commit (7b431aa).
- HomePage Inbox button behavior changed (DEC-021).

**Next:** Sprint 013 (scale-accessibility-resilience) — status `ready`, sprint
file created at `docs/sprints/013-scale-accessibility-resilience.md`.

## Session 2026-07-23 — Roadmap revision 5 (planning only)

**Done:**
- Diagnosed the reported library grid overlap from the actual `VirtualLibrary`, `CoverImage`, and
  `ScorePicker` implementation. The two-column article has three layout responsibilities; cover and
  metadata compete inside a 128px cell, controls cannot wrap, expanded score editing exceeds 320px,
  and fixed 310px virtual rows cannot absorb overflow.
- Inserted a focused, ready Sprint 013 with TDD spatial assertions and required Chromium checks at
  375px, 768px, and 1440px. Renumbered hardening/release to Sprints 014/015 and synchronized state,
  roadmap, workflow, decision log, completed-sprint forward references, and handoff (DEC-022).
- No application implementation was changed, as requested.

**Verified:**
- Initial `python scripts/validate_project.py` passed before edits.
- A local Vite server started for diagnostic inspection; the headless probe yielded no captured
  measurements, so the recorded diagnosis relies on direct DOM/CSS contract inspection and must be
  encoded as the sprint's initial failing Playwright test.

**Next:** Execute Sprint 013, beginning with the specified failing overlap regression; do not begin
Sprint 014 hardening until the grid repair is verified and closed.

## Session 2026-07-23 — Sprint 013 (library-grid-layout-repair)

**Done:**
- Reproduced the reported overlap with bounding-box Playwright assertions before touching the
  implementation. Recorded failures: grid cover width 32px (expected >= 48) at all three widths, the
  expanded score panel at 375px measuring `x=286 w=338` against a card at `x=20 w=335`, and grid mode
  reporting 1 column at 1440px.
- Rewrote grid mode as a virtualized multi-column card grid. `gridColumnCount` in
  `frontend/src/features/library/library.ts` derives the column count from the measured scroll
  container; `VirtualLibrary` virtualizes rows of `columns` fixed-height 280px cards inside a 300px
  band and uses `ResizeObserver` plus `scrollToIndex(floor(index / columns))`.
- Made the compact `ScorePicker` expand into an overlay anchored above its trigger (two rows of five)
  so expanded editing cannot alter or escape the card box.
- Added non-behavioral `data-card-cover` / `data-card-meta` / `data-card-controls` /
  `data-score-panel` hooks so spatial assertions address layout regions directly.
- Recorded DEC-023 and added the grid-virtualization/card-box contract to technical spec section 8.

**Verified:**
- `python scripts/validate_project.py`, `make format`, `make check` — all passed.
- `make test` — backend 122 passed, frontend 38 passed.
- `npx playwright test --project=chromium e2e/library.spec.ts` — 8 passed; full Chromium suite
  33 passed / 2 pre-existing skips / 0 failed.
- `make build` — frontend 343.79 kB JS (105.40 kB gzip), 19.21 kB CSS. `git diff --check` clean.
- Chromium inspection with screenshots at 375/768/1440: 1/2/4 columns, 4/10/20 mounted cards,
  4/5/5 mounted virtual rows, 0px horizontal page overflow at every width. Table mode re-checked
  visually at 1440 and unchanged.

**Deviations:**
- The single mounted-DOM assertion became two bounds (rows `< 20` unchanged, cards `< 48`) because a
  grid row now mounts `columns` cards; grid overscan was reduced from 4 to 2 to keep the budget
  tight. Recorded as DEC-023 rather than silently relaxing the old number.
- A throwaway `e2e/grid-inspect.spec.ts` was used to capture the required screenshots and geometry,
  then deleted; it asserted nothing and did not belong in the suite. Re-create it if the inspection
  needs repeating.
- Commit messages in this repository carry no `Co-Authored-By` trailer, per owner instruction.

**Next:** Sprint 014 (scale-accessibility-resilience) — status `ready`. Benchmark against both
DEC-023 mounted-DOM bounds and keep the score-picker overlay when doing accessibility work.

## Session 2026-08-08 — Roadmap revision 6 (assessment and replan, planning only)

**Done:**
- Audited the project end to end after the owner reported the product as a candidate failure.
  Wrote `docs/assessment.md` with the evidence: three libraries required by technical-spec
  section 8 (shadcn/ui, Motion, React Hook Form + zod) were never installed, and four defects
  were confirmed against live systems and running code.
- Inserted three sprints and renumbered downstream work. New Sprint 014 (metadata correctness and
  search relevance, backend only, `ready`), Sprint 015 (design system and component foundation),
  Sprint 016 (motion and interaction polish). Hardening moved to 017 (file renamed via `git mv`,
  content preserved, baseline section marked for re-derivation), release to 018.
- Recorded DEC-024 (the replan), DEC-025 (walkthrough gate and E2E in CI), DEC-026 (amber design
  direction, component library adoption, and the two deliberately bespoke components).
- Added the walkthrough gate to `AGENTS.md` section 3 and a `playwright` job to
  `.github/workflows/ci.yml`. The Chromium suite had never run in CI.
- Patched `docs/specs/technical-spec.md`: section 6.2 records the `/isbn/` plus redirect contract,
  the Google Books enrichment fallback, relevance preservation, and that mocking the unit under
  test is not proof of it; section 8 pins the concrete token set and the bespoke-component
  exceptions and forbids feedback rendered only into a hidden element; section 10 records the
  walkthrough gate and CI E2E.
- Corrected stale hardcodes that predate this session: `scripts/validate_project.py` bounded the
  complete-project check at `range(1, 13)` while the plan had already reached 015; `AGENTS.md`
  and `docs/agent/WORKFLOW.md` both hardcoded Sprint 015 as final. All now reference 018.

**Verified:**
- `python scripts/validate_project.py` — passed with the new numbering.
- `make check` — passed (ruff format/lint, prettier, eslint zero-warning, mypy, tsc, OpenAPI
  export and type check, validator).
- `make test` — backend 122 passed, frontend 38 passed. Unchanged; this session touched no source.
- `git diff --check` clean. `docs/sprints/` holds exactly one file per number 001–017 with no
  duplicate prefixes, and exactly one file reads `**Status:** ready` (014).
- `grep -rn "014-scale" --include=*.md .` returns nothing; every markdown link resolves.

**Deviations:**
- Sprint 018 remains roadmap-only per `ROADMAP.md` line 51 — the closing agent of 017 expands it.
  Sprints 015 and 016 were written as full files now rather than left as roadmap contracts, so the
  owner has an executable path without a planning session between each sprint.
- Sprint 014 includes one small frontend change (sourcing the shelf filter from
  `GET /api/shelves`) despite being described as backend-only. It is a data-correctness defect,
  not presentation, and fixing it in 015 would mix it with a full rewrite.
- No implementation was performed. This session changed documentation, state, protocol, and CI
  configuration only, matching how DEC-022 handled the Sprint 013 insertion.

**Next:** Sprint 014 (metadata correctness and search relevance) — status `ready`. It is blocked
on the owner supplying `GOOGLE_BOOKS_API_KEY` in `.env` before its walkthrough can be completed;
the code and tests can proceed without it. Start by writing the recorded-response test for
`OpenLibraryProvider.fetch_by_isbn` and observing it fail against the current `/books/{isbn}`
implementation.

## Session 2026-08-09 — Sprint 014 (metadata correctness and search relevance)

**Done:**
- All seven acceptance criteria, in the planned checkpoint order. Commits `97a7fd1`, `706a1aa`,
  `3437647`, `91118c5`, `31c5b8e`, `394926b`, `4f838df`, `4e3d825`, `bbf2371`, `4dcd8c2`.
- **Found a defect larger than the one the sprint was written around.** Nothing in production
  code ever called `JobRepository.enqueue`, and nothing ever called `JobRunner.tick`. The
  enrichment queue had no producer and no consumer, so the broken `/books/{isbn}` URL was never
  even reached. Repaired as prerequisite work: importers enqueue on commit, the lifespan drives
  the runner, enrichment installs covers. Recorded as DEC-027.
- Committed real recorded provider responses under `backend/tests/fixtures/providers/` with a
  README documenting provenance and forbidding silent re-recording. Deleted the five `AsyncMock`
  substitutions of `fetch_by_isbn` in `test_jobs.py` and replaced the behaviors they covered with
  tests driving real providers over those recordings.

**Verified:**
- `python scripts/validate_project.py`, `make format`, `make check`, `make build`, and
  `git diff --check` all clean. `make test`: backend 154, frontend 39.
  `npm run test:e2e -- --project=chromium`: 33 passed, 2 skipped (the live-provider specs).
- **Walkthrough**, against a copy of the real `data/` directory with the owner's key, backend on
  port 8100, UI driven through Playwright at 4173:
  - `/api/health/providers` → both available with the key; `degraded: true` with reason
    `GOOGLE_BOOKS_API_KEY is not set` when removed. Readiness stayed 200 in both cases.
  - Live search `Rayuela Cortázar`: intended edition ranked **first** (`OL47684105M`), cover and
    year present, providers interleaved. Before the fix the same query put "Claves de una
    novelística existencial" first. `Don Quijote de la Mancha`, `Cien años de soledad`,
    `El túnel Sabato`, `Los detectives salvajes Bolaño` each ranked the intended title first.
    **20/20 results carried an edition year in every query.** Latency: 1.24 s and 1.28 s and
    1.32 s where no year resolution was needed, 2.62 s and 3.63 s where several works had to be
    resolved — roughly +1.3 to +2.4 s, one extra bounded round trip to Open Library.
  - Added `100 años de soledad`, `Harry Potter y la piedra filosofal`, `La sombra del viento`
    through the UI. Each reached its detail page with real metadata and a cover on local disk
    (`covers/6.jpg` 1.6 KB, `covers/7.jpg` 33 KB). The first resolved to an existing item, took
    the duplicate path, and filled that item's previously empty cover and description.
  - Calibre import of a synthetic 4-book library whose rows carried an ISBN and nothing else —
    no pubdate, no comments, no cover file. Commit created 4 items and 4 unsorted entries and
    queued exactly 4 jobs. All drained in **~3 s**; every row acquired year, publisher,
    description, language, page count, and a cached cover. `entries` unchanged.
  - `POST /api/enrichment/backfill` over the pre-existing library queued 5, drained in ~3 s,
    filled a cover and metadata empty since Sprint 011. `entries` dumped before and after was
    byte-identical.
  - Offline: restarted with `HTTPS_PROXY=http://127.0.0.1:1` so both providers were genuinely
    unreachable. All 7 detail pages and the library rendered from cache; `grep` of the log counted
    **0 outbound provider calls** during the browse. Search returned a typed
    `providers_unavailable` 503, and readiness stayed 200.
  - Shelf filter: created two shelves with zero entries; the `/` filter listed both,
    alphabetically. Under the old code it would have been empty. Checked with a throwaway
    `e2e/tmp-shelf-check.spec.ts`, then deleted — it asserted nothing worth keeping now that
    `HomePage.test.tsx` covers the case.

**Two defects were found by running the application, not by tests:**
- A four-row import queued **seven** enrichment jobs and attributed all seven to that batch,
  because the commit-time enqueue reused the library-wide backfill scan. Its progress display
  would have reported work the import never caused. Fixed in `4dcd8c2` with a scoped scan plus a
  regression test.
- `live-metadata.spec.ts`, the walkthrough vehicle, asserted that adding a book navigates to the
  detail page. Product spec section 7 says a new entry returns to `/` highlighted; only an exact
  duplicate goes to detail. The spec had never run — it is gated behind an env var nobody set.

**Observed, out of scope, left alone:**
- `100 años de Soledad` (ISBN 9781516909629) still has no cover. Open Library returns an edition,
  but every cover URL for it 404s, and Google Books is not consulted because the edition data is
  otherwise usable. Enrichment falls back on a *miss*, not to complete individual empty fields.
  Worth deciding whether per-field completion across providers is wanted.
- `/api/shelves` was requested 7 times during one short browse; each navigation refetches it. A
  `staleTime` belongs in Sprint 015 when that component is rebuilt.
- Entries added through the UI carry no score, and the detail page shows an unset score control.
  Correct, but it reads oddly beside imported rows that have one.

**Deviations:** see the sprint Outcome. Principally DEC-027 (prerequisite pipeline repair), two
new endpoints, a product-spec 4.3 ranking reconciliation, and a validator exemption for recorded
fixtures.

**Next:** Sprint 015 (design system and component foundation) — status `ready`. It installs
shadcn/ui, real tokens, and visible feedback. Note that it will break `selectOption()` and
`input[type="checkbox"]` selectors across three e2e specs by construction; that is its scope, not
a regression. The degraded-search indicator it renders is already fed by
`GET /api/health/providers`.

## 2026-08-11 — Sprint 015 (complete)

**Done:** Installed the component library, form stack, and tokens that technical-spec section 8
has required since Sprint 004 and that DEC-024 found were never installed. Eight commits,
`0192b52`..`dad0b5a`; full inventory and per-criterion evidence in the sprint Outcome.

**Verified and how:**
- `python scripts/validate_project.py`, `make format`, `make check` (ruff, mypy 33 files, tsc,
  openapi, validator), `make test` = backend **154** / frontend **51**, `make build`,
  `git diff --check` clean.
- Chromium e2e **44 passed / 2 skipped**, run three consecutive times clean. The two skips are
  `live-metadata.spec.ts` behind `LIVE_METADATA_MODE`.
- Walkthrough against a real backend on `:8100` with the owner's Google Books key, a fresh
  database, and a 30-book Goodreads CSV. 42 screenshots at 375/768/1440. Zero uncaught page
  errors. Enrichment ran live and real covers appeared mid-session. The degraded-search notice was
  verified against a genuinely degraded backend by restarting without the key.
- DEC-023 bounds re-measured, not assumed: 7 rows / 28 cards against the 5,000-entry fixture
  (bounds 20 / 48); 4/2/1 columns with 5/5/4 rows and 20/10/4 cards against 30 real books. The
  spec now prints the measurement on every run.

**Dead ends and things a later session should not rediscover:**
- `npx shadcn add` wrote the components to a literal `frontend/@/` directory instead of resolving
  the alias, and pulled `next-themes` in for the Sonner wrapper. Both were corrected by hand.
- `buttonVariants` cannot be exported from `button.tsx`: `react-refresh/only-export-components`
  is a warning and lint runs `--max-warnings=0`. It lives in `button-variants.ts`.
- jsdom implements neither Pointer Capture nor `scrollIntoView`, so every Radix interaction test
  throws `hasPointerCapture is not a function` until the shims in `src/test/setup.ts` are present.
- Radix `AlertDialog` is `role="alertdialog"`, and `AlertDialogTitle` sets `aria-labelledby`,
  which overrides any `aria-label` on the content. Dialogs are addressed by visible title now.
- An intermittent e2e failure (a click landing on a row being replaced) was **not** a flaky test.
  Two real causes: the search-debounce effect wrote an unchanged query back to the URL on every
  page load, re-rendering the whole virtualized list a quarter second in; and Vite discovered the
  new dependencies during the first navigation and force-reloaded the page. Both fixed in source
  and `vite.config.ts`. Confirmed against the previous commit that the flake did not pre-exist.
- The dialog looked transparent in the first screenshots. That was the 200 ms enter animation, not
  a missing background. Screenshot dialogs after they settle.

**Observed, out of scope, left alone:**
- The edition-year line on a library card is `truncate`d inside a narrow metadata column, so
  `Edition year: 1994` shows as `Edition year: 199…`. A Sprint 014 correctness win clipped by
  Sprint 013 geometry; fixing it means changing the card, which DEC-023 pins. Recorded against
  Sprint 017.
- The triage score cell renders a provisional score as `6·` with no legend.
- The bundle is 610 kB of JavaScript and the build now warns about chunk size.
- Imported rows land `unsorted`, so the library reads as empty until triage runs. Correct, but it
  looks briefly like the import did nothing.
- Inline score and status edits deliberately produce no toast — they are optimistic writes that
  render instantly. Failures do toast.

**Deviations:** DEC-028 (one feedback surface; the `sr-only` announcement paragraphs are deleted
rather than retained, because Sonner's own region would announce every confirmation twice) and
DEC-029 (portalled primitives are safe inside a virtual row because Radix makes the document
inert; `isEditableTarget` widened from tag names to roles). Checkpoints 6 and 7 landed as one
commit because the e2e rewrite is not separable from the DOM change that forces it.

**Next:** Sprint 016 (motion and interaction polish) — status `ready`. `motion` is still imported
zero times. It starts from a token layer rather than a blank page, and must decide which Radix
enter/exit transitions to keep before adding its own. Re-assert both DEC-023 bounds with animation
enabled; current headroom is 7/20 rows and 28/48 cards.

## 2026-08-11 — Sprint 016 (complete)

**Done:** Motion is imported for the first time since it became a dependency in Sprint 004. Seven
commits, `6bb995c`..`f218578`; per-criterion evidence in the sprint Outcome.

**Verified and how:**
- `python scripts/validate_project.py`, `make format`, `make check`, `make test` = backend **154** /
  frontend **68**, `make build`, `git diff --check` clean.
- Chromium e2e **53 passed / 2 skipped** (the two skips are `live-metadata.spec.ts` behind
  `LIVE_METADATA_MODE`). Frontend unit 51 -> 68, e2e 44 -> 53.
- Walkthrough against a real backend on `:8100` with the owner's key, both providers available, and
  a **throwaway data directory** — the owner's `data/` was not touched. 30-row Goodreads CSV,
  Chromium at 375/768/1440, 25 screenshots, plus a full second pass under reduced motion.

**Measurements worth not re-deriving:**
- DEC-023 at rest against the 5,000-entry fixture: 7 rows / 28 cards (bounds 20 / 48). At the peak
  of a crossfade: 4 rows / 16 cards / exactly **1** container. Both printed on every e2e run.
- Real library: 1/2/4 columns at 375/768/1440, 4/5/5 rows, 4/10/20 cards.
- Score ramp measured in the browser: unscored `rgb(161,161,170)`, hover 2 `rgb(248,113,113)`,
  hover 9 `rgb(53,211,153)`. The trigger previews the band; the number keeps showing the committed
  value.
- Reduced motion: 522 animations observed across sorts, a commit and a search; **none** above 0.01s.
- Bundle **696.24 kB** JS / 219.66 kB gzip / 36.88 kB CSS. +86 kB on Sprint 015, roughly double
  Sprint 013. More than the contract's 30-45 kB estimate; flagged to Sprint 017.

**Dead ends and things a later session should not rediscover:**
- `m` is exported from `motion/react`, not from `motion/react-m`. The `react-m` subpath exports the
  tag components individually (`button`, `div`, …), so `import { m } from "motion/react-m"` yields
  `undefined` and fails at `m.button`.
- `m` and `useAnimationControls` work fine outside a `LazyMotion` provider: features are simply not
  loaded, so nothing animates. That is what lets component tests render in isolation.
- `tailwindcss-animate` **redefines the `duration-*` utilities to set `animation-duration`**, later
  in the cascade than the core transition-duration rule. A card carrying both `duration-500` for a
  transition and `animate-shake` ran the shake at 500ms. Use `[transition-duration:...]` when both
  live on one element. Found by an e2e assertion on the computed duration, not by looking.
- Motion's `useReducedMotion` is one-shot per component and reads a module global kept current only
  by a `change` event, so `setPrefersReducedMotion` must be called **before** `render` and must
  dispatch the event. With `matchMedia` absent entirely, Motion's fallback is "animations allowed".
- The non-compact `ScorePicker` replaces its trigger with the panel while open, so a test asserting
  the trigger recolours on hover must use `compact`.
- A raw `element.focus()` in a unit test is not act-wrapped, so React never flushes the resulting
  state before the assertion. Wrap it.
- `node_modules` was found materially incomplete at session start (`lucide-react`, `sonner`, `zod`
  and others absent) and `npm ci` was needed before anything typechecked. Not caused by any change
  in this sprint.
- The walkthrough's own scaffolding cost two false starts: the import page needs `Preview import`
  clicked before the commit button exists, and provider search takes ~5s, so a 4s wait reports zero
  results.

**Observed, out of scope, left alone:**
- Several walkthrough covers are wrong (a Mariana Enriquez title showing a Luisgé Martín cover).
  **This is the fixture, not the app**: the ISBN13s in that CSV were invented for the pass and
  resolve to real but unrelated editions. Do not chase it.
- A provider "image not available" placeholder JPEG is accepted and stored as a cover
  (`La invención de Morel`). It arrives as a successful response carrying a non-cover and nothing
  detects that. Added to the Sprint 017 roadmap entry as something to decide.
- The edition-year truncation and the triage `6·` cell are both still present, as recorded.
- Entries added through the UI still carry no score.

**Deviations:** DEC-030 through DEC-034. Two deliverables ship narrower than the contract's wording
and are named as such rather than quietly redefined: the cover treatment is a decode-reveal rather
than a blur-up (no server-side LQIP exists), and the add-flow selection is a carried-identity enter
rather than a shared-layout morph (projection is deliberately unavailable, and the source cover may
not have loaded). One prerequisite repair: the optimistic rollback restored its snapshot into the
query key on screen at failure time rather than the key it snapshotted.

**Next:** Sprint 017 (scale, accessibility, resilience) — status `ready`. It inherits a 696 kB
bundle and now owns that decision with a sharper number, a reusable animation sampler at
`frontend/e2e/motion.ts`, and a unit suite that already runs under reduced motion.

## 2026-08-12 — Sprint 017 (complete)

**Done:** all four acceptance criteria, nine implementation commits (`76253e8`..`b172366`) plus
closure. Owner decisions taken during planning: route-level code splitting over raising the chunk
limit, and axe gating in CI rather than local-only.

**Verified:** validator, `make format`, `make check`, `make test` (backend **164**, frontend
**74**), Chromium e2e **73 passed / 2 skipped**, `make build`, `git diff --check`. Plus a
walkthrough against a real backend on `:8100` with the owner's key, both providers available, and a
**throwaway data directory** — the owner's `data/` was not touched.

**Measurements worth not re-deriving:**
- Text sorting was over budget and is not any more. Contended p95 at 10,000 entries: `title` first
  page 312 → 82 ms, `sort_author` page 26 627 → 78 ms, text filter 988 → **10 ms**. Budget 500 ms.
  Rerun with `cd backend && uv run python ../scripts/benchmark_library.py`.
- The cause was call count, not the plan: `normalize_text` is a Python UDF invoked once per
  candidate row. **The projection is not index-backed and does not need to be** — the query drives
  from `entries` and reaches `items` by rowid, so SQLite builds a temp B-tree with or without the
  null-bucket CASE. Checked both ways with `EXPLAIN QUERY PLAN`; do not "fix" this by adding an
  index.
- Eager JavaScript 696.24 → **511.55 kB** across four chunks; largest chunk 193.67 kB; no warning.
- DEC-023 bounds at 10,000 entries: grid **7 rows / 28 cards**, table **15 / 15** (bounds 20 / 48).
  Unchanged from 5,000, as virtualization implies — which is why it was worth measuring.
- axe: twelve screens, **zero** serious/critical and zero moderate/minor.

**Walkthrough, 6-row Goodreads CSV with ISBNs verified against the live provider first:**
- Preview → commit → triage → "Accept all suggested" cleared the inbox in one action.
- Enrichment produced **5 real covers out of 5 resolvable books**; the sixth is a deliberately
  invented title with no ISBN and correctly shows the placeholder.
- Accent-insensitive search through the new projection, against real data: `paramo` and `PÁRAMO`
  both find *Pedro Páramo*; `cortazar` finds *Rayuela*; `bolano` finds *Los detectives salvajes*.
- Title sort orders *Ficciones, La invención de Morel, Los detectives salvajes, Pedro Páramo,
  Rayuela* — accents folded correctly.
- Keyboard: tab reaches the card `article`, then Open / Status / Score. Digit shortcuts score the
  focused row on both `/` and `/triage`.
- **Zero console errors across the whole walkthrough.**

**Dead ends and things a later session should not rediscover:**
- httpx normalizes a literal `/../secret.txt` to `/secret.txt` **before sending**, so a traversal
  test written that way asserts nothing about the server. Use percent-encoded forms
  (`/%2e%2e/…`, `/..%2f…`). Found by probe.
- `configure_logging` originally did `root.handlers = [handler]`, which removes pytest's `caplog`
  and broke an unrelated provider-health test. Replace only the handler you installed.
- Radix `Tabs` writes `aria-controls` on every trigger whether or not a `TabsContent` exists. The
  import page had none at all.
- A `role="feed"` locator does not survive a switch to compact view if the test grabbed
  `role="table"`; both densities are `role="feed"` now (DEC-038).
- `@axe-core/playwright` is a dev dependency and needs **no** `optimizeDeps` entry — that list is
  for runtime deps only.
- Asserting axe results as raw violation objects produces a several-thousand-line diff. Map them to
  one line each first.
- A route-failure test must stub the *module* request (`**/TriagePage.tsx*` in dev, the hashed
  chunk in a build), and must carry the `ALLOW_CONSOLE_ERRORS` annotation.
- "Fail only the first request" does not produce a visible error state: the URL-sync effect re-keys
  the query on mount, so the retry heals it before anything renders. Drive it with a flag.
- The score-picker options are named `Score N`, not `Set score N`; the add search input is
  `role="searchbox"`; the triage bulk controls are comboboxes, not buttons.

**Observed, out of scope, left alone:**
- **`s` is not implemented.** Product spec section 7 lists it as the triage shelf-autocomplete
  shortcut. `j`/`k`, the digits, the status letters, `Enter` and `Escape` all exist; `s` does
  nothing. Adding a shortcut is feature work, not hardening, so it was recorded rather than slipped
  in.
- Sorting by author sorts by the author string as providers give it — "Adolfo Bioy Casares" before
  "Jorge Luis Borges" — so it is a given-name sort despite the column being called `sort_author`.
  Correct against its own definition, probably not what the owner means by author order.
- Imports still land `unsorted`, so the library looks briefly as though the import did nothing.
  One click of "Accept all suggested" fixes it; the delay is the enrichment, not the import.

**Deviations:** DEC-036, DEC-037, DEC-038. Two prerequisite repairs (the root-handler wipe above,
and an error boundary that never reset so its fallback stayed pinned over every later route). Two
defects beyond the two the roadmap named were found in the walkthrough and fixed: the library score
control's unexplained provisional marker — the same defect as the triage cell, on a surface nobody
had listed — and a bare "unknown" where a year should be.

**Next:** Sprint 018 (container, backup, release) — status `ready`, file expanded at
`docs/sprints/018-container-backup-release.md`. It inherits two things from this sprint: migration
`0007` backfills every item row, making the "when do migrations run" question real; and the
frontend now emits several chunks instead of one.

## 2026-08-13 — Sprint 018: container, backup, and v1 release

**Done:** Compose gained the read-only Calibre mount that had sat commented out since Sprint 008
behind a note promising Sprint 008 would enable it, plus a `/backups` mount deliberately outside
the data volume; the LAN-only warning moved from a label to the top of the file. `book_tracker.backup`
provides online backup, verification, restore and label-scoped retention behind the `akasha-backup`
console script, with `scripts/backup.sh` as the host cron wrapper. Startup takes a backup before
applying pending migrations and refuses to migrate without one. `scripts/smoke_container.sh` was
rewritten to drive `docker compose` against the real API. Operator runbook, v1 release notes,
DEC-039/040/041, and README plus technical-spec section 11 brought in line. Sprint 019 expanded
from the roadmap contract, with its gate restated at the top.

**Verified and how:** validator, `make check`, `make test` backend **186** / frontend **74**,
Playwright **75 passed / 2 skipped** across both projects, `make build` with no chunk-size warning,
`make smoke-container` green end to end, `git diff --check` clean. Image 242 MB, user 10001:10001,
no Node, `STOPSIGNAL SIGTERM` with a graceful shutdown asserted from the logs rather than from the
exit code — compose runs the image under tini, which reports 143 for a perfectly clean stop.

The walkthrough ran against the **container**, not `make dev`, with throwaway `DATA_DIR` and
`BACKUP_DIR`. The owner's `data/` was not touched. Two real books added through the UI (ISBNs taken
from `/api/search` first, per the standing note), scored 8 and 9, a note each, one on a new shelf,
both with provider covers rendering. Backup taken from the running instance, the data directory
then **deleted outright**, restored into an empty one, stack restarted: both scores, both notes,
the shelf and both cover files came back, and `q=paramo` still matched `Pedro Páramo`. Separately,
a database seeded at `0006` with accented rows was started under the container: exactly one
pre-migration backup at revision `0006`, then head, then `Ávila, Ébano, Zurita` in the UI.

**Three defects found by the walkthrough that no test could have caught:**

- **The production bundle had been rendering a blank page since Sprint 017.** DEC-037's
  `manualChunks` object form names packages, which assigns only those exact entry modules and
  leaves `scheduler`, `jsx-runtime` and friends to fall wherever Rollup puts them; React ended up
  spread across chunks that imported each other and the entry threw before first render. Every gate
  was green because Playwright runs against the dev server, which does not chunk at all. Fixed by
  resolving each module to its package name with a fall-through vendor chunk — and the first
  attempt at that fix still missed `framer-motion`, a transitive dependency of `motion`, producing
  a different cycle. Guarded now by a second Playwright project that loads a real build (DEC-041).
- **The pre-migration backup ran once per restart.** `restart: unless-stopped` plus a migration
  that kept failing wrote ten copies of the same database in ninety seconds, and nightly retention
  deliberately never prunes pre-migration backups. Now taken once per revision.
- **`akasha-backup restore` needed `USER_AGENT_CONTACT`.** `book_tracker/__init__` imported `main`,
  which built the FastAPI app at import time, so restoring onto a bare machine died on a validation
  error about a metadata provider. The package init is now empty.

**Seen and left:** the crash-loop diagnosis was slow because a missing `chown 10001:10001` on the
data directory surfaces as `attempt to write a readonly database`, which reads like corruption and
is only permissions — that is now the first thing the runbook says. The Sprint 019 observations
appeared again: a provider "image not available" placeholder stored as a real cover, and search for
*Pedro Páramo* offering a 2024 reprint above the 1955 original. `s` on triage still does nothing,
and author sort is still a given-name sort. No v1 tag was created, per the owner.

**Deviations:** a sixth checkpoint was added for the pre-migration backup, which the owner chose
during planning and the sprint file's five did not cover. Documentation was written after the tests
rather than before, so the runbook could record what the drills actually did. The Calibre mount
took a `:-./calibre` default the sprint file omitted, without which Compose interpolation fails for
anyone with no Calibre library.

**Next:** Sprint 019 (metadata completeness) — status `ready`, file expanded at
`docs/sprints/019-metadata-completeness.md`. **It is gated:** DEC-035 approves an assessment, not
an implementation, and Phase A concluding the feature is not worth building is a legitimate
outcome. It is also the final planned sprint, so `WORKFLOW.md`'s final-sprint rule applies on close.

## 2026-08-13 — Roadmap re-plan, revision 8 (planning session, no sprint executed)

**Done:** Owner reviewed post-v1 options and asked for a sequenced roadmap. Plan extended from one
remaining sprint to eight, through Sprint 026. The metadata-completeness sprint was renumbered
019 → 020 and its file renamed (`git mv`), because `scripts/validate_project.py` requires
`active_sprint == len(completed_sprints) + 1` and permits exactly one non-completed sprint file, so
putting the polish work first forced the renumber. New `docs/sprints/019-post-v1-polish.md` written
from `TEMPLATE.md` and set `ready`. `ROADMAP.md` rewritten: duplicated contract blocks for sprints
002–018 deleted (each sprint file carries the same Deliverables and Acceptance criteria; no document
anchor-links into a roadmap section), OQ-001 deleted with its one live paragraph moved into the 020
file, contracts added for 021–026. 408 lines → 241 while covering eight more sprints. Final-sprint
bound moved 019 → 026 in `WORKFLOW.md`, `AGENTS.md`, and `validate_project.py`, where the literal
became a named `FINAL_SPRINT` constant. DEC-042 appended. Product spec §9 updated: export scheduled
as 023, second domain is albums (024) not wine. `HANDOFF.md` rewritten, including a cleanup pass
that flattened the "everything Sprint 015/016 recorded still holds" chain into one grouped gotcha
list with nothing dropped.

**Verified:** `python scripts/validate_project.py` passed after each edit batch, including after
the validator itself changed. `git diff --check` clean. Confirmed by inspection: exactly two
non-completed sprint files (019 `ready`, 020 `planned`), `ROADMAP.md` references
`019-post-v1-polish.md`, and the only surviving `019-metadata-completeness.md` reference is in this
worklog, which is append-only. No application code was touched, so `make check` / `make test` were
not run and are unaffected.

**Deviations:** two proposals raised during the session were dropped rather than planned. Renaming
the `book_tracker` package to match the Akasha brand was rejected on the existing `AGENTS.md`
invariant that internal names are permanent. Auth stays unscheduled at the owner's direction, still
a product spec §9 deferral. One item was promoted rather than deferred: the
`GoogleBooksProvider.fetch_by_isbn` first-hit bug is now recorded as a live v1 defect repaired
whatever Sprint 020's Phase A concludes, not only as a question the assessment asks. Sprint 018's
Outcome keeps its "Impact on Sprint 019" text with a bracketed pointer rather than being rewritten,
per the never-rewrite-history rule.

**Blocked/open:** none. Nothing is committed — the worktree carries the whole re-plan and the owner
was not asked for a commit.

**Next:** Sprint 019 (post-v1 polish) — status `ready`, file at
`docs/sprints/019-post-v1-polish.md`. Three small user-visible fixes; the walkthrough gate and the
`production-bundle` Playwright project both apply. Sprint 020 is the renumbered metadata sprint and
is still **gated**.

## 2026-08-13 — Sprint 019 (post-v1 polish and ledger clearing)

**Done:** The three defects that survived v1 are cleared. (1) The score chip: `scoreChipClass` in
`lib/score.ts` returns the existing `scoreFillClass`, and the picker trigger, the triage cell and the
detail fact all read from it, so a score is a filled ramp-coloured chip with the numeral knocked out
in `--background` on all three surfaces. The owner chose all-three over chip-on-card-only, reading
DEC-026's "the colour means the same thing wherever the eye lands" strictly. The provisional marker
had to change with it: dashed `border-primary/60` and a `bg-primary` dot are amber, and amber is the
4–6 band, so both vanished on the scores that most need them — both are now knock-outs, keeping the
accent only for an unscored provisional entry, where there is no fill to knock out of. (2) `s` on
triage: retired rather than built, at the owner's choice, with DEC-043 recording why and product spec
section 7 rewritten. (3) Post-import affordance: `unsorted_entries` on the commit response, and a
result panel that names the waiting count, says the library hides unsorted books, and links to
Triage. `v1.0.0` tagged, annotated and local, at `4ccf431`.

**Verified:** validator passed; `make check` passed; `make test` backend **187** / frontend **83**;
`npm run test:e2e` **75 passed / 2 skipped** across both projects; `make build` clean with no
chunk-size warning; `git diff --check` clean.

Walkthrough ran against a container mounted on a **copy** of the owner's library, never the real
one. Startup wrote a pre-migration backup before applying `0007` to the copy (DEC-039 working as
designed, since the repo's `data/books.db` had never been started since that migration landed), and
`docker stop` logged `Application shutdown complete`. A five-row Goodreads CSV with ratings
5/4/3/1/0 put one provisional chip in every band; all four knock-out markers are legible. The result
panel read *5 books are waiting in Triage*, the link landed on `Inbox 5 unsorted`, and
`Accept all suggested` cleared it. Geometry measured rather than assumed: picker trigger 36px, card
280px, every triage row 56px — unchanged, so the fill stayed a paint change (AC5). No console errors
in the whole run. Screenshots recaptured from that container.

**Seen and left:**

- **A provider description containing HTML renders as literal markup.** The detail page for
  *Escaping the Build Trap* shows `<p>To stay competitive…` with the tag visible, and *Cien años de
  soledad* has `<p> <b>`. Descriptions are escaped, so this is a display decision, not an injection
  risk. Not every book has it — *Shadow of the Wind*'s description is clean — so it depends on which
  provider answered. This is the first time it has been recorded; it belongs near Sprint 020's
  provider work.
- Publisher renders as `"O'Reilly Media, Inc."`, quotes included, from the provider payload.
- The *Add shelves* bulk action promised by product spec section 7 is still unbuilt and now has no
  sprint. DEC-043 names it deliberately.
- One walkthrough cover came out wrong (*La ciudad y los perros* got the *Cien años de soledad*
  cover). That is the documented gotcha rather than a defect: the ISBN came from my own test CSV
  instead of from `/api/search`, and unverified ISBNs resolve to real but unrelated editions. The
  entry was deleted from the throwaway copy before the screenshots were taken.
- Not re-observed this time, but neither was it looked for: the "image not available" placeholder
  cover and the *Pedro Páramo* reprint-over-original ranking, both Sprint 020's.

**Deviations:** the v1 tag was created, which the sprint file listed as a question rather than an
action — asked and answered yes. The commit response gained a field, so a sprint planned as
frontend-only moved an API contract and regenerated `frontend/openapi.json`.

**Next:** Sprint 020 (metadata completeness) — status `ready`, file at
`docs/sprints/020-metadata-completeness.md`. **It is gated:** Phase A measures whether
cross-provider field completion and edition choice are affordable, and concluding *no* is a complete
outcome. Do not start Phase B without an explicit owner go-ahead in `docs/decisions.md`. One item
does not wait on the gate: `GoogleBooksProvider.fetch_by_isbn` takes the first hit of an `isbn:`
search and is repaired whatever the verdict.

## 2026-08-13 — Sprint 020 (metadata completeness: viability, then build)

**Done:** Phase A ran and concluded; Phase B did not start, which is the gate working rather than
work left undone. The owner set that shape when planning: measure, repair the ungated defect, stop.

Two instruments produced the numbers. `scripts/benchmark_library.py` gained provider-request
counting — an Open Library hit costs **four** metadata requests plus a cover, not one — and needed
its own repair first: `query_plans` still emitted `normalize_text(...)`, removed as a
connection-level function by DEC-036, so every run of that script had died with `no such function`
since Sprint 017. `scripts/assess_provider_completeness.py` is new and asks both live providers
about a 60-ISBN sample harvested from real search.

The verdict is DEC-044 and it is mostly a decision **not** to build. Cross-provider field completion
buys a description in 22% of cases, a page count in 12%, and **0% for year, publisher, authors and
cover**, while a 5,000-book import would need ~15,000 Google requests against a ~1,000/day free
tier. The owner's headline want — choosing a cover from the editions fetched — gains **nothing**
from a second provider, because Open Library carried a cover for 100% of the editions it answered
for. But cover *choice* is still cheap from a source nobody had costed: the Open Library **work
record enrichment already fetches** lists 28 covers for Rayuela and 33 for *Cien años de soledad*,
so candidate discovery costs zero extra requests. That is offered as a Phase B and left unstarted.

The ungated defect is repaired. `GoogleBooksProvider.fetch_by_isbn` ran an `isbn:` search and took
the first hit; verification is now a tri-state and only a **confirmed** volume is merged.
Unverifiable is rejected exactly like contradicted, and the measurement is why: the observed failure
was not a wrong printing but a wrong *work* — for ISBN 9789583007828 Open Library returns *Crónica
de una muerte anunciada* and Google Books returns *Las venas abiertas de América Latina* — so
merging "only the work-level fields" would have kept the worst error. This discards 19.6% of Google
Books fallback answers, which is the stated price.

Two further fixes. The placeholder cover is *solved, not just described*: Google's "image not
available" is **575x92**, a 6.25:1 banner, where real covers measured 0.66 and 0.77, and
`prepare_cover` rejected only images under 10px, so it installed one as a real cover. And provider
HTML in descriptions is stripped at the boundary with migration `0008` backfilling what was already
stored.

**Verified:** validator passed; `make check` passed; `make test` backend **209** / frontend **83**;
`npm run test:e2e` **75 passed / 2 skipped** across both projects; `make build` clean with no
chunk-size warning; `make smoke-container` passed with its verified restore reporting revision
`0008_plain_text_descriptions`; `git diff --check` clean.

Walkthrough ran against a container on a **copy** of the library, never the real one. The copy sat
at `0006`, so startup wrote a pre-migration backup and applied both `0007` and `0008` unattended —
DEC-039 exercised for real. A three-row Goodreads import with ISBNs taken from `/api/search`
committed after resolving one genuine ambiguity (the library already held two *Cien años de
soledad*). Enrichment then showed both sides of the repair: `9788419233790` missed on Open Library
and was **confirmed** by the Google fallback, so it merged (RM Verlag, 136pp, 2024), while
`9788437604572` hit Open Library and got Cátedra and **746** pages — not the 762 the unverifiable
Google volume would have written. Every stored cover measured portrait, 0.59–0.67. Four detail pages
opened in a real browser: no literal `<p>` or `<b>` anywhere, no console errors. `docker stop`
logged `Application shutdown complete` and exited 143.

**Seen and left:**

- **Open Library returns mojibake for some titles** — `Cc3mo Leer a Garcc-A Mc!Rquez` for *Cómo leer
  a García Márquez*. Upstream data corruption this project cannot fix, but could detect.
- **Provider search silently degrades to one provider.** The client timeout is a hard 5 s while Open
  Library's search plus its year-resolution fan-out routinely exceeds it. In the walkthrough,
  `/api/search` for *Pedro Páramo* returned **Google Books results only**. The handoff's "provider
  search takes about five seconds" is this, and its real consequence is worse than slowness.
- **The reprint-over-original ranking is confirmed.** `merge_and_rank` puts a 1969 printing at rank
  0 and a 2024 edition at rank 1 for *Pedro Páramo*; the 1955 original is not in the top eight.
  Deliberately deferred in DEC-044 — it is search ranking, and changing it is product behaviour.
- **The quoted publisher is still there**: the detail page reads `"O'Reilly Media, Inc."`, quotes
  included, straight from the provider payload. Unowned.
- `POST /api/enrichment/backfill` exists but there is no `/api/jobs` listing endpoint, so job state
  during a walkthrough has to be read from the database.

**Deviations:** the repair landed *after* the verdict rather than before, because the owner chose to
let the measurement pick the policy. One fixture was **added** (the confirmed Google case) and none
re-recorded — the existing one already contained the defect. `ItemPayload` gained an `edition_match`
field, which Sprint 024 inherits. A prerequisite defect in the benchmark script was repaired.

**Next:** Sprint 021 (attachments) — status `ready`, file at `docs/sprints/021-attachments.md`,
expanded from `TEMPLATE.md` at this close. **It is gated** like 020: Phase A measures, and backup
growth is the measurement that scopes the whole feature. Concluding *no* is a complete outcome.

## 2026-08-13 — Sprint 020 Phase B (cover selector and provider quota)

**Done:** The owner read DEC-044 and gave the go-ahead DEC-035 required, so the sprint reopened for
its Phase B rather than being superseded by a new one — the decisions log is append-only and already
refers to Sprints 021, 024 and 026 by number, so renumbering would have falsified those references.
DEC-045 records that along with three decisions: the metadata merge is abandoned, the cover selector
is built, and provider order stays Open Library first.

The order question was the owner's and was measured rather than argued. Open Library first costs
**1,333** Google calls per 5,000 books; Google first costs **5,000**. Open Library is also verifiable
in 100% of its answers against Google Books' 80.4%, so correctness and quota agree. But 1,333 still
exceeds the ~1,000/day tier, which is why the guard shipped in the same sprint.

The guard is **provider-agnostic at the owner's explicit direction** — the roadmap adds MusicBrainz,
IGDB and TMDB, and a guard written around one provider becomes a patch at each new one. Nothing in
`ProviderQuota`, migration `0009` or the enrichment loop names a provider; limits are configuration,
and the tests are written against a fictional `pretendbooks` so they prove the mechanism rather than
re-asserting today's default. Exhaustion **defers** rather than fails, because `fail` increments
attempts and dead-letters at the ceiling, so a large import would otherwise destroy its own backlog.

The chooser rests on DEC-044's measurement: the work record enrichment already fetches lists the
sibling editions, so candidates cost no extra request to discover.

**Verified:** validator passed; `make check` passed; `make test` backend **235** / frontend **85**;
`npm run test:e2e` **77 passed / 2 skipped** across both projects; `make build` clean;
`make smoke-container` passed; `git diff --check` clean.

**Walkthrough — this is the part that mattered.** Container on a copy of the library, migrating
`0006` to `0009` unattended behind a pre-migration backup, graceful stop at 143. The feature worked
in the end — 14 candidates for *Shadow of the Wind*, a chosen cover installed and still there after
reload, no console errors — but only after **five repairs, every one of which passed the full test
suite first**:

1. The chooser failed outright: the shared client allows 5 s and Open Library answered one edition
   record in **11.3 s**.
2. "Not indexed" was reported as "could not be reached" — and my first fix then reported a real
   outage as "no candidates". One exception type carries both; only its code separates them. Open
   Library was genuinely 503-ing during the run, which is how the second direction surfaced.
3. Six of twenty tiles were blank and still clickable, because `resolve_work` invents an `/b/olid/`
   URL for an edition with no cover id. Choosing one answered 422.
4. A **60x40** image was installed as a cover. Provider downloads now require 200 px per side.
5. The screenshot gave away a fifth, which no assertion would have: the cover behind the dialog read
   *No image available*. **Open Library's placeholder is portrait and ordinarily sized**, so
   DEC-044's geometry rule — which catches Google's 6.25:1 banner — cannot see it. `default=false`
   is the only reliable guard and is now forced at the download boundary rather than trusted to the
   URL the client sent. This corrects DEC-044's answer on placeholder detection.

A sixth defect was found by testing one layer up rather than by the walkthrough: `JobRunner.tick`
routed every state that was not `succeeded` or `cancelled` to `fail`, so the new deferral was undone
above where its unit test was looking.

**Seen and left:**

- **Open Library's JSON API returns 503 under load**, repeatedly, for minutes at a time. Its website
  stays up. This makes the chooser and enrichment fail intermittently through no fault of ours, and
  nothing retries. Unowned, and now the most consequential provider observation.
- `search_providers` still degrades silently to a single provider on its 5 s timeout. This sprint
  worked around it for the chooser and did **not** fix it for search.
- Open Library title mojibake and the quoted publisher string are both unchanged.
- The reprint-over-original ranking is unchanged and still deferred by DEC-044.

**Deviations:** the sprint was reopened rather than superseded (DEC-045); one fixture was added and
none re-recorded; an existing test's arbitrary 40x60 stand-in image was resized to 400x600 because
the new minimum-size guard correctly rejects it.

**Next:** Sprint 021 (attachments) — status `ready`, file at `docs/sprints/021-attachments.md`. It is
gated like 020, and backup growth is the measurement that scopes the whole feature.

## 2026-08-14 — Sprint 021 (in progress — stopped at the Phase A gate)

**Done:** Phase A of the attachments gate. Built `scripts/assess_attachment_cost.py` plus 14 tests
in `backend/tests/test_attachment_cost.py`, ran the measurement, recorded the verdict as DEC-047,
and stopped for the owner's go-ahead. No product code changed; nothing user-visible shipped.

**The deliverable is a comparison table, not a verdict.** The owner directed during planning that
Phase A measure and report rather than pronounce — no disk budget is recorded anywhere in this repo
— and that the assessment cost alternatives (shallower retention, separate cadence, dedup,
exclusion) rather than the two options the sprint file named. Seven strategies were costed.

**Headline numbers**, 500 attachments at 2.5 MB, seven-night window, against today's 130.9 MB:
in-the-tar nightly **8.68 GB / 67.9x**; separate label keep-2 2.57 GB / 20.1x; weekly cadence
1.35 GB / 10.6x; loose deduplicated store 1.35 GB / 10.5x; excluded 130.9 MB / 1.0x. **Multipliers
are independent of corpus size** — identical at 100, 300 and 500 — so they are properties of the
strategy, not the sample.

**Two findings worth more than the table.** Measured gzip ratio on an epub corpus is **1.0003** —
the archive is *larger* than the raw bytes, because an epub is already a ZIP — and that useless
compression costs 20.4 s per backup against 2.0 s for a loose store, a 10x gap on hardware much
faster than the ZimaBoard. It is also exactly what makes deduplication impossible, since a tar
shares nothing with last night's tar.

**Method notes for whoever re-runs this.** `/tmp` here is tmpfs, so the run was pointed at
`/home/ibz/.cache/akasha-assess` via `TMPDIR`; running in RAM would have made every wall-time figure
fiction. The corpus is incompressible ZIP content on purpose, and disk accounting counts unique
inodes — both are pinned by tests, because getting either wrong silently flatters the result. The
real `create_backup`/`restore_backup` are called rather than reimplemented.

**Two defects found and deliberately left**, both Phase B's to fix and both in DEC-047:
`UndoService` deletes a batch-created item without regard for attachments it might carry, guarded
only by `modified_items`; and **no cover file is ever unlinked** when an item is deleted, which
product spec open question 2 accepts on the grounds that covers are ~50 KB — a premise a 2.5 MB
attachment invalidates.

**Also established:** `calibre_uuid` is already persisted as an item identifier and Calibre's
`books` table carries `uuid` and `path` in the same row, so the zero-copy Calibre reference needs
**no schema change**. And today's serving safety comes from the cover pipeline re-encoding
everything to JPEG, not from headers — the codebase sets no CSP, no `nosniff`, no
`Content-Disposition` anywhere — so an opaque blob endpoint would be the first user-controlled
content type to reach a browser, from the SPA's own origin.

**Verified:** validator passed; `make check` passed; `make test` backend **258** / frontend **85**;
`npm run test:e2e` **77 passed / 2 skipped** across both projects; `make build` clean with no
chunk-size warning; `make smoke-container` passed; `git diff --check` clean.

**Deviations:** seven strategies rather than two, and the Calibre reference assessed, both at the
owner's direction. Sprint left `in_progress` rather than closed, which is correct: DEC-035 requires
an explicit recorded go-ahead before Phase B, and it does not exist yet.

**Next:** the owner decides two things — whether to build attachments at all, and which strategy.
Recommended rows are E if attachments are stored (full fidelity, 10.5x, fastest backup of any
option) and F if 10.5x is unwelcome (1.0x, and an epub usually still exists wherever it came from,
which a score and a note never do). Record the answer in `docs/decisions.md`, then Phase B.

## 2026-08-14 — Sprint 021 (complete)

**Done:** Phase B. The owner read DEC-047 at the gate and asked whether strategy E meant "full
database backups, less intense file backups" — and, more usefully, pointed out that Phase A had
costed *backup* layouts while leaving the live store undesigned, asking for both to be designed
together and to be scalable. That is DEC-048 and it changed the shape of the build: the store is
**content-addressed**, not `{item_id}/{filename}`.

**Content addressing was the highest-leverage decision in the sprint.** `attachments/{sha256[:2]}/
{sha256}`, filename in the database. Identical bytes cost one blob; integrity is free; the backup's
hardlinking is correct by definition rather than by assumption; and **traversal stops being a filter
to get right** — no caller-supplied string reaches the filesystem at all. Marginal cost is 2x a
file's size, against 8x for the naive design.

**Shipped:** migration `0010_attachments` (head moves off `0009_provider_usage`; three literal pins
updated); `infrastructure/attachments.py`; four endpoints under `/api/items/{id}/attachments` with
`Content-Disposition: attachment`, `nosniff` and fixed `application/octet-stream`; refcounted
deletion; hardlinked backup blobs with digest+size in the manifest; the undo guard DEC-047 required;
a detail-page Files panel with its own query so it never blocks the page.

**The walkthrough found a defect no test could have, which is the whole reason the gate exists.**
The first implementation hardlinked out of the live store. Compose mounts `/data` and `/backups` as
**separate volumes**, so `os.link` fails `EXDEV` on every single run and it silently wrote a full
copy each night — 67.9x rather than the authorized 10.5x, with the entire suite green, because every
test runs inside one filesystem. Backups always share a filesystem with each other, so the fix links
from a sibling backup when the live store is unreachable, and copies only when neither works.
Measured in the container: two nightly backups of one 1.5 MB attachment went 4.0 MB → 2.6 MB. The
regression test monkeypatches `os.link` to fail exactly the way a volume boundary does, and was
confirmed to fail without the fix before it was kept.

**Walkthrough detail** (container, not `make dev`): real library at `0006` migrated to `0010`
unattended behind a pre-migration backup; upload → list → download byte-identical with all three
headers → delete; blob at `attachments/a1/a17e…`, gone with the last reference while both backups
kept it; two backups verified and restored; browser check showed the Files panel with names, sizes
and non-ASCII filenames intact and no console errors.

**Seen and left:**

- **Re-uploading identical bytes under a new name renames the existing row** rather than adding one.
  Deliberate — `(item_id, sha256)` is unique and last-write-wins on the name — but it is a silent
  mutation of a name the owner chose, and it surprised me during the walkthrough. Worth revisiting
  if it ever bites.
- **No cover file is unlinked when an item is deleted.** Unchanged and out of scope, but product
  spec open question 2 justified it with "covers are ~50KB each", so that question was updated
  rather than left implying attachments are cheap cache.
- The quoted publisher string (`"O'Reilly Media, Inc."`) is still visible on the detail page.
- The e2e download assertion checks the anchor's `href` and `download` attribute rather than driving
  a browser download; the forced-save contract is asserted against real headers in
  `test_attachments_api.py`, where it can be checked properly instead of inferred.

**Verified:** validator passed; `make check` passed; `make test` backend **293** / frontend **95**;
`npm run test:e2e` **79 passed / 2 skipped** across both projects; `make build` clean with no
chunk-size warning; `docker build` + `make smoke-container` passed; `git diff --check` clean.

**Deviations:** the live store design was not in the sprint file — it came from the owner's question
at the gate (DEC-048). Strategy G (Calibre reference) was assessed and deliberately not built. The
orphaned-cover defect was left; the undo defect was fixed.

**Next:** Sprint 022 (creator sort names) — status `ready`, file expanded at
`docs/sprints/022-creator-sort-names.md`. It replaces the `sort_author` generated column with a
stored, owner-correctable creator sort name, and the roadmap's warning stands: a last-space split
gets García Márquez and Vargas Llosa wrong while getting Rulfo right.

## 2026-08-14 — Post-021 review (no code changed)

**Done:** pushed Sprint 021 to `origin/main` (`743a509..7744302`), then reviewed the attachment
feature at the owner's request — does it cover delete/replace/rename, are the flows clean, is
anything leaking — explicitly without feature creep. **Assessment only; no product code was
touched.** Findings are DEC-049 and the work is scheduled as Sprint 022.

**Read out of the shipped code, not inferred:**

- `delete_blob_if_unreferenced` has **exactly one caller**. Three routes orphan a blob with nothing
  able to find it: `CASCADE` on item delete, a crash between `store_blob` and the row insert, and an
  item orphaned by entry deletion. The undo guard makes the first unreachable today — a guard, not a
  fix. **This is the only real hole.**
- No rename (the filename is already metadata, so it is one write) and no replace.
- Remove has no confirmation, while the product spec says deletes confirm and *Delete entry* on the
  same page does.
- `await file.read(cap + 1)` and `target.read_bytes()`: 25 MiB in memory per concurrent request.
  Not a leak, nothing accumulates, but sharp on a ZimaBoard where a cover is 39 KB.
- **No frontend leak.** No `createObjectURL` anywhere; query cache keyed per item; the file input is
  reset after each pick. Two warts: one pending flag disables every Remove button, and the `sr-only`
  input is a second tab stop with the same accessible name as its button.
- `Cache-Control: immutable` for a year with no validator against a **mutable** filename, so a
  re-upload under a new name leaves an already-downloaded file with its old one.

**Deviations:** scheduling Sprint 022 ahead of the plan forced the tail to renumber — creator sort
022→023, export 023→024, domains 024-026→025-027, `FINAL_SPRINT` 26→27 in the validator and
`WORKFLOW.md`. Same forced renumber as DEC-042 and for the same validator rule. Sprint 021's Outcome
was left as written, since a completed sprint's Outcome is audit history.

**Next:** Sprint 022 (attachment lifecycle) — `ready`. Reclamation is its dangerous deliverable: it
deletes data by inference, and must be reasoned about against an upload that has written its blob but
not yet committed its row.

## 2026-08-14 — Sprint 022 (attachment lifecycle), complete

**Done:** reclaim command, rename, remove confirmation, streaming, and the two UI corrections from
DEC-049. Commits `561d7d8` reclaim, `58c6956` rename, `bc24adf` confirm + UI, `84fd445` streaming,
plus this closure commit. Decisions in **DEC-050**.

**Asked before building, as the sprint required.** Both went to the owner at activation rather than
being settled quietly:

- **Replace: not built.** With rename in place it is remove plus attach, and building it would have
  added an endpoint, a second confirmation, and a question about what a row's identity means when
  its bytes change underneath.
- **Reclaim surface: CLI, dry-run by default**, over a UI button or an automatic sweep.

**The reclaim's two protections, and why the ordering one is real.** The sweep reads the filesystem
*before* the database. Reversed, a blob whose row was committed between the two reads is reported as
an orphan and deleted — a file the owner attached seconds earlier. I verified this is not a
theoretical concern by swapping the two lines and watching
`test_a_row_committed_during_the_walk_keeps_its_blob` fail, then swapping them back. The second
protection is a one-hour mtime grace period, which covers the upload still in flight during both
reads. Both are needed; neither is sufficient.

**The backup question was checked, not assumed.** Acceptance criterion 1 said to check what the
hardlink chain actually guarantees. It guarantees it: the backup holds its own directory entry
against the same inode, so unlinking the live path decrements a link count. Confirmed in the
container — reclaimed blob still byte-identical in the backup (`23b1873a…`), `akasha-backup verify`
still passed.

**Measured, not asserted** (criterion 5). Peak RSS of a real uvicorn process pushing 25 MiB, taken
before and after by running the same instrument against a temporary worktree at the pre-streaming
commit: upload **+29.9 → +2.6 MiB**, download **+24.9 → +0.0 MiB**.

**Seen and left:**

- **`entries.item_id` has no `ON DELETE CASCADE`.** Deleting an item raises `FOREIGN KEY constraint
  failed` while any entry references it, so producing the orphan for the walkthrough needed the
  entry deleted first. The sprint baseline described the `CASCADE` leak without this step. Recorded
  in DEC-050.
- **`HEAD` on any route is a 405.** Noticed because my first revalidation check used `curl -sI` and
  silently got an empty ETag, which made a working 304 look like a 200. The code was right and the
  check was wrong. Application-wide FastAPI behaviour, not attachment-specific, and not touched.
- **Row layout was ragged** — `justify-between` made the size and buttons track each filename's
  length, obvious once rows carried two buttons. Fixed in the file I was already changing.
- **The cover's "Replace cover" control is a raw unstyled `<input type=file>`** on the detail page,
  showing the browser's default "Choose File / No file chosen". Different component, out of scope,
  but it looks unfinished next to the Files panel.
- The quoted publisher string is still visible on the detail page (carried from Sprint 021).
- The orphaned **cover** file is still not collected. The reclaim is deliberately scoped to the
  attachment store; a cover is re-fetchable cache and does not deserve a second mechanism.

**Verified:** validator passed; `make check` passed; `make test` backend **328** / frontend **97**;
`npm run test:e2e` **79 passed / 2 skipped**; `docker build` + `make build` + `make smoke-container`
passed with no chunk-size warning; `git diff --check` clean. Full container walkthrough: attach,
rename ×2, download byte-identical with all three headers, 304/200 revalidation around a rename,
deliberate orphan + backdated `upload-crashed.tmp`, reclaim dry run then `--apply`, browser check of
inline rename, confirm dialog, cancel-is-a-no-op, one tab stop, confirmed removal, no console errors.

**Next:** Sprint 023 (creator sort names) — status `ready`. No migration was added here, so the head
is still `0010_attachments` and 023's baseline was updated to say so.

## 2026-08-14 — Sprint 023 (creator sort names), complete

**Done:** stored creator sort name with a heuristic seed and an owner override, migration
`0011_creator_sort_names`, ordering and cursors moved onto it, the "Sorts as" edit field, and the
Calibre `authors.sort` seed. Commits `2bc81f0`, `e5f15b4`, `aeec7c9`, `5780155`, plus this closure
commit. Decisions in **DEC-051**.

**Two owner decisions were taken at planning, before any code.** Calibre's curated `authors.sort`
seeds the value as owner data rather than as a guess; and `sort_author` keeps its name and its
display role, with the rename deferred to Sprint 025 where the `authors` → `creators` key change
happens in one pass. Both are recorded in the sprint file's own "Owner decisions" section.

**The three-name test would have passed against the defect.** García Márquez, Bioy Casares and
Rulfo sort the same way by given name as by surname — a, g, j against b, g, r — so a regression
test built only from the three names the roadmap listed proves nothing. Zoé Aguirre is in the test
for that reason: last by given name, first by surname. I noticed this only when the first version
of the test passed before the implementation existed.

**Measured rather than tuned.** On the walkthrough library the heuristic got **14 of 16** authored
items right. Both failures are one shape: two given names and no initial, so "Jorge Luis Borges"
becomes "Luis Borges, Jorge". That is exactly the class Calibre's curated column fixes, which is
why the seed matters more than a cleverer split would.

**Undo was pulled in, and it was not in the sprint file.** The import now fills
`creator_sort_override`, and `_set_item_field` silently ignores fields it does not recognise — an
undone import would have left the seeded name behind while *reporting* it as "retained", which is
the worst of both. Fixed with a test that also pins the retain half: a name corrected after the
import survives undo.

**Verified:** validator passed; `make check` passed; `make test` backend **350** / frontend **99**;
`npm run test:e2e` **79 passed / 2 skipped**; `make build` and `make smoke-container` passed;
`git diff --check` clean.

Container walkthrough against a copy of the real `data/`, which was still at revision `0006`, so it
migrated through `0011` for real and wrote a pre-migration backup on the way. Seeded 13 Spanish
titles to make the ordering legible, then: read the author-sorted grid in the browser (Allende,
Bioy Casares, Bolaño, Borges, Cortázar, Esquivel, García Márquez ×2, …); walked six cursor pages of
three with no skip, no repeat, nulls last; hand-built a `v: 1` cursor and got `400 invalid_cursor`;
ran a real Calibre preview-and-commit and saw `Borges, Jorge Luis` and `Vargas Llosa, Mario` land
as overrides; corrected a name in the dialog and watched the row move from eighth to fourth, then
cleared it and watched the order return exactly. Tab order goes Authors → Sorts as → Publisher, one
stop, no console errors. Benchmark re-run: `sort_author` page 26 contended **78.7 ms p95** against
DEC-036's 78 ms.

**Seen and left:**

- **Item 1 of the dev library has `OL14454691A` as its author** — an Open Library author key that
  reached `metadata.authors` as if it were a name, so it now sorts under O. Pre-existing and
  unrelated to this sprint, but visible in any author-sorted list and worth a look.
- The `statuses=` query parameter I reached for while walking through does not exist; the API takes
  repeated `status=`. My own error, but it cost a confusing few minutes where imported rows looked
  missing from the list when they were simply in the Inbox, which the default excludes.
- **`ROADMAP.md` claimed plan revision 8** while `state.json`, `WORKFLOW.md` and sprints 022–023 all
  said 9. Repaired as a documentation-only inconsistency; no re-plan happened here. The product
  spec also still said export was "Sprint 023 in roadmap revision 8"; corrected to 024/9.
- The unstyled "Replace cover" `<input type=file>`, the quoted publisher string, and the
  application-wide `HEAD` 405 are all still there, all carried from earlier sprints.

**Next:** Sprint 024 (export) — status `ready`, file written. Its one real decision is whether an
export carries attachment bytes, references, or neither; put it to the owner at activation.

## 2026-08-14 — Domain architecture planning (no code changed)
- Done: wrote `docs/domain-architecture-proposal.md` and recorded **DEC-052**, which the
  owner accepted in full. Probed MusicBrainz `ws/2` and the Cover Art Archive live to
  validate the album mapping instead of reasoning about it. Rewrote
  `docs/sprints/025-second-domain-albums.md` around six named seams, added Sprint 026
  (status vocabulary, seam 5b), renumbered games 026→027 and series 027→028, moved the
  roadmap to plan revision 10, moved `FINAL_SPRINT` 27→28 in `scripts/validate_project.py`,
  and added the field-spec paragraph to Sprint 024. No source code touched.
- Verified: `python scripts/validate_project.py` passes. Live API observations, all
  reproducible with a descriptive User-Agent:
  - `artist/561d854a…` (Miles Davis) type=`Person` sort-name=`Davis, Miles`;
    `056e4f3e…` (Daft Punk) type=`Group` sort-name=`Daft Punk`; Various Artists
    type=`Other`, not inverted. **MusicBrainz only inverts people.**
  - barcode `888837168625` observed on three distinct *Random Access Memories* releases,
    twice more with a leading zero; 8 of 10 sampled releases carry a barcode, a 1959
    release carries none. **Barcode is not a unique edition key.**
  - `release-group/8e8a594f…` holds 25 releases → release-group≈work, release≈edition.
  - CAA `image` fields are `http://`; final redirect host is `dn710907.ca.archive.org`,
    matched by neither the `archive.org` literal in `ALLOWED_COVER_HOSTS` nor the
    `.us.archive.org` suffix rule, and `validate_url` runs on every hop (`covers.py:117`).
  - CAA sizes: full 811 KiB · 1200px 244 KiB · 500px 49 KiB · 250px 16 KiB, against
    `MAX_COVER_EDGE = 600`.
  - MusicBrainz throttles with **503**, not 429; `x-ratelimit-limit: 1200` observed.
- Deviations: Sprint 025 was previously an unstructured gated pilot. DEC-052 replaces the
  gate with six falsifiable seams and un-gates the sprint — the gate's purpose is served
  better by seams that can each be proved wrong. Seam 5 split into 5a (labels, Sprint 025)
  and 5b (vocabularies, Sprint 026) because the owner judged six seams over-specified for
  one sprint; splitting *before* albums was rejected as it would design the abstraction
  from one domain.
- Blocked/open: the Sprint 026 product question — whether `reread_count` and
  `date_finished` mean anything for an album — is the owner's and is deliberately deferred
  until two domains exist.
- Next: Sprint 024 (export) is unchanged and still `ready`; it runs first. Its format bet
  is confirmed by seam 3, so no redesign — read the new deliverable 2 paragraph and
  DEC-052 before starting.

## 2026-08-14 — Sprint 024 (export), complete
- Done: `GET /api/export` streaming entity-shaped JSON, `?format=csv` streaming the
  Goodreads-shaped CSV. New `application/export.py` and `api/export.py`, router wired in
  `main.py`, `frontend/openapi.json` regenerated. DEC-054 records the attachment answer.
  Product spec §6 route list, §9 and §10 row 6 and technical spec §7.1 updated to match.
  Commits `01bfce1`, `afb1902`.
- Verified: `validate_project.py` pass. `make check` pass. `make test` — 358 backend, 99
  frontend. `npm run test:e2e` — 79 passed, 2 skipped. `make build`, `make smoke-container`
  pass. `git diff --check` clean.
  Walkthrough against the real dev library (7 items, 5 entries) at port 8123; note the
  server auto-migrated it 0006 → 0011 and wrote `backups/pre-migration-20260814T163152Z`
  first. Downloaded both artifacts: correct `Content-Disposition` and content types.
  Corrected item 3's creator sort by hand via `PATCH /api/items/3`
  (`García Márquez, Gabriel José`), re-exported, and read it back — the correction is
  there and `sort_author` still holds the display name. Attached a 1.5 MB epub, renamed
  it, and the export carried the **renamed** filename plus digest with no inlined bytes.
  Resolved the exported sha256 against `data/attachments/85/8565c3d…` and `sha256sum`
  matched. Opened the CSV in LibreOffice headless → xlsx: 17 headers, `Carlos Ruiz Zafón`
  intact.
- Deviations: checkpoints 1 and 3 merged (attachment references are a field of the item
  payload, not a separate slice). The memory criterion needed a comparison across two
  library sizes rather than the absolute bound first written — peak is dominated by ~1 MB
  of fixed statement compilation, so a *small* library failed a bound the large one passed.
  CSV formula neutralization added beyond plan and confined to the CSV. All recorded in the
  sprint Outcome.
- Dead ends worth not repeating: `yield_per` / `stream_results` does **not** bound memory
  on SQLite — the driver has no server-side cursor and materializes the whole result. And
  selecting mapped entities defeats any batching, because the `Session` identity map
  retains every instance for the session's life. Both paths select columns and walk in
  keyset batches. Functional tests passed throughout both defects; only the measurement
  saw them.
- Blocked/open: none.
- Next: Sprint 025 (albums, six seams) is `ready`. **Its first act is to cut a branch from
  `main` (DEC-053)** — nothing else in the protocol changes.

## 2026-08-14 — Sprint 025 (second domain, albums), complete
- Done: all six seams on branch `sprint-025-albums` (DEC-053), twelve commits `510b2bc`..`07cfaea`,
  nothing pushed. Seam 2 `IdentityStrategy` (grouping key + source preference), seam 1
  `authors`→`creators`/`credit` with migration `0012_creators` and source-seeded sort names, seam 3
  `FieldSpec` served at `GET /api/item-types`, seam 4 CAA covers with the https-per-hop and
  `.archive.org` fixes, seam 6 no-enrichment plus per-domain URL recognizers, seam 5a status labels,
  and `MusicBrainzProvider` with its own 1.1 s pacing. DEC-055 and DEC-056 appended.
- Verified: `validate_project.py`, `make check`, `make test` (387 backend, 106 frontend),
  `npm run test:e2e` (79 passed, 2 skipped), `make build`, `make smoke-container`, `git diff --check`
  — all green. Walkthrough in Chromium against the **real dev library** at `127.0.0.1:8123`: it
  auto-migrated 0011→0012 and wrote `backups/pre-migration-20260814T220529Z` first; added *Kind of
  Blue* (item 8) and *Discovery* (item 9) as real albums with cover art fetched through the whole CAA
  redirect chain. `Daft Punk` stored `Daft Punk` and `Miles Davis` stored `Davis, Miles`. Compared
  every row against the pre-migration backup: no creator or sort name lost, item 3's hand correction
  carried verbatim.
- Deviations: checkpoints 5+6 and seams 6+5a merged into single commits; two extra fixture commits;
  `/api/health/providers` now lists MusicBrainz; shared-surface copy stopped saying "book".
- Dead ends worth not repeating: **the container cannot run the walkthrough against the dev checkout**
  — compose runs as uid 10001 and `data/` is owned by the host user, so it dies with "attempt to
  write a readonly database"; use `make smoke-container` for the container gate and run the app
  directly for the library walkthrough. **Two MusicBrainz releases can share the group's own
  `first-release-date`** (mono and stereo *Kind of Blue*), so release selection needs a stable
  tiebreak or it flips between pressings. `text("... IN :param")` does not expand in SQLAlchemy —
  build the placeholders. And a blanket `authors`→`creators` rename over the tests will break the
  migration tests that deliberately seed *old* rows: those must keep the old key.
- Blocked/open: none. The Goodreads CSV fix (`07cfaea`) came from the walkthrough, not the suite.
- Next: Sprint 026 (status vocabulary, seam 5b) is `ready` at `docs/sprints/026-status-vocabulary.md`.
  **Its first deliverable is a question for the owner, not code**: whether `reread_count` and
  `date_finished` mean anything for an album.

## 2026-08-15 — Sprint 026 (statuses, formats and tracklists), complete
- Done: seam 5b on branch `sprint-025-albums` (DEC-061, amending DEC-053 for this sprint at the
  owner's direction), six commits `ebe6827`..`7246134`, nothing pushed. `Domain` declares what an
  *entry* can be: an ordered status vocabulary with its own labels and triage keys, a default status,
  which of the passage fields exist, its formats, and the personal panel's heading. Migration
  `0013_entry_formats` adds the join table **and** rebuilds `entries`. Tracklists landed rather than
  being deferred. DEC-060 and DEC-061 appended; product spec §3.2/§3.3/§7 and technical spec §5.1/
  §7.1 updated.
- Verified: `validate_project.py`, `make check`, `make test` (**411 backend, 110 frontend**),
  `npm run test:e2e` (**84 passed, 2 skipped**), `make build`, `make smoke-container`,
  `git diff --check` — all green. Walkthrough in Chromium against the **real dev library** at
  `127.0.0.1:8123`; it auto-migrated 0012→0013 and wrote `backups/pre-migration-20260815T145406Z`
  first. Added *Discovery* with **no status in the request** and it landed `owned`; added *Kind of
  Blue* as `wishlist` and marked it `Vinyl` with neither value moving the other; both fetched cover
  art through the whole CAA chain. `read` on an album, `owned` on a book, `reread_count` on an album
  and `borrowed` on an album are each a 422 naming the domain. The album page reads "YOUR COPY" with
  five tracks `A1`..`B2`; the book page still reads "YOUR READING DATA" with rereads and dates and no
  tracklist. Triage `o` set the focused album to `owned`. No console errors.
- Deviations: checkpoints 1 and 3 straddle, because migration 0013 had to carry both the new table
  and the `entries` rebuild. A `rows` field is deliberately **not** hand-editable. Two MusicBrainz
  fixtures were re-recorded in their own commit (`9821d30`) because the adapter's own request
  changed. The dev library's three albums were deleted rather than migrated, per the owner, after a
  backup to `backups/pre-sprint026-20260815T142246Z`.
- Dead ends worth not repeating: **a dynamically built `StrEnum` is opaque to mypy** — spell the
  published unions out and pin them to the registry with a test instead. **SQLAlchemy does not
  reflect SQLite CHECK constraints**, so a batch rebuild that relies on reflection silently drops
  every one of them; `copy_from` with the table spelled out is the only safe form. **Ctrl+A selects
  every triage row without focusing one**, so a per-domain hotkey map must fall back to the
  selection's own vocabulary or the keyboard dies on a select-all. And the frontend's registry
  helpers must tolerate a partial or odd-shaped `/api/item-types` response: several tests mock every
  URL with one body, and a helper that trusted the shape took the whole page down.
- Blocked/open: none. **The two defects the suite could not see were both found by the walkthrough**
  — a shared status counted once across domains, and `digital` listed twice in the format filter.
- Next: Sprint 027 (library shell and shelves) is `ready` at
  `docs/sprints/027-library-shell-and-shelves.md`. **Its first act is a question for the owner**:
  whether the domain tab defaults to all or to the last domain used.

## 2026-08-15 — Sprint 027 (library shell and shelves), complete
- Done: the three owner-feedback items from 2026-08-14 (roadmap items 1, 4, 5), on branch
  `sprint-025-albums` at the owner's direction (DEC-063, amending DEC-053 as DEC-061 did for 026).
  Four commits `80fea5f`..`531f38f` plus the closing one, nothing pushed. A `type` filter on
  `GET /api/entries` with a published `ItemTypeName` union and `type` in `_filter_key`; a domain tab
  strip rendered from `GET /api/item-types`, defaulting to the last domain used; the library
  virtualizing against the window instead of a fixed-height box; inline shelf editing on the detail
  page with create-on-type, out of `OpinionDialog`. DEC-062 and DEC-063 appended; product spec §7
  and technical spec §7.1/§7.2/§8 updated. Sprint 028 expanded into its own file.
- Verified: `validate_project.py`, `make check`, `make test` (**414 backend, 120 frontend**),
  `npm run test:e2e` (**86 passed, 2 skipped**), `make build`, `make smoke-container`,
  `git diff --check` — all green. Walkthrough in Chromium against the **real dev library** at
  `127.0.0.1:8123`, backed up to `backups/pre-sprint027-20260815T154413Z` first. Tabs render
  `All / Book / Album`; Album gives two records, one chip row without the redundant heading, and a
  format selector holding no `Physical`; "All" keeps both grouped rows and the flat five-format
  union. The choice survives a reload and a return from a detail page. The feed has **0px of inner
  scroll** at 375/768/1440 with 1/2/4 columns while the document scrolls and nothing overflows
  sideways; six presses of `j` moved focus to entry 11 and scrolled the window to 341px with the row
  fully in view. *Cien años de soledad* onto a brand-new shelf in one control with no dialog and no
  navigation; two triage rows onto "Work" in bulk, `entry_count` 1 → 3. No console or page errors.
- Deviations: **AC6 rested on a false premise.** It asserted that bulk shelf assignment "still works
  in triage"; `add_shelves` existed on the endpoint and was tested, but no control ever sent it, and
  product spec §7 line 671 said so. Building it was the owner's call at planning time. No shelf
  control on a library card — the sprint named that as where scope grows and the owner chose detail
  plus triage instead. `EntryFilter` deliberately did **not** gain `type`: triage has no domain tab
  and the bulk path already refuses a selection spanning domains.
- Dead ends worth not repeating: **`offsetTop` is the wrong scroll margin** — it walks a chain of
  offset parents the motion wrapper interrupts, so read `getBoundingClientRect().top + window.scrollY`
  instead, and observe `document.body` as well as the list, because the chips above it reflow without
  the list's own size ever changing. **cmdk points its input's `aria-labelledby` at the element its
  `label` prop renders**, which beats an `aria-label` on the input itself, so the input had no
  accessible name until the name was given to `Command`; there is no `Command.Label` in this version
  to render one by hand. **jsdom has no `ResizeObserver`** and cmdk constructs one on mount, so the
  test setup shims it. And `libraryQueryString` puts `sort`/`order`/`limit` first, so a test
  asserting `"/api/entries?type=album"` is asserting the parameter order, not the filter.
- Blocked/open: none. One flaky failure seen once — `triage animates its action bar but not under
  reduced motion` failed in a single full-file run and passed alone and in every subsequent run
  including the full suite. Motion sampling timing, not a regression, but worth watching.
- Observed and out of scope: the header Inbox badge and each domain's `unsorted` chip both read
  "Inbox", so three buttons on `/` share that label — correct in each place, ambiguous together.
  `/triage` still scrolls inside `h-[min(70vh,760px)]`; that is deliberate for a dense working table
  and was left. The walkthrough created a shelf "Latin American" on item 6 and added two books to
  "Work"; both left in place as realistic test data.
- Next: Sprint 028 (the domain contract) is `ready` at `docs/sprints/028-the-domain-contract.md`.
  **It is gated**: Phase A writes the contract and a conformance suite and changes nothing
  user-visible, and Phase A concluding that little is misplaced is a complete outcome.

## 2026-08-15 — Sprint 027, second pass (the add flow), complete
- Done: the owner tried the closed sprint and reported the add screen, and directed it folded into
  this sprint rather than scheduled — so 027 was reopened, the way 020 was for its Phase B. Three
  commits `762ed70`..`d722135` plus the closing one. `GET /api/search/preview`; the confirm screen
  rendering everything the search already returned, from the domain field spec; notes, formats and
  the domain's passage fields on `POST /api/entries`, validated against the item's own domain before
  the write; the create-on-type shelf control moved to `features/shelves` and shared with the add
  screen; one closed `FormatPicker` shared by the add screen and the opinion dialog. DEC-064
  appended; product spec §7 and technical spec §7.1 updated.
- Verified: `make check`, `make test` (**419 backend, 126 frontend**), `npm run test:e2e`
  (**86 passed, 2 skipped**), `validate_project.py` — all green. Walkthrough against the real dev
  library and **live providers** at `127.0.0.1:8123`: a MusicBrainz search showed year and artist
  credit instantly with zero preview requests; *Load full details* spent exactly one and added
  label, catalogue number, country, format and track count, after which the button is gone. A record
  offers notes and formats and no dates or reread count; a book offers all of them. Added *Rayuela*
  with a brand-new shelf, notes, `physical`, a finished date and 2 rereads in one action — entry 17,
  everything persisted, publisher and page count fetched. No console or page errors.
- Deviations: the measurement changed the design. The owner asked "do we already have the data?" and
  the answer is **partly** — identity yes, description/tracklist no, and there is no provider
  response cache — so it is a button rather than an effect, and the fork was put to the owner with
  that cost stated (DEC-064).
- Dead ends worth not repeating: **a `TabsTrigger` with no `TabsContent` behind it is a critical axe
  failure** — `aria-controls` points at an element that does not exist. A single-choice filter is a
  radio group, which is what `AddPage` already used for the very same choice. **`Command`'s `label`
  prop is the only way to name a cmdk input** in this version; there is no `Command.Label`. And
  **`make format` runs prettier over the tests**, so a scripted edit matching a pre-format string
  silently no-ops — two of my own verification edits did exactly that and made a test look like it
  bit when it did not. Assert on every replacement, and re-check that a new test fails for the
  reason claimed *after* formatting.
- Blocked/open: none. **Two defects the unit tests could not see, each caught by the gate built for
  it**: the axe suite caught the tab strip's dangling `aria-controls`, and the walkthrough caught
  `Language` rendered twice on a real MusicBrainz record, because both domains declare it as a field
  while the candidate also carries a column of that name.
- Observed and out of scope: the walkthrough left entry 17 (*Rayuela*, 2000 Alfaguara edition) and a
  shelf "Rayuelas" in the dev library. The library now holds 10 entries.
- Next: Sprint 028 (the domain contract) is `ready`. **Gated**: Phase A writes the contract and a
  conformance suite and changes nothing user-visible, and concluding that little is misplaced is a
  complete outcome.

## 2026-08-15 — Sprint 028 planning pass, and Phase A (in progress)
- Done: re-derived Sprint 028's baseline from the code rather than 027's summary, since the file said
  to (`4cb28f8`, DEC-066). Rewrote the sprint's objective, baseline, deliverables and acceptance
  criteria around the finding; repaired three stale references while reading (ROADMAP still headed
  the per-domain-imports contract "Sprint 029" after DEC-065 renumbered it 030; WORKFLOW still named
  028 as the final sprint; HANDOFF's "no `type === "album"` branch anywhere" was silent about the
  three `itemType === "book"` branches on the add screen). Then Phase A: the conformance suite
  (`afbf5ff`) and the contract plus both verdicts (`a35c027`). Three owner decisions were taken at
  planning time and are DEC-066: 028 runs on this branch, the frozen CHECK constraint is a costed
  finding rather than pre-authorized work, and the contract prescribes a per-domain code home.
- Verified: `make format`, `make check`, `make test` (460 backend, 129 frontend), `npx playwright
  test` (86 passed, 2 skipped), `make build`, `make smoke-container`, `git diff --check`,
  `validate_project.py`. **The suite was shown to bite against a registered domain, not only against
  its fixtures**: removing `pending`'s hotkey from `ALBUM_STATUSES` failed
  `[album-statuses_are_a_usable_vocabulary]` and renaming `track_count` to `year` failed
  `[album-fields_are_described_completely]`; both injected, observed, reverted. The recognizer repair
  was exercised against the running app on the real dev library with live providers: `http://[` is
  now 422 with the actionable message rather than 502, an ISBN still resolves, a real MusicBrainz
  release-group URL still resolves with its tracklist, no errors in the log.
- Deviations: **AC6 (Phase A changes nothing user-visible) was broken deliberately and once.** The
  suite failed on its first run against both shipped domains — `urlsplit` raises on `http://[`, and
  because `resolve_input` asks each domain in turn, the first recognizer to raise denied every domain
  after it its turn. That is one domain breaking another's add box, which is the exact failure this
  epic exists to prevent, so it was repaired here rather than costed: a shared `split_url`, plus
  isolation in the loop. Recorded in DEC-067 and the sprint Outcome.
- Dead ends worth not repeating: under **vitest, `import.meta.url` is the dev server's URL, not a
  file path** — `readFileSync(new URL(...))` fails with "The URL must be of scheme file"; read from
  `process.cwd()` instead. `ruff` will not wrap a long f-string inside an `assert` message, so the
  100-column limit has to be met by splitting the literal by hand. And `make format` runs prettier
  over everything, so re-run the focused test *after* formatting rather than before.
- Blocked/open: **the Phase B gate.** DEC-067 orders it — per-domain packages, `provider_health`
  derived from the registry, the cover chooser declared per domain, then dropping
  `ck_entries_status` as a separate schema change — and it runs only on an explicit owner
  go-ahead. Nothing else is open.
- Observed and out of scope: resolving a "Kind of Blue" release-group URL returns the Swiss Blues
  Authority record, which is the arbitrary release selection already on record rather than a
  regression. The dev library is now 13 entries — the owner has been adding albums since 027 closed.
- Next: put the Phase B gate to the owner with DEC-067's costed table. On a go-ahead, start with the
  per-domain packages; on a no, close Sprint 028 with Phase A as the complete outcome.

## 2026-08-15 — Sprint 028 Phase B, and the sprint closed (complete)
- Done: the owner authorized **all four** DEC-067 items at the gate. Ran smallest-first rather than in
  DEC-067's order, so the package move was the tail that could be handed forward if it ran long
  (DEC-069 records the departure). `acbbbbf` provider_health from the registry; `47ac1bc`
  `Domain.chooses_covers` and the chooser hidden where it cannot work; `ff94c7f` migration
  `0014_status_is_the_domains`; `82fb11c` `domains/book/` and `domains/album/` with `domain/spec.py`
  and `domain/registry.py` behind them; `fa67410` the adapters and importers into their packages;
  `12dd7fc` the smoke script's module path. DEC-069 appended; technical spec 2, 5.1 and 6.6 updated.
- Verified: `make check`, `make test` (**469 backend, 130 frontend**), `npx playwright test` (86
  passed, 2 skipped), `make build`, `make smoke-container`, `git diff --check`, `validate_project.py`.
  Walkthrough on the **real dev library with live providers** in a browser at `localhost:5199`:
  migration 0014 ran on the real database after writing `backups/pre-migration-20260815T223017Z`,
  `ck_entries_status` is gone from the live schema and `ck_entries_score` is not; the album detail
  page no longer offers *Choose a cover* and the book page still does (screenshots taken);
  cover-candidates answers `not_supported` for all three album items; an Open Library book search
  returned 18 results and a MusicBrainz album search 20 from their new homes; an album's status went
  `owned` → `wishlist` → `owned` with no CHECK behind it and `read` was still refused with "Album has
  no status named 'read'". No console errors, no server errors.
- Deviations: Phase A broke AC6 once, deliberately — the recognizer repair turns a malformed paste
  from 502 into 422. Phase B reordered DEC-067's list. Both recorded.
- Dead ends worth not repeating: **a scripted import rewrite must be indentation-aware** — three
  function-local imports were rewritten at column 0 and ruff refused to parse the file. **`make
  format` reflows a long import back into a parenthesised block**, so a follow-up `sed` matching the
  single-line form silently no-ops; this is the second sprint to hit that. And **a migration that
  imports the live registry is a bug even when it passes**: `0013` rendered its CHECK from
  `ALL_STATUSES` at run time, so two installs a month apart could build different constraints.
- Blocked/open: none. Two couplings remain **by decision** (DEC-067 rows 2 and 4): the hand-spelled
  published unions and the central cover-host allowlist.
- Observed and out of scope: the library tab strip still reads `All | Book | Album`; DEC-065 removes
  "All" in Sprint 029. The walkthrough left album entry 16 back at `owned` where it started.
- Next: Sprint 029 (one search bar) is `ready` at `docs/sprints/029-one-search-bar.md`. It rebuilds
  `/` around a single bar and removes "All" as a filter.

## 2026-08-15 — Sprint 028 third pass (documentation), sprint closed again (complete)
- Done: the owner asked, before closing, that the docs convey the new structure. Reopened 028 rather
  than scheduling it (DEC-070; same precedent as 020 and 027). New: `docs/guides/adding-a-domain.md`
  (three ASCII diagrams, a nine-row job table, step-by-step against `domains/album/`, what you get
  free, what you may never touch, the IGDB worked verdict), `CONTRIBUTING.md`, `docs/README.md` (the
  map, labelling every document canonical/historical/proposal). Updated: README gains a Domains
  section and a docs pointer; AGENTS.md gains the domain boundary as an invariant and the map as
  required reading; product spec §2 table and §9; ROADMAP's Sprint 030 contract paths; status headers
  on `assessment.md`, `domain-architecture-proposal.md`, `domain_metadata_roadmap_report.md`.
  **Nothing deleted** — a historical doc is dated, not wrong. Commit `f7569fa`.
- Verified: **the guide was tested by following it.** Built a throwaway `game` domain from the guide
  alone — own package, three fields, `playing`/`finished` statuses, own formats, identity strategy —
  registered it, and ran everything: conformance suite green (56), **480 backend tests green, no
  migration needed**. The only legitimate gate failure was OpenAPI drift, which is a documented step.
  Then removed the domain and re-ran: `make check`, `make test` (469 backend, 130 frontend) green.
- Deviations: **two documentation defects from earlier in this sprint were found and repaired** —
  technical spec 6.6 still said the per-domain layout was "not yet inhabited" (a Phase B edit lost
  because a second `write_text` in the same script used the pre-edit string), and product spec §9
  still said the registry would be extracted later and that games/series were Sprints 027/028.
- Dead ends worth not repeating: **two `p.write_text(t.replace(...))` calls in one script silently
  discard the first edit** unless `t` is reassigned between them. That is how the spec regression
  shipped. Assert on the file afterwards, not on the return value.
- Blocked/open: none.
- Observed and out of scope: four other `{"book", "album"}` assertions were checked and deliberately
  left — they assert over rows the test itself seeded, which is correct and not closed-world.
- Next: Sprint 029 (one search bar) is `ready`. It rebuilds `/` around a single bar and removes "All"
  as a filter.

## 2026-08-15 — Assessment answered, plan revision 12 (no sprint active work)
- Done: wrote `docs/domain-expansion-assessment.md` at the owner's request — what the domain work
  proved (a throwaway third domain passed everything with five shared lines and no migration), the
  structural limit of that proof (the conformance suite cannot check whether the *contract* is
  sufficient, and both domains are the same shape), one rewrite risk (a flat entry blocks serial
  domains) and six additive gaps, with costed options. The owner answered the same day: **DEC-071**.
  Sprint 029 gains deliverable 6 (chrome copy neutrality, 18 strings, listed with the rule and an
  acceptance criterion); **entry depth becomes Sprint 030, Phase A only**, carrying the owner's
  one-level/provider-shaped hypothesis and the tracklist precedent; per-domain imports moves to
  **031**; `FINAL_SPRINT` 30 → 31; plan revision **12**.
- Verified: `python scripts/validate_project.py` and `make check` green. No code changed.
- Deviations: the assessment recommended depth *before* 029; the owner resequenced it after, and the
  decision records why that is the better call. It also rejected the implicit premise that the music
  release should wait for a third domain — a release waits for a feature, not a validation exercise,
  and DEC-071 corrects that drift in how "gated" was being used.
- Dead ends worth not repeating: renumbering an unbuilt sprint is cheap **only** because it has no
  file and nothing closed depends on it (the DEC-065 precedent). The two forward references inside
  the closed Sprint 028 file were corrected visibly — naming the old number and the decision — rather
  than silently rewritten, which is what `AGENTS.md` actually forbids.
- Blocked/open: **merging and releasing the album work is an owner action and is now unblocked.**
  Nothing else.
- Next: Sprint 029 (one search bar, now with copy neutrality) is `ready`.

## 2026-08-16 — Sprint 029 (in progress: all code and verification done, docs pending)
- Done, before the sprint: reviewed the ready sprint file against the code and
  corrected it (`8d877a3`). The copy inventory claimed eighteen strings across eight
  files while its own table listed nineteen across nine, and it missed `HomePage`'s
  empty state and `NotFoundPage` entirely — `HomePage` being the screen the sprint
  rebuilds. AC9 was a prose claim that could never reach zero without renaming
  `manualBookSchema`/`ManualBookValues`; it is a runnable command with stated
  exclusions now. The `AbortController` and the stale-response guard joined the
  functionality inventory as rows 12 and 13. `WORKFLOW.md`'s final-sprint rule still
  said Sprint 030 / revision 11 while citing `FINAL_SPRINT`, which DEC-071 moved to 31.
- Done, the sprint: six commits. `397da78` removes "All" and makes the list query wait
  for the registry; `a174842` extracts `AddForm` and `ResultsGrid` and adds `labelFor`;
  `7c94cb4` builds the unified bar, the settled-and-empty rule, the web-results region
  and the add dialog; `47e0b4d` leaves `/add` to manual entry and moves its tests;
  `de12294` is copy neutrality; `97b4c34` is the AC7 gates and the keyboard rule;
  `d845317` is the walkthrough fix.
- Verified: 469 backend + 146 frontend tests, 90 e2e (2 skipped), `make check`,
  `make build`, `make smoke-container` all green. **The quota rule was verified by
  counting requests against live providers**, not by inspection: a title I own costs
  0 provider requests; one I do not costs exactly 1; the same string retyped costs 0;
  **Add** on a query with local hits costs 1; a pasted ISBN takes
  `/api/search/resolve`. AC7 re-run with a web-results block: 28 mounted cards against
  DEC-023's bound of 48, and the list's bounding box does not move when the block
  appears — results render *below* the list, so `scrollMargin` never changes.
- Deviations, and the one that matters: **AC7 says "with a web-results block above
  it" while deliverable 3 and the accepted proposal both say results render *below*
  the library.** Below is what shipped, because deliverable 3 is the specification
  and the proposal's diagram agrees with it; the AC's "above" is an incidental phrase.
  The consequence is that the Sprint 013 class of bug is avoided by construction
  rather than survived — recorded here rather than quietly.
  Also: `/add` lost its domain chooser. `LibraryService.add` types a manual item as
  `DEFAULT_DOMAIN.item_type` whatever the client sends (DEC-067 row 6), so the old
  chooser showed a record's statuses and fields and then wrote a book.
  Also: deliverable 6 needed **no new `Domain` field**. One neutral placeholder
  naming title, creator, ISBN and link serves every domain, and the resolve path it
  advertises is domain-neutral anyway. The backend contract is untouched after all.
- Dead ends worth not repeating: **do not `git checkout <file>` to undo a mutation
  test.** It reverted uncommitted work twice — once losing the `data-web-results`
  attribute and the results-grid label change, once restoring "Add a book" to the
  library's empty state after the copy pass. AC9's grep is what caught the second;
  copy the file to the scratchpad and copy it back instead.
- Walkthrough gate, against the real dev library and live providers (Open Library,
  Google Books, MusicBrainz): everything above, plus adding a record and a book from
  `/` with notes, format and a created shelf, and the duplicate path (200, "Already in
  your library", navigates to `/books/17`). **It found one defect, now fixed
  (`d845317`)**: adding from `/` closed the dialog onto a library still filtered by
  the query that had just missed, so the new entry was created and highlighted where
  nothing could see it. The old flow got this free by navigating to an unfiltered `/`.
  One transient **502 on an album add** (MusicBrainz at add time); the identical retry
  returned 201. Not a sprint regression — the add path is unchanged — but worth
  watching.
- Dev library state: **16 entries, up from 13.** The walkthrough added *The Left Hand
  of Darkness* (19), *Selected Ambient Works 85–92* (20), *Kid A* (21) and *OK
  Computer* (22), and created a shelf named *Walkthrough* (id 5). Left in place rather
  than deleted; the pre-walkthrough database is at
  `backups/pre-sprint029-20260816T042730Z/books.db` if the owner wants it back.
- Blocked/open: none.
- Next: **documentation only.** Product spec section 7 still describes `/add` as the
  place you search; technical spec sections 7.1/8 describe the two debounces; a
  decision entry is owed for the settled-and-empty rule as built, the `/add` domain
  chooser removal, the below-not-above resolution and the no-new-`Domain`-field
  outcome. Then the sprint `Outcome`, the ROADMAP impact review, `state.json`,
  `HANDOFF.md`, and the `docs(sprint-029): close sprint and hand off` commit.

## 2026-08-17 — Sprint 029 closed (complete), Sprint 030 ready
- Done: the documentation close the previous session left, and nothing else — no
  application code was touched. Product spec section 7 now describes `/` as the screen
  you search and add from (one bar, one domain, results below, the confirm step as a
  dialog) and `/add` as manual entry with no domain chooser and why; its Interaction
  notes carry the `a`-focuses-the-bar change and the focus rule for `j`/`k`. Technical
  spec 7.1 names the two searches, what each costs, and that which one a keystroke
  reaches is a frontend rule; section 8 carries the firing rule clause by clause, the
  two-regions rule, the below-not-above reason and the shortcut rule. **DEC-073**
  records all four open items: the firing rule as built (three clauses DEC-065's
  sentence did not have), results below rather than above, `/add` losing its domain
  chooser, and deliverable 6 needing no new `Domain` field. Sprint 029's Outcome,
  the ROADMAP impact review, `docs/README.md`'s proposal row, `state.json` and
  `HANDOFF.md` follow, plus `docs/sprints/030-entry-depth.md` expanded from the
  template.
- Verified: `make test` re-run at the close — **469 backend, 146 frontend**, the same
  counts the implementation session recorded. `python scripts/validate_project.py`
  green. AC9's grep re-run: **two lines, both JSX comment continuations** in
  `HomePage.tsx`, nothing that reaches a screen. `make check`, `git diff --check`
  green. The container was rebuilt and run for the owner to look at.
- Deviations: none from the plan. The one thing worth naming is that the previous
  session's note about "technical spec sections 7.1 and 8 describing the two
  debounces" was approximate — neither section stated a debounce value; section 8
  had one generic line about search being debounced and cancellable. The rule is
  written there now rather than corrected there.
- Blocked/open: none. **Sprint 030 is Phase A only and gated** — it ends with a
  verdict and a question to the owner, not with an implementation.
- Next: **the merge (DEC-072)**, which is an owner action. `sprint-025-albums` goes
  into `main` with two things in the same merge: `README.md`'s feature copy stops
  being book-only, and `docs/operations/release-notes-v1.2.md` is written following
  the v1 and v1.1 precedent. Neither was written on this branch, because the handoff
  is explicit that the copy changes when the branch merges and not before. After
  that, claim Sprint 030.

## 2026-08-17 — Sprint 029 second pass (complete), Sprint 030 ready again
- Done: five owner-reported UI defects, found by using what 029 built against the
  real library. `d130fa0` a `long_text` field spans both columns of the confirm step
  (split on the declared type, mirroring `DetailPage`'s `inlineFields`/`blockFields`,
  not on the name "description"); `e746c32` the search bar clears in one press —
  box, `q` and web results together, refocusing the box, sharing one function with
  the successful-add path; `cc38640` an active query with no rows gets one line
  instead of the tall empty state; `84c2ec7` the status chips become a fourth filter
  beside sort/shelf/format, built on `FormatPicker`'s popover shape because the
  filter is multi-valued; `4007e89` Files becomes its own region on the detail page
  at the weight of *Edit opinion*. Then product spec §7, **DEC-074**, the sprint's
  *Second pass* Outcome, and this close.
- Verified: every change test-first, each new test observed failing for its own
  reason first. `make check`, `make test` (**469 backend, 153 frontend**, seven new),
  `npx playwright test` (**90 passed, 2 skipped**), `make build`,
  `make smoke-container`, `git diff --check`, validator — green. Walkthrough against
  the real dev library in the container with live providers and a screenshot of each
  of the five: real counts in the status panel (Read 9, To read 2), one and two
  statuses reaching the URL, *Neuromancer* producing the compact line and no tall
  empty state, the clear control emptying box + URL + results and returning focus,
  the description measured at 588px of a 622px panel, and `/books/19` showing Files
  as its own region with exactly one attach button. No console errors.
- **Trap worth not rediscovering: stop the container before running e2e.** The dev
  server proxies `/api` to `localhost:8000`, so a container left running there
  answers every request a spec forgot to stub — with the real dev library.
  `add-detail.spec.ts`'s stagger test then clicks a real *Rayuela* card instead of
  the web result and fails, three runs in a row, looking exactly like a regression.
  It reproduces against the pre-pass source, which is how it was told apart from one.
- Deviations: none. Two judgement calls are in DEC-074 rather than left in the code:
  the status counts moved inside the panel (and if they turn out to be read
  constantly, the fix is to surface them in the trigger, not to bring the row back),
  and the empty state is suppressed during a query rather than deleted, with one
  line rather than nothing because the settle rule waits ~800 ms and a page that
  goes blank in that gap reads as broken.
- Blocked/open: none.
- Next: unchanged by this pass — **the merge (DEC-072)**, an owner action, carrying
  `README.md`'s feature copy and `docs/operations/release-notes-v1.2.md` with it.
  Then claim Sprint 030.

## 2026-08-17 — Sprint 029 second pass, follow-on repair (complete)
- Done: one defect the owner found reviewing the second pass. **The shell's
  *Library* link, pressed while already on the library, left the page saying
  "Loading your library…" with nothing coming.** The link is `/` with no query, so
  it strips `type` out of the URL; every list request names a domain since 029's
  deliverable 2, and the restore that supplies one ran once per mount — correct for
  every arrival that remounts the page and wrong for the only one that does not.
  The restore now answers to the URL lacking a `type`, whenever that happens;
  writing the value back is its own guard against repeating, so the `restoredDomain`
  ref is gone rather than replaced.
- **Recorded in DEC-074 and in 029's second-pass Outcome rather than by reopening
  the sprint a third time.** `WORKFLOW.md` has no `completed → in_progress`
  transition; the repair is small, closed, tested and part of the same review.
  State stays at 030 `ready` and the sprint stays `completed` — this was not done
  with the sprint open, and the record says so.
- Verified: reproduced against the running container first (`/` → 11 cards,
  *Library* → 0 cards and the loading state), then fixed and re-checked — the URL
  keeps `?type=book`, the eleven cards stay, three presses running are stable, the
  **remembered** domain comes back (Records after choosing Records, five cards), and
  the ordinary arrival from `/shelves` is unchanged. No console errors. Held by a
  unit test that clicks a `Link` to `/` beside the mounted page and an e2e test
  through the real shell; **the e2e test was mutated against the old guard and
  observed failing** before being kept. `make check`, `make test` (469 backend,
  **154** frontend), `npx playwright test` (**91 passed**, 2 skipped),
  `git diff --check`, validator — green.
- Deviations: none. Worth naming for the next agent: the first version of the new
  e2e test passed alone and failed in the suite, because it left `/api/item-types`
  unstubbed and so asserted against whatever answers `localhost:8000` — the same
  proxy trap as before, in its other form. It stubs the registry now.
- Blocked/open: none.
- Next: unchanged — **the merge (DEC-072)**, an owner action, carrying `README.md`'s
  feature copy and `docs/operations/release-notes-v1.2.md`. Then Sprint 030.

## 2026-08-17 — The merge and v1.2.0 (release)
- Done: the owner authorized the merge, so DEC-072 was carried out. `build: release
  v1.2.0` (`ba70c30`) carries the two things that had to go in *with* the merge:
  `README.md`'s feature copy stops being book-only — two domains, one search bar,
  music as its own vocabulary — and `docs/operations/release-notes-v1.2.md`,
  following the v1 and v1.1 precedent including a *Known and left* section that
  names manual entry's default-domain binding, book-only import and the arbitrary
  release selection. Versions moved to **1.2.0** in `backend/pyproject.toml`,
  `frontend/package.json` and the FastAPI string, with `uv.lock`,
  `package-lock.json` and `frontend/openapi.json` regenerated — the FastAPI string
  is part of the API contract, which is what makes the openapi file move with it.
  Then `sprint-025-albums` merged into `main` as one `--no-ff` merge (`d4d50e9`),
  tagged **`v1.2.0`**, and `main` pushed to `origin` — the first push since v1.1.0.
- Verified: before the merge on the branch and again on `main` after it —
  `python scripts/validate_project.py`, `make check`, `make test` (**469 backend,
  154 frontend**), `npx playwright test` (**91 passed, 2 skipped**), `make build`,
  `make smoke-container`, `git diff --check` — all green on both sides, so the merge
  is proven rather than assumed. The container was rebuilt from the merged tree and
  answers `/api/health/ready`.
- Deviations: none. `git merge -F -` does not read stdin ("could not read file
  '-'"); the message went through a file. Worth knowing for the next merge.
- Blocked/open: none. **`sprint-025-albums` is kept rather than deleted**, as
  history for the five sprints that ran on it.
- Next: claim **Sprint 030** — Phase A only, gated, a verdict rather than an
  implementation. It needs no branch by default: DEC-053's arrangement covered the
  album line and is discharged. Taking one is a deliberate choice to record.

## 2026-08-20 — Plan revision 13: Sprint 031 absorbs the import boundary, row 6, and the README story
- Done: documentation-only re-plan from owner feedback after v1.2.0. Measured the ingest/import
  layer against the domain contract (DEC-076): triage, the import ledger, undo, fingerprint
  idempotency and the two readers are already domain-neutral; the book shape is five named places
  (`api/imports.py`, `application/imports.py`, `ImportRepository.commit`,
  `ImportPage.tsx`/`api/imports.ts`, and `AddService.add`'s `DEFAULT_DOMAIN` binding). Expanded
  Sprint 031's contract in `docs/sprints/ROADMAP.md` to carry the measurement, the `Importer`
  boundary's concrete shape, DEC-067 row 6 (manual entry honours the domain — the +Add gap), and
  the README *Importing and triage* section plus the importer half of
  `docs/guides/adding-a-domain.md`. `spotify → music` stays a Future epic as an architecture goal,
  not a commitment; its track-vs-album shape is recorded as a Sprint 030 question. Plan revision
  12 → 13 in the roadmap and `state.json`; `FINAL_SPRINT` unmoved (31) with the validator comment
  updated. No sprint file for 031 yet — the closing agent for 030 expands it from `TEMPLATE.md`,
  per the roadmap's rule.
- Verified: `python scripts/validate_project.py` (pass), `make check` (format, lint, types,
  OpenAPI drift — all green). No application code changed, so no test suite run was owed; docs and
  one comment in `scripts/validate_project.py` only.
- Deviations: none. No sprint is active beyond 030 (`ready`); this session changed planning
  documents only, which AGENTS.md §1 permits as an unambiguous documentation repair — the change
  was owner-directed.
- Blocked/open: none.
- Next: unchanged — claim **Sprint 030** (Phase A only, gated, a verdict). Its AC7 impact-review
  of 031 now runs against the expanded contract.

## 2026-08-20 — Sprint 030 (complete)
- Done: executed Phase A end to end and closed the sprint. Claimed 030 (state + sprint file);
  re-derived the implementation baseline from code; measured MusicBrainz live as the control
  (two re-captures committed, tracklist identical to 2026-08-15, third 503-throttling
  observation); probed TMDB and IGDB (both 401, no credentials — owner asked via clarify, no
  answer, fallback rule applied); wrote `docs/entry-depth-verdict.md` (four questions, the
  nine-surface cost table, the verdict: flat holds, build nothing); adopted it as DEC-077;
  pointed product spec §11.4 at it; impact-reviewed 031 (unaffected — importers create flat
  entries and provider `rows`); answered the Spotify shape question in the ROADMAP (tracks roll
  up to albums); added `test_sprint030_control.py` and `test_flat_entry_contract.py`; expanded
  the 031 contract into `docs/sprints/031-per-domain-imports.md` from TEMPLATE.md per the
  roadmap rule. Commits: `6eeb00f`, `1416dc0`, `84e53d9`, `8e94771`.
- Verified: `python scripts/validate_project.py` (pass), `make format` (no drift), `make check`
  (green), `make test` (frontend 154/154; backend 472 passed incl. the two new tests),
  `git diff --check` (clean). E2e/build/container not owed — no application code changed, per
  the sprint's Verification section. No walkthrough owed for the same reason; nothing
  user-visible exists to walk through.
- Deviations: two, both recorded in the verdict. (a) TMDB/IGDB are labelled paper walks — the
  sprint risk note's anticipated fallback. (b) The TMDB arm's first draft was model memory;
  the owner challenged it mid-session and it was re-grounded against the published API
  reference the same day (verdict §1, DEC-077, and the provenance table all carry this).
- Blocked/open: the Phase B gate question is with the owner (recommendation: NO). TMDB/IGDB
  arms stay paper walks until credentials exist; the TMDB epic inherits the measurement.
- Next: owner answers the gate; then claim **Sprint 031** — file exists
  (`docs/sprints/031-per-domain-imports.md`), status `ready`, state points at it. Closing 031
  sets the project `complete` per WORKFLOW.md's final-sprint rule.

## 2026-08-21 — Sprint 031 (complete; project complete)
- Done: confirmed Sprint 030's closure was internally consistent before claiming 031. Added the
  importer protocol and conformance checks; registered Goodreads and Calibre through the book
  domain; replaced duplicate application paths with one domain-validated pipeline; published the
  importer registry and rendered import tabs from it; removed book/default-domain assumptions
  from the repository; made manual entry require and honour its selected domain; documented the
  importing/triage and connector stories. DEC-078 records the chosen boundary. Commits:
  `5d908bb`, `a6666c8`, `4877447`, `aeb19f0`, `a9f10f0`.
- Verified: validator, format/static/type/OpenAPI checks, and diff checks passed. Focused backend
  import/conformance/jobs: 97 passed; manual-add neighbourhood: 43 passed; frontend Import/Add:
  16 passed; targeted Playwright import/add flows: 12 passed. The realistic isolated walkthrough
  passed (1 test): Goodreads and a read-only synthetic Calibre library previewed and committed
  through the generic routes, one batch was undone, remaining rows were bulk-triaged until the
  inbox was clear, and the UI added an owned Album with album-specific metadata. The first
  walkthrough assertion expected a numeric empty count; it was corrected after observing the
  product's truthful “Inbox is clear” state. A queued Calibre enrichment logged an expected,
  non-blocking Open Library `provider_unreachable` warning in the isolated environment.
- Verification deviation authorized by owner: the final combined `make test` was interrupted
  after collecting 482 backend tests and progressing through `test_export.py`; its frontend stage
  was not reached. The owner explicitly asked to skip the remainder and wrap up. It is recorded as
  **not completed**, not green. The sprint's referenced `test_undo.py` does not exist; unchanged
  undo coverage is distributed across existing suites, principally `test_jobs.py`, which passed
  in the focused 97-test run.
- Blocked/open: none. No tag, push, release, or deployment was requested or performed.
- Next: none scheduled. The numbered plan is complete; the owner may choose a future epic and a
  new plan, or separately authorize release operations.


## 2026-08-21 — Sprint 032 planned (docs-only)
- Done: owner-directed planning session; no implementation. Read the live importer code
  (`domain/importers.py`, `application/imports.py`, `api/imports.py`, both book connectors,
  `ImportPage.tsx`, `TriagePage.tsx`, `AppShell.tsx`, e2e/component fixtures) rather than
  DEC-076/078's summaries. Wrote `docs/sprints/032-import-ux-and-connector-extensibility.md`
  from TEMPLATE.md; extended ROADMAP to plan revision 14 (sprint index, tree, closing
  contract paragraph); state.json -> `ready`/032; FINAL_SPRINT 31 -> 32 in
  `scripts/validate_project.py`; appended DEC-079; rewrote HANDOFF.
- Verified: `python scripts/validate_project.py` (pass), `make check` (green). `make test`
  not run — docs-only session, no application code changed.
- Deviations: none. AGENTS.md §1 permits documentation-only changes when owner-directed.
- Blocked/open: the sprint file's risks section carries four implementation-time decisions
  (`/triage` redirect vs 404 — redirect recommended; browse endpoint returns names only;
  guide as ordered steps vs markdown — steps recommended; default import tab remembers last
  source, mirroring DEC-062).
- Next: claim **Sprint 032** per the normal protocol (state.json + sprint file to
  `in_progress`, TDD the acceptance criteria in listed order).

## 2026-08-21 — Sprint 032 (complete; project complete)
- Done: claimed 032 and executed it end to end. Folded Triage into `/import` as a tab (the
  `TriagePage` component unchanged, only its wrapper), with the tab in the URL, a `/triage`
  redirect, the nav item removed, and the Inbox button plus the post-commit link retargeted.
  Extended the importer contract declaratively: `ImportInputSpec.guide`/`empty_state`/`help_url`/
  `browsable`, `ImportReadError.user_message`/`action`, a required `Importer.error_codes` with
  `declared_read_error` enforcing the closed set at the boundary, and a separate
  `BrowsableImporter` protocol. Added `GET /api/import/{importer}/browse`, confined through the
  new shared `CalibreAdapter.confine` that `read` also uses. Built `ConnectorGuide`,
  `SourceDropZone` and `FolderPicker`; both connectors now publish their own guidance and their
  own actionable error sentences. Rewrote README's importing section, the domain guide's importer
  half, technical spec §6.5/§7.1 and product spec §7; appended DEC-080; impact-reviewed the
  roadmap. Commits: `a0bd8d1`, `711fe65`, `57422c8`, plus the closing commit.
- Verified: `python scripts/validate_project.py` (pass), `make format` (no drift), `make check`
  (green), `make test` (backend 502 passed, frontend 164 passed), `npx playwright test`
  (95 passed, 2 skipped), `git diff --check` (clean). The full `make test` that Sprint 031 left
  waived was run to completion here.
- Walkthrough (the gate, run headless at 1440×900 against an isolated backend on a temporary data
  dir, screenshots at every step, zero console/page errors):
  - **Data.** A synthetic Calibre mount `Estanterías/{Calibre Library (5 books), Comics (1),
    Sin biblioteca (empty)}` with a loose `leeme.txt` beside it, and a 120-row Goodreads export
    with Excel-armoured ISBNs, unrated rows, blank dates and one malformed date.
  - **Exercised.** Nav shows four destinations, no Triage. `/triage` redirected to
    `/import?tab=triage`. The Goodreads tab rendered its five declared steps and the external
    link; the export previewed as 119 ready / 1 with errors (the malformed date, correctly) and
    committed 119 entries. The post-commit link landed on the Triage tab inside the Import screen;
    the inbox read "Inbox 119 unsorted"; `j` then `r` set a status on the focused row; "Accept all
    suggested" cleared 118 and emptied the inbox. The Calibre tab listed the mount root
    (`Estanterías` only — the loose file was correctly absent), walked one level down to the three
    folders, and on selecting `Calibre Library` said "This folder holds a Calibre library" and
    filled the path field; preview read 5 rows, commit landed them, undo inside the window reverted
    10 changes. Previewing `Sin biblioteca` produced the connector's own refusal: "No Calibre
    library sits at that folder. Choose the folder that contains metadata.db — usually the one
    Calibre calls your Calibre Library."
  - **Observed and fixed, all three invisible to tests.** (a) After the Goodreads commit, the
    Calibre tab rendered the Goodreads result and no Calibre form: the tab strip is now visible
    during a preview, and staged state was global. A staged source now belongs to its connector,
    and a trip through Triage does not discard it. (b) The picker printed "No Calibre library in
    this folder — open one below" directly above "No folders here", which contradict each other in
    an empty leaf folder; it is one derived sentence now, and the connector's `empty_state` renders
    only at the mount root, where "your library is not mounted" is the true reading. (c) The
    triage tab carried a second "← Library" beside the one the triage surface already has;
    removed.
  - **Observed and left.** The picker fires its listing request twice on mount in dev, which is
    React StrictMode double-invoking the effect and does not happen in a production build; the
    e2e assertion is written not to depend on the sequence. Nothing else looked wrong.
- Deviations: four, all in DEC-080 and the sprint Outcome — `browsable`/`BrowsableImporter` beyond
  the three planned fields; `error_codes` promoted from convention to required contract member;
  guide-as-ordered-steps and the `/triage` redirect (both the sprint's recommended options); and
  the connector-scoped preview found by the walkthrough.
- Blocked/open: none. No tag, push, release or deployment was requested or performed.
- Next: none scheduled. The numbered plan is complete through 032. The unnumbered epics (Games/
  IGDB, Series/TMDB, Music/Spotify, Steam) inherit the extended contract; the first thing Spotify
  will hit is that `ImportInputSpec.kind` is still `upload | path` and an OAuth handshake is
  neither.

## 2026-08-21 — Sprint 033 planned (docs-only)
- Done: owner-directed planning session after they used 032's picker against a real library. The
  complaint was the mount, not the picker: `CALIBRE_DIR` is container-level so re-aiming it needs
  an `.env` edit plus a restart, and the NAS library is held open by calibre-web-automated.
  Established by measurement rather than argument — nothing in the codebase syncs Calibre
  automatically (there is no scheduler at all; the mount is read only by `browse` and `read`, both
  user-triggered), so the mount buys file access at one instant, and what it really buys is
  covers. Measured both libraries: `/home/ibz/Calibre Library` = 2 books / 416 KB db / 3
  `cover.jpg` of which one is `.caltrash` trash / 32 MB total; the NAS one = 21 books / 448 KB /
  8.2 MB covers / 95 MB / 19% ISBN coverage. The ISBN number killed the cheap option
  (upload `metadata.db` alone → enrichment refills 4 of 21 covers, 17 stay blank). Probed
  `<input webkitdirectory>` in Chromium via Playwright before committing to the design: it is
  driveable from tests with a real directory path, `webkitRelativePath` is populated, its first
  segment is the picked folder's own name, and hidden dirs and ebooks are both in the file list.
  Wrote `docs/sprints/033-calibre-without-a-mount.md` from TEMPLATE.md; ROADMAP to revision 15;
  state.json -> `ready`/033; FINAL_SPRINT 32 -> 33; appended DEC-081.
- Verified: `python scripts/validate_project.py` (pass). `make test` not run — docs-only session,
  no application code changed.
- Deviations: none. AGENTS.md §1 permits documentation-only changes when owner-directed.
- Owner decision taken during planning: the mount is **kept**, as secondary affordances beneath
  the folder chooser on the same Calibre tab, rather than deleted or split into a second tab.
  That is what forces `ImportInputSpec.alternate` — one connector, two ways in.
- Blocked/open: the sprint's risks section carries one that needs evidence during implementation —
  whether Starlette's multipart handling can stream parts at the granularity AC5 requires, or
  whether the honest answer is a lower declared `max_bytes`.
- Next: execute **Sprint 033** per the normal protocol.

## 2026-08-21 — Sprint 033 (complete; project complete)
- Done: claimed and executed 033. Extended `ImportInputSpec` with `kind="directory"`, a one-deep
  `alternate`, `accepts_files`, and per-input `max_bytes`/`max_files`; `ImportSource` with
  `directory`. Added the streaming bundle branch to `_source` (validating every client-supplied
  member path before writing), made `_chosen_input` pick between a connector's two inputs by
  content type, and taught the browse endpoint to consult the alternate. Calibre now leads with a
  folder chooser and keeps the mount picker plus typed path as its alternate. Frontend: a pure
  `bundle.ts` filter, `DirectoryPicker.tsx`, and a controlled disclosure for the alternate.
  Docs across README, the domain guide, technical spec §6.5/§7.1 and product spec §5.2/§7.
  Commits: `1f5ad81`, `a0ea09b`, `18105c4`, plus closing.
- Verified: validator (pass), `make format` (no drift), `make check` (green), `make test`
  (backend 522, frontend 171), `npx playwright test` (96 passed, 2 skipped), `git diff --check`.
- Evidence gathered before designing, which changed the design twice:
  - Nothing syncs Calibre automatically — there is no scheduler in the codebase at all — so the
    mount buys file access at one instant, and what it really buys is covers.
  - Only 19% of the NAS library carries an ISBN, so "upload metadata.db alone and let enrichment
    refill covers" would have left most books blank. That killed the cheap option.
  - `.caltrash/b/1/cover.jpg` is a deleted book's cover, so the filter cannot be a `cover.jpg`
    glob; and `webkitRelativePath` prefixes the picked folder's own name, so the leading segment
    must be stripped. Both found by looking at real files.
  - Starlette spools a part to disk only past 1 MiB and covers are smaller, so `request.form()`
    would hold a whole library in memory. `SpooledTemporaryFile(max_size=0)` means *never roll*,
    not "roll immediately" — 1 is the value that works. Measured after: 60 MiB bundle, 1.8 MiB peak.
- Walkthrough (both arms, headless at 1440x950, isolated backend and temp data dir, screenshots):
  - **No mount.** `CALIBRE_DIR` pointed at an empty directory; the alternate correctly said "No
    Calibre library is mounted." Chose `/home/ibz/Calibre Library` in the browser: 71 files offered,
    2 sent (metadata.db + 18 covers, 10.0 MB), 52 left behind. Preview 18 ready / 0 errors, all 18
    covers staged, committed, landed in Triage as 18 unsorted. Re-imported the same folder: the
    fingerprint returned the same batch rather than a second copy (verified in the DB: one batch,
    18 items, 18 entries), and undo reverted 36 effects leaving 0 items and 0 entries.
  - **With a mount.** Restarted against a mount holding the same library: the alternate browsed to
    `Estantería/Calibre Library`, confirmed it held a library, previewed 18 rows, staged 18 covers.
  - No console errors or page errors in either arm.
- Observed and left, none blocking:
  - The native file input renders "71 files" beside a summary saying 2 will be sent. The summary
    directly below corrects it, and hiding the input would cost the keyboard and assistive path.
  - The connector guide sits above both affordances and its first step is written for the folder
    flow, so it reads slightly off when the reader is using the mount. Steps 2-5 apply to both and
    the alternate carries its own help line.
  - A fingerprint replay reports "18 entries added" when it added nothing — pre-existing behavior
    from the replay returning the prior batch's summary, not a 033 regression. Worth a copy fix if
    anyone touches that panel.
  - My first cover check read 7/18 decoded; that was the script measuring before images finished
    loading. Re-checked properly: 18/18 decode, no failed cover responses.
- Deviations: four, in the sprint Outcome and DEC-081. The material one is that `ImportSource`
  carries a bundle directory rather than `Mapping[str, bytes]` — the planned shape contradicted
  the plan's own memory bound, and the plan text was corrected in place.
- Blocked/open: none. No tag, push, release or deployment was requested or performed.
- Next: none scheduled. The numbered plan is complete through 033.

## 2026-08-21 — Sprint 034 planned (docs-only)
- Done: owner-directed planning session, prompted by their question about 033's result — is it
  reasonable to drag a 600 MB folder into a browser on every sync? Established that it is not, and
  why: content-addressing dedupes storage but not transfer, so an unchanged re-sync still uploads
  10.0 MB of covers today and would upload 163 MB once ebooks are attachable. Measured the obvious
  fix out of the running: `crypto.subtle` needs a secure context, and Chromium reports
  `isSecureContext=true` with `crypto.subtle.digest` present on `http://localhost:8000` and
  `http://127.0.0.1:8000` but `isSecureContext=false` with `crypto.subtle` **undefined** on
  `http://books.home.lan`, which is the reverse-proxied deployment the runbook describes — so a
  digest negotiation would work from the box and fail silently from the rest of the LAN. Wrote
  `docs/sprints/034-incremental-import.md` from TEMPLATE.md; ROADMAP to revision 16; state.json ->
  `ready`/034; FINAL_SPRINT 33 -> 34; appended DEC-082.
- Verified: `python scripts/validate_project.py` (pass). No `make test` — docs-only session.
- Owner decisions taken during planning: (a) attaching files is a feature of the **importer**;
  Akasha's own file UI stays simple and file-type agnostic rather than growing toward an ebook
  manager, which settles the product-spec §1 tension raised earlier without amending the non-goal;
  (b) ebook attachments come **after** incremental sync, since shipping them first would mean
  163 MB on every sync.
- Blocked/open: three implementation-time risks are recorded in the sprint file — `metadata.db` is
  uploaded twice (stated, not engineered around); a changed file under an unchanged identity is
  not detected, with "an item without a cover is always wanted" as the escape hatch; and the plan
  must degrade to a full upload rather than fail closed.
- Next: execute **Sprint 034**, then plan 035 (ebook attachments on a toggle).

## 2026-08-21 — Sprint 034 (complete; project complete)
- Done: claimed and executed 034. Added `ImportCandidate`, `ImportPlan`, `ImportInventory`,
  `IncrementalImporter`, `planned_upload` and `ImportInputSpec.incremental`; implemented the
  inventory on `DomainRepository` (two batched questions, chunked at 500); added
  `POST /api/import/{importer}/plan` reusing `_bundle`'s streaming and `_bundle_member`'s
  validation; taught `CalibreImporter` to plan by `calibre_uuid`; made the client plan before it
  previews, with a fallback that sends everything. Docs across README, the domain guide, technical
  spec §6.5/§7.1 and product spec §5.2. Commits: `fce12fe`, `8fcb0fc`, `1d0e027`, plus closing.
- Verified: validator (pass), `make format` (no drift), `make check` (green), `make test`
  (backend 531, frontend 176), `npx playwright test` (97 passed, 2 skipped at `--workers=1`),
  `git diff --check`.
- Walkthrough (four phases, isolated backend, clean data dir, the owner's real library copied so
  it could be modified mid-run):
  1. first import — 10.55 MB on the wire, 18 rows, nothing skipped
  2. unchanged re-sync — 0.99 MB, 18 skipped ("18 already in your library with a cover")
  3. one book added to metadata.db plus its cover — 0.99 MB, 19 rows previewed, 18 skipped, so
     only the new cover travelled
  4. plan route aborted — 10.06 MB, "Could not check what is already imported, so everything was
     sent", and the import still completed
  No console errors or page errors in any phase.
- Measurement dead end worth not repeating: **Playwright reports a large multipart body as zero
  bytes.** Both `request.postDataBuffer()` and `request.sizes().requestBodySize` returned 0 for a
  10 MB upload, and two walkthrough attempts produced "0.00 MB -> 0.00 MB" that looked like a
  perfect saving and measured nothing. The third attempt put a counting TCP proxy between the dev
  server and the backend (`scratchpad/w34/counter.mjs`) and produced the real figures above. If a
  future sprint needs upload sizes, start there.
- Observed and left: an unchanged re-sync shows "Local cover staged" on all rows despite uploading
  no covers. Correct rather than wrong — the fingerprint of an unchanged `metadata.db` matches, so
  Sprint 031's replay returns the stored batch, which did stage them. Recorded because it looks
  like a bug until you know why.
- Also observed: two heavy specs in `library.spec.ts` (the 10,000-row DOM budget and the keyboard
  guards) fail intermittently under parallel workers and pass alone; which of the two fails varies
  per run, and `--workers=1` is green. Load sensitivity in assertions that guard real invariants
  (offset stability, DOM budget), not a regression from this sprint, and not worth loosening.
- Deviations: three small ones in the sprint Outcome — `ImportSource.manifest` and
  `_bundle(form_extras=)` so the plan route reuses one streaming implementation, and keeping
  `book_path` on the reader payload because the planner needs it.
- Blocked/open: none. No tag, push, release or deployment was requested or performed.
- Next: **Sprint 035 — ebook attachments on a toggle**, which this sprint exists to make
  affordable. It still needs a sixth `attachment` entity type in the undo ledger, a decision on
  `.epub` vs `.azw3` where a book has both (14 of the owner's do), and skip-and-report above the
  25 MiB attachment cap.

## 2026-08-21 — Sprint 035 planned (ebook attachments on a toggle)

- Planning session only. No product code was touched and no sprint was executed.
- Question asked was whether the feature makes sense and is viable, so the assessment came before
  the plan and is recorded in DEC-083 rather than only in the sprint file.
- Measured rather than assumed, on `/home/ibz/Calibre Library`: 174 MB total — 18 books, 18 epub
  (95.4 MB, mean 5.3 MB, **max 14.8 MB**), 14 azw3 (67.4 MB, max 15.3 MB), 18 covers (9.6 MB),
  `metadata.db` 0.5 MB. **Zero files exceed the 25 MiB attachment cap**, so skip-and-report is built
  for correctness rather than for this corpus. `du -sh data` is 2.6 MB today, of which
  `data/attachments` is 1.5 MB.
- Read fresh before deciding anything: `application/undo.py` in full, `infrastructure/attachments.py`,
  `backup.py` (`_share_attachments`), `reclaim.py`, `api/imports.py` (`_bundle_member`, `_bundle`,
  `_candidates`, `plan`), `application/imports.py`, `domains/book/calibre.py`, `bundle.ts`.
- Three findings shaped the plan and none of them came from the previous handoff:
  1. `UndoService` **retains any item that has an attachment** (DEC-047). An import that attaches
     files therefore makes every imported book permanently un-undoable unless the ledger can tell an
     imported file from a hand-uploaded one. That is the sprint's real work, not the upload.
  2. `_bundle_member` hardcodes the Calibre bundle shape in a **shared** route, down to naming
     Calibre in its refusal. Widening it for ebooks forces that to become connector-declared, which
     the domain-contract invariant wanted anyway.
  3. The bundle route's ceiling is **per request** (`max_bytes` 256 MiB), so folding ebooks into the
     preview bundle would cap the feature at roughly forty books. One request per file after commit
     removes the ceiling, bounds every request by the attachment cap, and makes skip-and-report and
     progress fall out instead of being built.
- Written: `docs/sprints/035-ebook-attachments.md`, DEC-083, ROADMAP to revision 17 (tree, table,
  contract section), `state.json` to `ready`/035, `FINAL_SPRINT` 34 → 35.
- Verified: `python scripts/validate_project.py` passed.
- Blocked/open: nothing blocking. Two things the owner should see before execution starts — the disk
  curve (95 MB here, ~3.2 GB for 600 books, backups at ~1.0 effective copies only while `BACKUP_DIR`
  shares a filesystem with the data directory) and the honest scope of the value, since
  calibre-web-automated already holds and reads these files.
- Next: execute Sprint 035 in deliverable order, taking the undo ledger before the toggle.

## 2026-08-21 — Sprint 035 (complete; project complete)
- Done: delivered the connector-declared bundle/source-file/inventory contract (`11b2d42`), the
  committed-batch one-file attachment route (`978a2d5`), attachment-aware undo (`102eeb2`), the
  off-by-default ebook toggle with preferred-file selection, cap reporting, sequential progress and
  named failures (`c1cf940`), and synchronized canonical docs (`3095239`). The optional real-data
  Playwright walkthrough now remains locally in ignored `frontend/e2e/scratchpad/`, parameterized
  by library and isolated-data environment variables, rather than being rebuilt and deleted.
- Verified: project validator passed; `make format` made no product-code changes; `make check`
  passed Ruff, Prettier, ESLint, mypy, TypeScript, OpenAPI and project validation; `make test`
  passed 559 backend and 179 frontend tests; full Playwright at one worker passed 98 with 3 skipped;
  focused `import.spec.ts` passed all 11; `git diff --check` passed. A sandbox-only TestClient futex
  deadlock interrupted an earlier run at the export memory case; the same two cases passed in 3.79s
  and the complete backend suite passed in 59.86s outside that PID/network namespace.
- Walkthrough: ran the UI at 1440px against `/home/ibz/Calibre Library` and a clean isolated backend
  data directory, never live `data/`. The toggle began off; when enabled the summary named 18
  ebooks / 95.4 MB. Commit produced 18 entries, items, attachment rows and blobs, all epubs, and
  exactly 18 post-commit file requests. Downloaded one file from its detail page. An unchanged
  re-sync reported 18 held files and made zero ebook requests. Removed one attachment in detail;
  the next re-sync reported 17 held and requested exactly that one file. Replayed the committed
  batch, used the UI undo, and confirmed 0 entries, 0 items, 0 attachment rows and 0 attachment
  blobs by API/SQLite/filesystem. Isolated disk use was 97 MB populated and 2.3 MB after undo.
- Deviations: no product or architecture deviation from DEC-083. Reusing the ignored walkthrough
  is a local workflow improvement requested by the owner; only the ignore rule is committed.
- Observed and left: `_bundle`'s root `metadata.db` refusal remains connector-specific even though
  member patterns are declared; generalising required files was out of scope. One asynchronous Open
  Library enrichment attempt raced local-cover installation and logged `provider_unreachable`
  after undo; covers and attachments were correct. The successful walkthrough needed two selector
  corrections first: an import-complete regex matched both panel and toast, and an unescaped `(` in
  a filename made a dynamic regex invalid.
- Blocked/open: none. No accounts, keys, payments, irreversible choices, tag, push, deployment or
  release action is needed or was performed.
- Next: none scheduled. The numbered plan is complete through Sprint 035; future work begins by
  planning one of the unnumbered roadmap epics or a remediation sprint.

## 2026-08-21 — Post-Sprint 035 verification protocol optimization (docs-only)
- Done: registered the Sprint 035 testing retrospective as DEC-084 and canonical
  `docs/agent/TESTING.md`; linked it from the documentation map, AGENTS entry sequence and WORKFLOW.
  Amended the binding protocol to run distinct exhaustive gates once after code freeze and to use a
  post-gate diff matrix instead of automatically repeating all product tests after documentation-only
  closure edits. Recorded duration baselines, the Codex sandbox/TestClient deadlock signature,
  walkthrough reuse rules, output discipline and a clearly unimplemented optimization backlog.
- Verified: project validator, `make check`, and `git diff --check` passed. `make test` was not run:
  this owner-directed session changed documentation and agent protocol only; DEC-084's matrix
  requires no product rerun for that class of change.
- Deviations: none. This is the owner-requested protocol change following the completed sprint, not
  a reopened Sprint 035 or a new product sprint; project state remains `complete`.
- Blocked/open: none. The Playwright project split, Vitest warning cleanup, tracked walkthrough
  launcher and bounded phase timeouts remain explicit future work rather than hidden scope growth.
- Next: use the new ladder when the owner schedules the next sprint; if optimizing test
  infrastructure itself is chosen, plan a remediation sprint around the measured backlog.

## 2026-08-21 — Sprint 036 (complete; project complete)

- Done: turned `/import` into two clear workflow steps with source tabs nested under Import
  (`142d422`); made triage row bodies open detail while checkbox clicks alone enter pointer bulk
  selection; added optimistic row-local domain status and score editing (`e7dfe05`); repaired mobile
  row geometry and made short inboxes fit their content (`4e8f151`, `cbdf7e4`); then closed the axe
  suggestion-badge gap and isolated reusable scratchpads from the ordinary browser gate (`87d73cc`).
  README, product and technical specifications, domain guidance, roadmap and decisions now match.
- Verified: focused Vitest passed 31 tests; focused Triage Playwright passed all 16 cases; focused
  Triage axe and production-bundle checks passed 2 each. `make check` passed every static, type,
  generated-contract and project-validation gate. `make test` passed 559 backend and 179 frontend
  tests before the final accessibility-only JSX fix; its affected frontend gate then passed all 179
  again. Full Playwright at one worker passed 101 with 2 intentional skips in 1.6 minutes, and no
  scratchpad specs were collected. Closure validator and `git diff --check` passed.
- Walkthrough: ran against a disposable copy of realistic owner data at 390 px, with four entries
  temporarily made unsorted. Confirmed the `1. Import` / `2. Triage` hierarchy and nested source
  tabs; changed Harry Potter's score 8 -> 7; changed The Shadow of the Wind to `read` and watched
  only it leave the inbox; opened Cien años de soledad from the row body; checked Tokio blues and
  saw the bulk toolbar appear; returned to Import without losing source state. The first visual pass
  exposed a 70vh blank panel under four rows, which was fixed; the repeat showed a fitted list with
  no mobile overflow, console errors or page errors. Live `data/` was untouched.
- Testing retrospective applied: the parameterized runner remains in ignored
  `frontend/e2e/scratchpad/`, but Playwright now excludes that directory by default. Future sessions
  opt in with `BOOK_TRACKER_INCLUDE_SCRATCHPAD=1`, so owner-data walkthroughs are reusable without
  polluting the deterministic gate. DEC-084 remains the canonical record for the freeze-once ladder,
  duration baselines, warning cleanup backlog and sandbox deadlock signature.
- Deviations: native status/score selects replace the planned shared controls because an expanding
  picker clips at a fixed virtual-row edge and a portalled select failed `aria-hidden-focus`.
  DEC-086 records the geometry-specific decision. No backend, API or schema change was needed.
- Observed and left: `_bundle` still has Calibre-specific wording for a missing root `metadata.db`;
  it remains outside this UI sprint. Existing optional-request proxy chatter in Playwright and
  JSDOM warnings in Vitest remain explicit DEC-084 cleanup work, not hidden failures.
- Blocked/open: none. No account, key, payment, irreversible choice, push, tag, deployment or release
  action is needed or was performed.
- Next: none scheduled. The numbered plan is complete through Sprint 036; future product work starts
  by planning a new sprint from an unnumbered roadmap epic or a remediation need.

## 2026-08-21 — Sprint 037 (in progress; implementation frozen)

- Done: opened owner-directed remediation Sprint 037. Triage now window-virtualizes against the
  document instead of keeping a nested 70vh scroller. Row status choices are visible client drafts;
  Apply groups IDs by status through the existing bulk endpoint, Discard sends nothing, partial
  failures retain only failed drafts, and score writes remain immediate. Pending-status and explicit
  bulk controls share one sticky stack rather than overlapping. Commits: `b556b1d`, `8de69ed`.
- Verified before freeze: TypeScript passed. The complete Triage/axe regression passed 20 browser
  cases; focused failure-first coverage passed staging, discard, grouped apply, partial failure,
  window scroll, bounded 200-row DOM, immediate score, combined-toolbar geometry and accessibility.
  Project validation and `git diff --check` passed. No backend/API/schema change exists.
- Walkthrough: used `/tmp/akasha-s37-walkthrough.RbFZRa/data`, a disposable copy of realistic owner
  data with all 16 entries temporarily marked unsorted, at 390x844. The browser window reached the
  final rows with no nested overflow. Two status choices stayed visible and made zero requests;
  Discard restored both. Repeating them plus a Tokio blues score change produced one immediate row
  PATCH, then exactly two status-group bulk PATCHes only after Apply; the two rows left and Inbox
  became 14. The final pass had no console/page error; screenshot:
  `/tmp/akasha-s37-walkthrough.png`. Live `data/` was untouched and the backend was stopped.
- Walkthrough adaptation: two early local assertions were wrong, not product failures. A 16-row real
  list legitimately fit inside virtualization overscan, and after scrolling to the bottom the first
  title was correctly unmounted. The retained ignored Sprint 037 runner now uses the actual final-row
  title and leaves the 200-row DOM bound to the deterministic tracked test.
- Interrupted verification: `make check` and `make test` were started together after freeze, then the
  owner ended the session after 11.6 seconds. The tool returned no usable result and no check/test
  process remains, so neither command counts as run. Full Playwright was not started. Do not close
  Sprint 037 until all three exhaustive gates pass.
- Blocked/open: not blocked; paused at the owner's request. Product implementation and canonical
  README/spec/DEC-087 changes are committed. Only exhaustive verification and normal sprint closure
  documentation/state remain.
- Next: run `make check`, `make test`, then `npm run test:e2e -- --workers=1` once. If green, update
  Sprint 037 Outcome, roadmap, worklog, handoff and state to project-complete, run closure validator
  plus `git diff --check`, and create `docs(sprint-037): close sprint and hand off`.

## 2026-08-22 — Sprint 037 (complete; project complete)

- Done: resumed the frozen Sprint 037 implementation from the verification handoff. No runtime or
  test code changed. Completed the sprint Outcome, marked the roadmap and state complete through
  Sprint 037, and rewrote the handoff as release-state current reality. Implementation commits remain
  `b556b1d` and `8de69ed`.
- Verified: `make check` passed all formatting, lint, type, OpenAPI and project checks. `make test`
  passed 559 backend tests and 179 frontend tests. The isolated run reproduced the documented
  FastAPI `TestClient` stall in `test_export.py`; after stopping that non-counting run, the approved
  outside-sandbox run completed the backend suite in 49.95 seconds. Full Playwright at one worker
  passed 103 cases with 2 intentional skips across 105 cases.
- Walkthrough evidence reused from the immediately preceding frozen implementation session, per
  `docs/agent/TESTING.md`: disposable realistic data at 390x844 proved document scroll, staging and
  no-request discard, immediate score save, two grouped Apply requests, Inbox reduction from 16 to
  14, and no console/page errors. No code changed after that walkthrough.
- Deviations/observations: no product or architecture deviation. Existing Playwright proxy chatter
  from deliberately unstubbed optional requests and Vitest jsdom/Radix warnings remained noisy but
  did not hide failures. The working branch was already `main`, so closure required no feature-branch
  merge commit.
- Next: no numbered sprint remains. New work must be planned explicitly; the roadmap's unnumbered
  epics are not active commitments.

## 2026-08-27 — Plan revision 20: anime as the third domain (planning only)

- Done: planned the anime domain end to end at the owner's request, as an explicit trial run of the
  Sprint 028 domain contract whose findings feed back into the repository. Probed four metadata
  providers live from this host between 16:20 and 17:00 UTC, parsed the owner's real MyAnimeList
  export, wrote DEC-088 and DEC-089, and added Sprints 038–041. Moved `FINAL_SPRINT` to 41, plan
  revision to 20, and reactivated state with 038 `ready`. **No runtime code was written.** Work is on
  the `sprint-038-anime` branch under DEC-053.
- Measured, not reasoned: AniList answered 6/6 searches (0.3–1.5s median, one 40.04s outlier) and
  resolved all 81 of the export's ids in **2 requests / 54 KiB** through `media(idMal_in:)`. Kitsu
  answered 6/6 (3.7s median, one 8.2s), returns the MyAnimeList id on a search row via
  `include=mappings`, and returns studios and categories in the same fetch via
  `include=animeProductions.producer,categories` — correcting an earlier assumption that studios cost
  one request per item. **Jikan returned HTTP 504 to every request across ~40 minutes**: 0/12 on
  search and 1/81 by id, where the single success was a record fetched moments earlier from its own
  cache. `myanimelist.net` answered this host in 0.66s throughout, so MAL was up and Jikan could not
  reach it. AniList returns Cloudflare `error code: 1010` / 403 without a User-Agent. Cover variants
  measured against the pipeline bounds: AniList `extraLarge` 460x635 / 110 KiB, Kitsu `original`
  980x1420 / 1.6 MiB PNG (so `large` is the one to ask for).
- The export: 81 rows, gzipped XML, `series_animedb_id` distinct on every row, `my_status` in
  {Completed 74, Dropped 6, Plan to Watch 1}, `my_score` 0 on 3 rows meaning unrated, `my_start_date`
  `0000-00-00` on all 81 and `my_finish_date` on 76, `my_watched_episodes` diverging from
  `series_episodes` on the partial rows (`Black Clover`, 20 of 170, dropped).
- Two seams found, both foreseen and both unbuilt: **DEC-067 row 3** (enrichment is keyed on the
  literal `'isbn'` below `Domain.enriches`, with a module-constant provider order of two book
  providers) and **DEC-077 shape (a)** (a per-domain progress field, chosen by that verdict and never
  implemented). They are Sprints 039 and 040 rather than folded into the domain or the connector.
  Three smaller findings recorded in the sprint files: `DetailPage.tsx:368` hardcodes `Rereads` as the
  label for `reread_count` in every domain, which is the entry panel's last book-shaped word; the
  conformance suite requires a non-empty `formats` vocabulary, which a domain with no notion of a
  copy would have to invent one for; and the owner's export sat untracked at the repository root
  carrying a user id and username, now gitignored.
- Owner decisions taken at planning time, recorded in DEC-088 and DEC-089: AniList plus Kitsu despite
  AniList's terms naming anime tracker services, with Kitsu kept as the hedge; build progress before
  the import rather than drop the watched-episode counts and re-import; generalize enrichment rather
  than let the connector fetch at read time. One earlier framing of Jikan was corrected to the owner
  mid-planning after the wider measurement contradicted it, and the provider question was re-put.
- Verified: `python scripts/validate_project.py` passed. No product gate applies — nothing outside
  `docs/`, `.gitignore` and the validator's sprint bound changed.
- Next: execute Sprint 038 under the ordinary protocol.

## 2026-08-27 — Sprint 038 (complete)

- Done: built the anime domain from `docs/guides/adding-a-domain.md` alone — package, AniList and
  Kitsu adapters, registration, ten recorded provider responses, and the per-domain passage-field
  labels. Commits `9144daf`, `7165816`, `b2482c8`. Branch `sprint-038-anime`, unpushed.
- Verified: `make check` green. `make test` **616 backend / 183 frontend** (from 559/179 at Sprint 037
  closure). Playwright **103 passed, 2 skipped**, matching the prior baseline. Conformance passed over
  three domains; registering the domain broke no existing backend test on the first run.
- Walkthrough: 5 of 5 in the ignored `frontend/e2e/scratchpad/anime-walkthrough.spec.ts`, at 390x844
  against a disposable `BOOK_TRACKER_DATA_DIR` and the **live** AniList and Kitsu APIs, backend on
  8123 and vite on 5199. Observed: a live `akame ga kill` search returned three rows with the first
  two merged across both providers on `mal:22199`, AniList primary; all four URL forms resolved;
  covers installed from both new hosts (AniList's stored at 425x600 / 74 KiB); `status=read` and
  `formats=["vinyl"]` each refused 422 naming Anime; `reread_count=3` accepted; the detail page read
  `Your watch data` and **`Rewatches: 3`**; the status filter listed all six anime statuses with facet
  counts and no book vocabulary. Live `data/` untouched.
- Four walkthrough assertions failed first and **every one was my selector, not the product**: the
  domain chooser is a `radiogroup` and not tabs (Sprint 029), the status filter is a popover and not
  a select (multi-valued, see `StatusFilter.tsx`), its options carry facet counts, and library row
  controls are popovers where Triage's are native (DEC-086). Worth knowing before writing the next
  walkthrough.
- Three shared changes, all in DEC-090: `bounded_json` gained `method`/`json_body` because GraphQL
  asks by POST; three `provider_health` tests were deriving nothing and enumerating providers, so a
  third domain failed them with no behaviour changing; `Domain` gained `entry_field_labels`.
- Observed and left alone, out of scope: `Episode length: 24` carries no unit on the detail page;
  Kitsu holds no production records at all for some series (Cowboy Bebop), so it arrives with no
  creator where AniList has Sunrise; and conformance requires a non-empty `formats` vocabulary, which
  a domain with no notion of a copy would have to invent one for.
- Next: Sprint 039, enrichment beyond the ISBN. It inherits one fact from this sprint — `bounded_json`
  already takes a method, so a provider reached by POST costs it nothing.

## 2026-08-27 — Sprint 039 (complete)

- Done: generalized background enrichment off the ISBN. `EnrichmentSpec` on the domain contract,
  `EnrichingProvider.fetch_by_identifier` as the interface, a per-domain backfill query, and a handler
  that reads the item's domain instead of assuming books. Commits `c62c559`, `81e110f`, `16e2f20`,
  `eb03114`, `19a3361`. Recorded as DEC-091. Branch `sprint-038-anime`, unpushed.
- **The spec has three parts, not two.** The sprint file's baseline named the ISBN join, the payload
  and `PROVIDER_ORDER` and missed that `_backfillable_items` also judged incompleteness by
  `publisher`/`page_count`/`description`. An anime has none of the three, so every anime would have
  looked incomplete for ever and been re-queued on every backfill — enrichment appearing to work while
  never finishing. DEC-067 row 3's option (b) had named "an incompleteness rule per domain", so the
  gap was in the sprint file rather than the original costing. `completeness_fields` is the third part
  and conformance refuses one naming a field the domain does not declare.
- Verified: `make check` green. `make test` **641 backend / 183 frontend** (from 616/183). Playwright
  **103 passed, 2 skipped**, unchanged. `make check` caught one real thing: the backfill route's
  docstring is its OpenAPI description, so rewording it made the checked-in schema stale.
- Walkthrough on a disposable database at port 8124, live providers. Chainsaw Man added by MAL URL,
  stripped to `{"kind": "TV", "episodes": 12}` with no year and no cover, then backfilled. Job row
  verbatim: `{"item_id": 1, "kind": "mal", "value": "44511"}` → succeeded via `anilist`, filling year,
  creators, english_title, japanese_title, episode_minutes, season, source, genres, airing_status,
  synopsis and cover. `kind` and `episodes` untouched. **A second backfill queued 0**, which is the
  completeness rule doing the job this sprint existed for. A thin book beside it queued
  `{"item_id": 2, "kind": "isbn", "value": "9788437604572"}` and filled from Open Library exactly as
  before. A hand-written job in the **old** `{item_id, isbn}` payload also succeeded. Live `data/`
  untouched.
- Observed, pre-existing, not fixed here: `JobRepository.complete` never clears `error`/`error_code`,
  so a job that failed once and then succeeded on retry shows `succeeded` beside stale failure text.
  Seen live. In DEC-091.
- Criterion 7 stated precisely rather than broadly: the enrichment path names no identifier kind or
  provider, but `grep isbn application/` still hits `export.py` (books' CSV column names), `add.py`
  (the near-match check) and `providers.py` (the cover chooser's Open Library path, kept by DEC-067
  rows 6 and 7). Those are other features with their own decisions.
- Next: Sprint 040, entry progress. It is the only shared-table migration in the line and is
  independent of this sprint; both block Sprint 041.

## 2026-08-27 — Sprint 040 (complete)

- Done: built DEC-077 shape (a) — a per-domain progress count on the flat entry.
  `ProgressSpec` on the contract, `validate_progress` as the fourth validator, migration
  `0015_entry_progress`, API and export, the detail page and opinion dialog, and a Sprint 038
  prerequisite repair. Commits `b17060b`, `e396d46`, `e16a4b3`. DEC-092. Branch
  `sprint-038-anime`, unpushed.
- **The plan's own bounding rule was wrong and the owner overruled it.** The first draft refused a
  count above the item's episode total; AniList returns `episodes: null` for airing shows, a weekly
  total is stale by definition, and a refresh could lower it under a stored count — making a valid
  row invalid on its next write, which is `ck_entries_status`'s mistake again. Bounded below only.
- Verified: `make check` green, `make test` **660 backend / 189 frontend** (from 641/183),
  Playwright **103 passed / 2 skipped**.
- Migration walkthrough on a **copy** of the real database: 16 entries, 19 items, 7 shelf
  memberships, 6 formats — all preserved, `integrity_check ok`, four CHECKs including
  `ck_entries_progress`, six indexes, and all 16 rows `NULL` rather than `0`. Live `data/` was never
  opened for writing and still has no `progress` column.
- Browser walkthrough 4/4 at 390x844 against that copy: `20 / 170 episodes` rendered from the
  declaration plus the item's metadata, an emptied box PATCHes `null`, `"0"` PATCHes `0` and reads
  `0 / 170 episodes`, and a book offers no control and still says "Rereads".
- **Two rebuild traps, both cost failed attempts and are now asserted.** A `copy_from` that already
  spells the new column dies on the row copy — the column must arrive inside the `with` block. And a
  rebuild is a `DROP TABLE`, so under `PRAGMA foreign_keys=ON` it would silently empty
  `entry_shelves` and `entry_formats` via CASCADE and still report success. `alembic/env.py` never
  sets that pragma, unlike `database.py` — load-bearing, undocumented, and already relied on by
  `0013` and `0014`. The test seeds a shelf and a format and checks both survive, and pins the six
  indexes a drifted `copy_from` would drop.
- `0014`'s docstring is wrong that SQLAlchemy cannot reflect SQLite CHECKs — on 2.0 it can.
  `copy_from` is still correct for two other reasons (unnamed CHECKs, and `ON DELETE RESTRICT`
  downgraded), and `0015` states those.
- Review findings folded in: **`AddForm.tsx` was the third render site Sprint 038 missed** and still
  said "Reread count" to an anime — repaired. `test_backup.py` hardcoded the head revision, the third
  instance of that defect class in three sprints. `String(undefined)` from a fixture without the key
  made the opinion form permanently unsaveable; the client tolerates an omitted field now.
- AC7 was untestable as written — there is no JSON importer, so "export and re-import" does not
  exist. Rewritten as: the JSON export carries progress including an explicit null for a book; the
  Goodreads CSV does not.
- Next: Sprint 041, the MyAnimeList import — the last in the line. It writes a watched-episode count
  through `ImportEntry.values`, which all three `EntryRow` constructions now carry.

## 2026-08-27 — Sprint 041 (complete; the anime line closed)

- Done: the MyAnimeList connector, its registration, migration `0016` and two prerequisite
  repairs. Commits `a738828`, `5b55e53`, `0d9b6a3`. DEC-093. Branch `sprint-038-anime`,
  **unpushed and unmerged** — the merge is the owner's call at the line's close (DEC-053).
- **The central criterion, answered precisely.** `api/imports.py`, `ImportPage.tsx` and
  `TriagePage.tsx` were not touched at all; `application/imports.py` changed by eight lines and
  that was the prerequisite repair. What did not hold was the schema: `ck_import_batches_kind` read
  `kind IN ('goodreads','calibre')`, frozen in migration `0002` — `ck_entries_status`'s mistake one
  table over, surviving because no connector had been added since. The first one to try passed
  every application check and failed at commit. `0016` deletes it.
- **A correction to Sprint 040.** Its Outcome and handoff both claimed `validate_progress` ran on
  the import path. It did not — `validate_entry_fields` is a denylist over `PASSAGE_FIELDS`, so
  `progress` passed through unchecked and reached the column unvalidated. Closed here with a test.
- **Seven defects found after the first green run**, by adversarial review, none of them exercised
  by the owner's own file: `series_episodes` of `0` (MyAnimeList's "still airing", which the domain
  refuses with a minimum of 1), a blank title, out-of-range numbers that pass preview and raise an
  IntegrityError mid-commit, a duplicate id counted as `unchanged` with its data discarded, a
  half-known date like `2021-05-00` stored verbatim in a text column, a punctuation-only tag raising
  a 500 out of `shelf_slug`, and a byte-scan DOCTYPE guard with a comment false positive. All
  reproduced before being fixed. `goodreads.py` still shares two of them.
- **Measured rather than assumed:** ElementTree on Python 3.12 expands internal entities, so billion
  laughs is live and expands inside the parser where a decompression cap cannot reach it; external
  entities are already refused. The guard is the parser's own `doctype` callback, so the test that
  it fires is load-bearing. And `ImportInputSpec.max_bytes` is ignored for `kind="upload"` while
  still being published to the client — the connector declares none and bounds its own gunzip at
  8 MiB.
- Verified: `make check` green. `make test` **698 backend / 189 frontend** (from 660/189).
  Playwright **103 passed, 2 skipped**. One browser run reported 102 with no failure text and exit
  code 0; the immediate re-run gave 103, matching every earlier run. Recorded rather than smoothed.
- Walkthrough on a disposable directory with the owner's real gitignored export: 81 records
  previewed with zero row errors and every measured count matching, 81 items and 81 `unsorted`
  entries committed, Triage reading `Inbox 81 unsorted` in anime's own vocabulary, `Black Clover`
  at 20 of 170, all 81 enriched from AniList with covers and studios, a re-upload replaying rather
  than importing twice, and undo reversing a new batch completely. Live `data/` never opened for
  writing — still 16 entries, no anime, no `progress` column.
- Next: nothing numbered. The plan is complete through 041 and `state.json` is `complete`. The
  branch holds four sprints and is the owner's to merge.

## 2026-08-27 — Plan revision 21: Sprint 042 planned, not started

- Done: retrospective on the anime line at the owner's request, written up as **DEC-094**,
  and **Sprint 042 planned**. `FINAL_SPRINT` moves to 42 and state reactivates from
  `complete` to `ready` with 042 active. **No implementation.** The owner has a UX fix to
  do first and asked for the plan committed unexecuted.
- The finding, which is not the one that was expected: **the abstraction held; the friction
  was mechanical.** Ranked by time actually lost — walkthrough selector churn (every
  walkthrough needed 2-4 corrections and the assumption was wrong every time, never the
  product), the `entries` rebuild recipe (three failed attempts in 040), the
  `validate_entry_fields` denylist (root cause of `progress` reaching storage unvalidated
  for a sprint), the missing conformance wiring tier, three entry-field render sites, and
  three hand-enumerated `EntryRow` constructions.
- Verified while writing it rather than recalled: `alembic/env.py` still says nothing about
  the `PRAGMA foreign_keys` silence three migrations depend on; `EntryRow` is constructed
  at `repositories.py:256,382,774`; `validate_entry_fields` is called from three sites and
  its return value is discarded at two of them; conformance has exactly two tiers; and no
  live CHECK constraint enumerates an application-owned vocabulary (both offenders gone,
  nothing keeping it that way).
- Deferred deliberately and recorded in DEC-094: the shared frontend hook for the three
  entry-field render sites (a refactor with its own risk, and 040 already repaired its one
  real consequence), the OAuth seam IGDB will need, and a generalised cover chooser.
- Stated caveat: this is a sample of one domain, and an unusual one. Games would exercise
  authentication with a lifetime and would likely surface a different list. Weighed and
  rejected in favour of proceeding, because deliverables 1-3 record mistakes already made
  rather than predictions.
- Branch: still `sprint-038-anime`, unpushed and **unmerged**. Sprint 042 depends on the
  anime line's code, which is not on `main`, so it continues there unless the owner merges
  first.
- Next: the owner's UX fix, then execute Sprint 042.

## 2026-08-27 — Sprint 042 (complete; one decision per Triage row)

- Done: inserted and completed the owner-directed Triage correction ahead of the already-planned
  domain-contract sprint. Commit `c99aa23`. A row now displays explicit draft → importer suggestion
  → domain default, offers only choosable statuses, has no duplicate suggestion chip, and applies
  its displayed target from a check action at the row's right. Applying one row preserves unrelated
  drafts; failure retains the attempted target for retry. DEC-095. Sprint 043 is ready.
- TDD: the new real-flow browser case first failed because anime displayed `unsorted` rather than
  `completed`. A second assertion exposed that the first row-Apply implementation cleared an
  unrelated book draft; the mutation now clears only IDs it attempted. Focused Triage/accessibility:
  **36 passed**.
- Verified after implementation freeze: `make check` passed; `make test` passed **698 backend / 189
  frontend**; full Playwright **105 passed / 2 skipped**. The first sandboxed `make test` advanced to
  `test_export.py` and stopped with the documented TestClient signature; it was interrupted and the
  prescribed outside-sandbox run passed 698 in 57.58 seconds. The first `make check` found only an
  unformatted ignored walkthrough file; formatting it made the exact gate pass.
- Walkthrough: fresh disposable data at `/tmp/akasha-s42-visual.v4vaHl`, 390×844. Imported the
  owner's real 81-row MyAnimeList export and 18-book Calibre library through the UI: 99 unsorted.
  `Akame ga Kill!` displayed Completed from its suggestion with no Inbox option or duplicate chip;
  row Apply removed it. `Proyecto Hail Mary` displayed Read from the book default; changing it made
  no request, Discard restored Read, and row Apply removed it. `Black Clover` changed from Dropped
  to Watching and left only on page-level Apply. Exactly three status bulk requests occurred, no
  row overflow at mobile width, and no console/page errors. Live `data/` was never opened for
  writing. Background AniList requests succeeded while the disposable app was running.
- Observed and left out of scope: with a search whose only matching row has just left, Triage says
  `Inbox is clear` although unfiltered rows remain; and `Accept all suggested` stays visible on a
  Calibre-only filtered result with no suggestion, where it would affect zero rows. Both pre-date
  this sprint and belong to a later filtered-state/copy correction.
- Deviations: no product or architecture deviation. The prior `1466208` rename had made room for
  Sprint 042 but left state, roadmap, validator and the new sprint file inconsistent; the intended
  owner-directed repair was unambiguous and was completed before implementation.
- Next: Sprint 043, sharpening the domain contract. Its scope is unchanged from DEC-094 and has no
  user-visible behavior or walkthrough gate.

## 2026-08-27 — Sprint 043 complete; v1.3 release gates green

- Done: completed the owner's final Triage pass in `bb474c7`. The check is icon-only and visually
  quiet, the redundant staged-status toolbar is gone, and row targets persist in tab-scoped session
  storage across navigation and refresh. Successful commits clear their drafts and failures retain
  them. Explicit checkbox bulk actions are unchanged. DEC-096.
- TDD/focused evidence: the navigation/reload case failed before persistence was implemented; 20
  Triage browser tests, 3 Triage accessibility tests and frontend type checking then passed.
- Walkthrough: disposable data with the owner's real 81-row MyAnimeList export plus 18-book Calibre
  library at 390×844. A book target survived Library navigation and refresh and then committed; an
  anime suggestion and an overridden anime target each committed from their own row. No console or
  page errors; live data untouched.
- Release freeze evidence for v1.3.0: `make check` passed; `make test` passed 698 backend / 189
  frontend; full Playwright passed 106 / 2 intentionally skipped; `make build` passed; container
  smoke passed health, non-root/no-Node, API persistence, assets/deep links, read-only Calibre,
  backup/restore, named-volume recreation and graceful shutdown.
- The first container smoke run found its own stale manual add payload (`authors`, no `item_type`),
  not a product failure. The harness now sends the current domain-neutral shape; the rerun passed,
  followed by fresh `make check` and `make test` because test configuration changed.
- Release preparation updates README coverage for anime and MyAnimeList, synchronizes all version
  surfaces at 1.3.0, adds release notes, and refreshes the generated OpenAPI contract. Merge, tag and
  push remain the next authorized release actions.
- Next: merge/tag/push v1.3.0, then execute Sprint 044. The owner's root Letterboxd archive is
  private feasibility input for the subsequent movies line and remains uncommitted.

## 2026-08-27 — Sprint 044 complete; domain-addition QOL gates green

- Done in five implementation commits: all entry write paths share an allowlisting validator;
  conformance has a built-application wiring tier; the live schema is guarded against frozen
  application vocabularies; `EntryRow` has one constructor; and the migration/UI-driving recipes
  that cost the anime line time are documented. DEC-097.
- TDD evidence: each slice first failed at its intended boundary. The expanded focused suite passed
  **265 tests**. `make openapi` generated no diff, `make check` passed, full backend passed **710**,
  full frontend passed **189**, and Playwright passed **106 with 2 intentional skips**.
- Deviation: the sprint baseline said the live head had no string-valued CHECK. Inspection found
  `jobs.ck_jobs_state`, which is a schema-owned durable state machine rather than an extensible
  registry vocabulary. The guard allows that one named constraint and an in-test temporary table
  proved it rejects the class the sprint intended.
- Environment note: one combined backend run in the filesystem sandbox hit the already-documented
  TestClient deadlock after 227 tests; the same suite outside it passed. After the owner questioned
  the time spent on an already-working container, no container/build rerun was done: this sprint was
  nonvisual and did not touch deployment behavior.
- No walkthrough by contract, no migration, no API change and no screen change. Post-gate closure
  is documentation/state only and was checked with the validator and `git diff --check`.
- Next: Sprint 045 on a separate movies branch. Measure current providers and the private
  Letterboxd ZIP, then plan movie domain/provider and Letterboxd importer sprints in that order.

## 2026-08-27 — Sprint 045 complete; movies/provider gate measured

- Done: created `sprint-045-movies`, measured providers and the private Letterboxd export, recorded
  DEC-098, and planned Sprint 046 (movie domain/Wikidata) followed by Sprint 047 (Letterboxd import).
  No runtime code, dependency, migration, generated contract or deployment configuration changed.
- Live provider evidence: TMDB and OMDb both returned 401 without a configured key; neither record
  payload is claimed as tested. TMDB's current six-month cache term is incompatible with Akasha's
  provenance-free permanent owner-editable cache. Wikidata film-filtered search found all four
  representative query classes; five fetched entities carried the structured claim set and all 41
  linked values had Spanish/English labels. Exact IMDb, TMDB and Letterboxd claims converged on one
  film. Image coverage was 1/5 and not poster art, so launch is intentionally coverless.
- Private sample evidence: ZIP read in place, 16 CSV files / 1,022 uncompressed bytes; two distinct
  watched rows and the same two rated rows; all other live film tables empty; dates ISO and ratings
  valid half-steps. No personal value was copied to docs, fixtures or logs. One source URI was
  followed without printing it: GET and HEAD each made one redirect to HTTPS `/film/<slug>/`.
- Plan: Sprint 046 supplies a recorded-response Wikidata provider, exact external-id/URL resolution,
  Movie declarations and Letterboxd-keyed enrichment. Sprint 047 supplies bounded ZIP parsing,
  aggregation/mapping, a neutral title+year ambiguity and the real Import → Triage walkthrough.
- Verified only the sprint's documentation gate: `python scripts/validate_project.py` and
  `git diff --check`. No application/frontend/Playwright/build/container rerun by explicit sprint
  contract and in response to the owner's request to stop debugging an unrelated working container.
- Next: Sprint 046 is ready on this branch. No owner key/account/payment is needed for Wikidata.
  The private ZIP remains untracked for Sprint 047 walkthrough only.

## 2026-08-27 — Sprint 046 complete; movies ship as the fourth domain

- Done in three implementation commits: the movie declaration (`6e53952`), the recorded Wikidata
  adapter with its registration (`1cd443e`), and exact identity resolution plus enrichment
  (`20fda58`). DEC-099 and DEC-100.
- Validated the two new sprint plans against the code before starting. Everything Sprint 046 assumed
  held; three things did not, and all three are now recorded rather than discovered later.
- **Measured before building, and it changed the design.** `wbgetentities` with claims costs ~113 KB
  for one film, up to 1.15 MB for five and **1.9 MB for ten**, against `MAX_PROVIDER_BYTES` of
  2 MiB. A twenty-result search is unreadable through the shared boundary. Search is now six
  candidates, entities three at a time, one label batch: measured 1.6 s for one result and 2.8 s for
  the six-result `Metropolis` query through the running app, inside the five-second search budget.
- **The rank traps the plan predicted are real and are now pinned by fixtures.** `Q546900` lists
  four original languages with the preferred one third, so a first-value parser calls Dario Argento's
  film German. `Q151599` opens with a deprecated country and a `somevalue` language. `P577` arrives
  up to thirty times per film at mixed precision including `+1977-03-00T00:00:00Z`, which is day
  zero and unparseable as a date.
- **A `haswbstatement` hit is not proof of the claim.** `P345=tt0000000` returns a real film, because
  that entity genuinely carries the placeholder id. The adapter now re-checks the value on the
  fetched entity. Found while recording a zero-hit fixture; the fixture was re-recorded against a
  value that truly matches nothing.
- Nineteen fixtures recorded live today (~940 KB), one of them synthetic and labelled as such, with
  a README row each. The only shared test change is `recordings.py:replay` gaining an optional route
  key, because Wikidata answers search, entity and label reads at one path.
- TDD evidence: each slice first failed at its intended boundary — the declaration on a missing
  module, the adapter on a missing module then on eighteen behavioural assertions, enrichment on a
  handler that queued nothing for a `letterboxd` key.
- Gates: focused suite **239**; `make openapi` then `make check` clean; `make test` **818 backend /
  189 frontend**; Playwright **106 passed, 2 intentional skips**.
- Walkthrough: `frontend/e2e/scratchpad/movie-walkthrough.spec.ts`, **12 passed** at 390×844 against
  a disposable `BOOK_TRACKER_DATA_DIR` and the **live** Wikidata API, launched with
  `BOOK_TRACKER_DATA_DIR=/tmp/akasha-movie-walkthrough USER_AGENT_CONTACT=<contact> uv run uvicorn
  book_tracker.main:app --host 127.0.0.1 --port 8100` and
  `BOOK_TRACKER_INCLUDE_SCRATCHPAD=1 BOOK_TRACKER_E2E_BACKEND=http://127.0.0.1:8100`. Added the
  Argentine film, the 1927 film and Suspiria 1977 through the real add box. Verified Spanish labels
  (`Metrópolis`, `El secreto de sus ojos`), Juan José Campanella as the credit, runtimes 129/153/94,
  countries, genres, cast, `Your viewing data`, Rewatches with no Started and no Rereads, the exact
  identities on Detail, default Watchlist, a status change to Watched, the four declared formats
  with `dvd` applied while the film stayed on the Watchlist, status filtering, and a pasted IMDb
  link resolving to Suspiria 1977. Final library: 3 films, facets `{watched: 1, watchlist: 2}` and
  `{dvd: 1}`, all three `cover_url: null`. Provider health lists `wikidata` available; `degraded` is
  true only for the long-standing missing Google Books key. No 500s and no unexplained console or
  page errors.
- Observed and left out of scope, all three recorded in DEC-100 and the sprint Outcome:
  `_backfillable_items` counts a null cover as incomplete in every domain regardless of
  `completeness_fields`, so the explicit backfill route will re-queue every (deliberately coverless)
  movie forever; `GET /api/search/resolve` reports a typed `record_not_found` as HTTP 502
  `provider_failure`, so a link to a film that does not exist tells the reader the provider failed;
  and Triage could not be exercised with a movie row at all, because nothing yet produces an
  unsorted film and the domain chooser is absent from Triage while the inbox is empty.
- Deviations: one, and it is the search-shape bound above. No product or architecture deviation, no
  migration, no screen change, no credential, no container work.
- Next: Sprint 047, the Letterboxd importer. Its plan now carries the two constraints this sprint
  found for it — scope the title+year suggestion to the target domain, and store the export's URI as
  it comes because the adapter already accepts all three Letterboxd shapes.

## 2026-08-28 — Sprint 047 complete; the plan is finished, at a reduced gate

- Done in one implementation commit, `a076f0c`: the bounded Letterboxd ZIP reader, the five-table
  aggregation and mapping, the archive-safety checks, and the scoped title+year matcher seam.
  DEC-101 and DEC-102.
- **The owner directed this sprint to skip the in-depth testing pass**, observing it had been taking
  about two thirds of a sprint. That instruction sits above the protocol in the authority order, so
  it was followed and the trade is recorded rather than argued (DEC-102).
- What ran: `test_letterboxd_import.py` **61 passed**; conformance plus every other importer suite
  **239 passed**, which is what proves Goodreads, Calibre and MyAnimeList are untouched by the
  matcher change; `make check` clean; `make openapi` no diff; full suites **880 backend / 189
  frontend**.
- Real-data pass against the owner's own archive on a disposable data directory, through the running
  application: preview returned the measured two unique films with exactly doubled scores and both
  suggesting Watched, zero row errors; commit created 2 items and 2 unsorted entries; **both Wikidata
  enrichment jobs succeeded**, resolving each `boxd.it` short URI by HEAD and filling directors,
  runtime and Spanish genres; both films appeared as ordinary unsorted Triage rows, which is the
  first time any movie has reached Triage; re-uploading the identical archive returned
  `state: committed` rather than duplicating. The archive is byte-identical at 2,908 bytes and still
  untracked. No title, URI, rating or review from it is in the repository.
- **What did not run, and is not evidence:** Playwright; the walkthrough gate through the real
  screens; frontend tests for the new connector declaration. Nobody has seen the Letterboxd connector
  rendered on the Import page or approved a movie row from the Triage UI, and **undo has no coverage
  at any level in this sprint**. The risky logic — archive handling, the mapping matrix, the matcher
  scope, enrichment — is covered; the screen is not.
- The matcher change is the only shared behaviour change and it is deliberately narrow: title plus
  *exact* year, scoped to one item type, offered and never merged. The scope is the load-bearing
  part — `DomainRepository.match` scanned every row regardless of type, so without it a film diary
  would have offered to merge films into books.
- Deviations: none in product or architecture. No migration, no new route, no OpenAPI change, no
  screen change, no credential.
- Next: **the plan is finished.** Sprint 047 was the final planned sprint, so project state is
  `complete` with null active fields. Nothing is tagged, released or pushed. The obvious next pieces
  of work are the two defects DEC-100 recorded, the untested UI surface DEC-102 names, and a v1.4
  release for the movie line if the owner wants one.

## 2026-08-28 — Sprint 048 complete; v1.4.0 prepared

- Done in one implementation commit, `beb4427`: movie posters from Stremio's keyless image service,
  with TMDB as a narrow fallback. DEC-103.
- The trigger was the owner's own report: the Letterboxd import worked and every film was a blank
  tile. Sprint 046's gate had passed while producing exactly that, because it asserted `cover_url`
  was null *on purpose* and nobody looked at a screen. The lesson is in this sprint's verification.
- Measured live before writing code: Stremio answered **14 of 14** films on a deliberately hard
  sample (Argentine cinema, `Sátántangó`, `Tokyo Story`, `Cure`, `La flor`); its URL is
  **deterministic from the IMDb id** so a poster costs zero requests; a miss is a clean **404**, not
  a placeholder; `medium` is 500×750, inside the existing cover bounds; and **49 of 50** films
  carrying a TMDB id also carry an IMDb id, which is what reduced TMDB to a ~2% fallback.
- Also measured and worth keeping: Wikidata's own `P3383` film-poster property was present on **one
  of eight** sampled films, and that one is a 1927 lithograph that is public domain by age. There is
  no permissively-licensed poster archive because posters are copyrighted; the choice was never
  "free or paid" but "whose terms".
- Gates: `test_movie_posters.py` **22**; `test_wikidata_provider.py` **60**; `make check` clean;
  `make openapi` no diff beyond the version; full suites **903 backend / 189 frontend**;
  `make build` produced the 1.4.0 wheel and the frontend bundle.
- **Verified on a screen**, which is the point of this sprint: the owner's archive re-imported on a
  disposable data directory with the real configuration; both enrichment jobs succeeded; both films
  installed a 400×600 JPEG; each image was opened and confirmed to be that film's real poster art;
  and `frontend/e2e/scratchpad/movie-posters.spec.ts` asserted an `<img>` pointing at the cover
  endpoint with non-zero `naturalWidth` in **Triage** and the **Library**. The width assertion is
  deliberate — an element whose image failed to load still has a `src`.
- Sprint 046's two `NoCover` tests were rewritten rather than deleted. The decision they encoded is
  reversed; the invariant inside them is not. `P18` is still never read, and `Q151599` must still not
  wear its set photograph, so those assertions now name the poster the film should have instead.
- Owner-directed omission, recorded in DEC-103: no six-month TMDB cache refresh and no TMDB
  attribution notice. The owner accepted the refresh when it was costed, then reversed. Akasha
  therefore sits outside TMDB's API terms for the ~2% of films that path serves.
- Release preparation for **v1.4.0**: all four version surfaces bumped together, README coverage
  extended to Movies and Letterboxd, `docs/operations/release-notes-v1.4.md` added with a
  **Known limitations** section naming all six recorded defects and omissions, and the generated
  OpenAPI contract refreshed. **No migration in this release at all** — the movie domain, its
  importer and its posters are entirely application-level.
- Not run: the container smoke drill, per the owner's standing request not to re-investigate a
  working container, and no packaging behaviour changed in this release.
- Next: merge to `main`, tag `v1.4.0`, push — all three explicitly authorized by the owner.

## 2026-08-31 — Planning session: the series line (Sprints 049–053), plan revision 27

**Done.** No runtime code. Extended the roadmap from 48 sprints to 53 and moved the project from
`complete` back to `ready` on Sprint 049.

Measured first, planned second, in that order:

- **Wikidata as the series primary.** 13/13 series resolved by IMDb id through
  `haswbstatement:P345=`; every fetched entity carried IMDb, TMDB and TVDB ids, an episode count, a
  start date and at least one genre. Seasons absent on 2/13, cast absent on 4/13 (every animated
  series measured), poster property absent on 13/13. Thirteen entities weighed 1.37 MB, so DEC-099's
  bounded batching applies unchanged.
- **The movie search filter does not transfer**, which is the finding of the session. A single
  `P31=Q5398426` filter returned the right series at rank 1 for 9 of 14 titles and *nothing at all*
  for `Chainsaw Man` and `Rick and Morty`; a five-class filter returned 14/14.
- **TVmaze as the fallback.** Keyless, 13/13 by IMDb id, a synopsis and an airing status on every hit,
  and it covers Spanish-language shows Wikidata's title search does not surface. Its images are the
  wrong sizes for the cover pipeline (210×295 and 2000×3000), so it is not a cover source.
- **Posters need no new work.** `images.metahub.space` answered 15/16 series and is already
  allowlisted; the miss was a clean 404.
- **Both exports parsed in place.** IMDb turned out to be *two* CSV shapes with different headers, not
  one. Trakt is a ZIP of 43 verbatim `/sync/*` responses, 26 of them empty, with `imdb` on every movie,
  show and episode object, and episode detail only in `watched-history.json`.
- **The anime-overlap switch the owner asked me to evaluate: measured and dropped.** Over fourteen
  anime spanning the popular and the obscure, Stremio answered 14/14, Wikidata 14/14 and
  TVmaze 13/14 — the condition the switch would fire on did not occur.

**Owner decisions taken during the session.** Three questions were put and all three answered:
multi-domain importers rather than two connectors per source, with the source chosen and the target
decided downstream (DEC-106); TVmaze taken **with** a credit line, unlike TMDB three days earlier
(DEC-105); and the anime switch evaluated independently and dropped if not viable, which it was not
(DEC-107).

**Verified.** `python scripts/validate_project.py` passes. No code, tests, migrations or generated
contracts were touched, so no product gate applies.

**Deviations.** None from the protocol. One change outside the plan, at the owner's explicit
instruction: `exports/` is now gitignored as a whole directory. It was untracked and unignored, and
it holds five private source archives including one carrying the owner's email address.

**Also written, at the owner's request, after reviewing the plan.** Two questions came back and both
produced documentation rather than sprints:

- Auditing the sprint files against the code found **two real defects in what had just been written**,
  both now fixed. Sprint 050 specified a "consult TVmaze when Wikidata returns nothing" fallback that
  does not exist — `search_providers` fans out to every provider in parallel and `_merge_group`
  already does identity grouping and fill-empty by `source_preference`, so the sprint would have sent
  an implementer to build a second merge mechanism competing with the shared one. Sprint 051 left the
  commit signature as "a mapping or per-record resolution, either is acceptable", which is not a
  specification; it now names the exact change.
- **Why anime and series are two domains** is now `docs/guides/adding-a-domain.md` §8, because that
  question is bound to be asked again. The deciding test is not field overlap — 6 of 12 fields, and
  identical statuses, formats and entry shape — it is that `EnrichmentSpec.identity_kind` is one
  string per domain and the two provider sets share nothing: a merged domain would silently never
  enrich whichever half arrived under the other key. The section generalises the test and states the
  accepted cost. The guide's stale intro and file map (movies missing since Sprint 046) were fixed in
  passing. The "move to anime" button the owner asked about is costed there and recorded under **Not
  scheduled** in the roadmap as a general *re-file* feature — it is not a button, because `items.type`
  is written at creation only and a moved item would strand itself from every anime provider.

**Next.** Sprint 049 — the series domain on Wikidata, with posters in the same sprint rather than a
sprint later. Nothing is implemented.

## 2026-08-31 — Sprint 049 complete; series is the fifth domain

**Done.** Series ships as the fifth domain, on keyless Wikidata, with a working poster and a working
episode-progress control from the first commit. `metahub_poster_url` was promoted to
`infrastructure/posters.py`; `domains/series/` carries the declaration (12 measured fields, anime's
five statuses plus `unsorted`, the movie four formats, `ProgressSpec("Episodes watched", "episode",
total_field="episodes")`), the recognizer and `WikidataSeriesProvider` with the five-class `P31`
filter, the `P170`→`P58` creator fallback, the `_is_series` guard, the claim re-check,
`fetch_by_identifier("imdb")` and the Stremio `cover_url`. Registered into the registry
(`ItemTypeName.SERIES`) and constructed into the provider catalog as `wikidata-series`. No migration,
no new status, no new format, no screen. 28 declaration tests, 19 provider tests, 20 live-captured
fixtures.

**The walkthrough, and what it found.** The gate ran against recorded Wikidata — the replicas were
maxlag-shedding all day (lag 24 s → 47 s and climbing) and the adapter's contractual `maxlag=5`
means every live search is refused — with the Stremio poster fetch and the whole cover pipeline left
live. `scripts/walkthrough_series.py` boots the real application on a disposable data directory and
replays the Wikidata half at the transport seam. 12/12 browser tests pass: the Series tab and its
five status words render from the registry with no frontend change; searching "BoJack Horseman"
finds the animated series a single-class filter would miss; a pasted IMDb link resolves through the
exact `P345` claim to Breaking Bad; the detail page renders the domain's fields and its own words;
the poster is the series' actual poster art (two ~60 KB JPEGs fetched live from
`images.metahub.space`, asserted non-trivial — the Sprint 046 blank-tile failure mode); an episode
count stores and renders `20 / 62 episodes` against the series' own `P1113`, and a count above it is
stored rather than refused; a hand-added series lands in Plan to watch and moves between statuses;
the opinion form offers this domain's formats and no book's; filtering the library by status finds
the series; a link naming no series says so rather than guessing.

One real defect surfaced and was fixed: `resolve_input` was first-match-wins, and the movie domain
(registered before series) claims every `wikidata.org/wiki/Q…` and `imdb.com/title/tt…` URL, so a
pasted series link was intercepted by the movie provider, refused by its film guard, and never
reached the series recognizer. A typed `record_not_found` is an answer about that domain's
catalogue, not about the URL, so the loop now offers the next domain its turn; any other error still
propagates, and when every recognizing domain refuses, the last refusal is the answer. Surfaced to
the owner, who chose the continue-on-miss repair (`eb0a316 [FIX]`, three tests).

Two runner bugs cost time before the gate ran: uvicorn's own lifespan pass re-ran after the replay
seam was installed and rebuilt every provider on a live client, silently undoing the swap (fixed
with `lifespan="off"`, the runner driving the lifespan itself); and the add path fetches the chosen
entity alone rather than as the search batch, so the replay needed single-entity routes derived from
the batch fixtures.

**Verified.** The sprint's focused suites — 252 passed. `make check` — lint, typecheck, format,
OpenAPI-type parity, project validation all pass. `make test` — 967 backend + 189 frontend, zero
warnings from this sprint. `make openapi` — no diff beyond the already-committed `ItemTypeName`
addition. The walkthrough above.

**Deviations.** The walkthrough ran against recorded Wikidata, not live (DEC-108); what is not
proven is that the adapter's request shape is still what live Wikidata answers today, discharged by
one live search once the replicas recover. Fixtures were captured without `maxlag`; `tt0000001`
turned out to be a real film, so the miss fixture uses `tt9999999`; `Q87484192` carries
`P31=Q5398426` itself. The conformance check was refined — `source_preference` is a ranking, not a
strict order; `enrichment.provider_order` stays strict (DEC-109). The shared resolve repair is a
behaviour change outside the listed deliverables, approved by the owner during the walkthrough.

**Also observed, out of scope, recorded for the owner.** The `/api/search/resolve` route maps every
failure — including a plain `record_not_found` miss — to a 502 "Metadata could not be resolved", so
a link that names nothing still reads as a provider outage rather than a clean "no series by that
name". The walkthrough tolerates it; a future sprint may want to map a miss to a 4xx.

**Next.** Sprint 050 — TVmaze, the second series provider: a real synopsis, an airing status, and
the shows Wikidata's search misses. The identity strategy already declares `("wikidata", "tvmaze")`,
so 050 adds an adapter, not a declaration.

## 2026-08-31 — Sprint 050 (complete)
- Done: closed Sprint 050 (TVmaze, the second series provider). The implementation was already
  committed by the prior session (`0e96e9a` adapter, `e094a4b` merge/registration, `ff4ec35` credit,
  `d279341` provenance, `e1f8719` format). This session fixed the walkthrough spec's wrong assertion,
  resolved the unexplained 422, wrote the Outcome, added DEC-110, advanced the roadmap and state to
  Sprint 051, and rewrote the handoff.
- Verified: focused backend suites 229 passed; `make check` green (lint, typecheck, format,
  OpenAPI-type parity, project validation); `make test` 989 backend + 190 frontend, the single warning
  a pre-existing Letterboxd zipfile duplicate-name; `make openapi` clean. The walkthrough spec ran
  5/5 green earlier in the session against recorded Wikidata+TVmaze with a live Stremio cover fetch.
- Deviations: (1) The walkthrough spec asserted TVmaze's synopsis would appear on the merged record —
  a misread of `fill_empty`, which only fills empty fields; Breaking Bad's Wikidata synopsis is
  non-empty so it correctly survives. Corrected the assertion to the designed rule (fill when empty,
  overwrite nothing); the merge was already right. The spec is gitignored scratchpad, so the fix is
  local-only. (2) The intermittent `422 POST /api/entries` was identified by static analysis as the
  designed `near_match_confirmation_required` guard (`application/add.py:197-202`) firing on a
  leftover row when two add-tests ran back-to-back against a reused walkthrough data dir; it does not
  reproduce on a fresh data dir. Recorded as a harness state artifact, not a product defect. (3) The
  `bounded_json` widening to `Any` plus the `bounded_json_object` companion is recorded as DEC-110.
- Blocked/open: the walkthrough gate ran against recorded provider responses, not live (DEC-108); one
  live series search is still owed to prove the adapters' request shape is still what live Wikidata
  and TVmaze answer today. Carried into the handoff.
- Next: Sprint 051 — One source, many libraries. A connector declares the domains it can produce
  (`Importer.item_types`), the shared service resolves the domain per record, the screen renders a
  target checkbox per declared type, and the chosen targets fold into the preview fingerprint. Built
  and proved against a test connector, not IMDb. Read `docs/sprints/051-multi-domain-imports.md`.

## 2026-08-31 — Planning session: the gate-optimization sprint (Sprint 051), plan revision 28

- Done: no runtime code. The owner directed TESTING.md's *Optimization backlog* to run as a sprint
  before the remaining roadmap. Inserted **Sprint 051 — The verification gates get faster**
  (file expanded from TEMPLATE.md, status `ready`) and renumbered the import line 051→052,
  052→053, 053→054 (three `git mv`s plus every reference). Moved `FINAL_SPRINT` 53→54, bumped
  `plan_revision` to 28, recorded DEC-111, rewrote HANDOFF. Measured the baseline the sprint
  file carries: Playwright 106 passed + 2 skipped in 49.4 s at one worker; Vitest 190 passed in
  23.3 s with 21 `Query data cannot be undefined` warnings on `["attachments",3]`; no timeouts
  configured anywhere; the scrollTo shim already present at `frontend/src/test/setup.ts:30`.
- Verified: `python scripts/validate_project.py` green; `git diff --check` clean. `make test`
  not owed — no application code changed (plan revision, per the playbook).
- Deviations: none beyond the renumbering itself, which DEC-111 records. Append-only records
  (old worklog entries, prior DEC entries, the dated viability report) keep their original
  sprint numbers on purpose.
- Blocked/open: nothing.
- Next: execute Sprint 051 — read `docs/sprints/051-verification-gate-optimization.md`.

## 2026-08-31 — Sprint 051 (complete): the verification gates get faster

- Done: implemented all four TESTING.md optimization-backlog items. (1) Playwright split into a
  parallel `chromium` project and a serial `heavy-library` project holding the two load-sensitive
  10,000-entry invariants (`library.spec.ts:75`, `:125`); 49.4 s → 38.2 s, the modest gain recorded
  as boot-dominated. (2) New shared `frontend/src/test/mockApi.ts` with defined-by-default answers;
  all 24 DetailPage mocks migrated; 21 `Query data cannot be undefined` warnings → 0. The mechanism
  was mocks answering the attachments query with the *entry* JSON, not `fetch` returning undefined.
  (3) `scripts/walkthrough.py` launcher: fresh temp data dir, ephemeral port, readiness wait,
  clean stop, `--replay <module>` seam inside the lifespan. (4) `pytest-timeout` 30 s backend,
  Vitest `testTimeout` 15 s, Playwright `timeout` 60 s stated; backend and frontend bounds proven
  with throwaway sleeping tests (30.06 s, 15.01 s).
- Verified: `npm run test:e2e` 106 passed + 2 skipped in 39.5 s; `npm test` 190 passed, 0 warnings;
  `uv run pytest -q` 989 passed; `make check` green; `make test` 989 + 190; `make openapi` no diff.
  The mockApi guard (un-routed endpoint rejects loudly) and both timeout bounds proven with
  throwaway tests, run and removed.
- Deviations: (1) AC3's flow-through run — one Playwright flow through the launcher — is NOT done;
  the owner stopped further server launches after the harness foreground-timeout loop. The launcher
  is proven to boot and serve in live and replay modes; the flow run is owed and carried into the
  handoff. (2) The Playwright speedup is 23%, not a transformation. (3) The e2e `ECONNREFUSED`
  proxy noise (dev server proxies `/api` to a non-running backend) observed and left, not one of
  the four items.
- Blocked/open: the flow-through proof (above). One live series search is still owed from Sprint
  050, unchanged.
- Next: Sprint 052 — One source, many libraries. Read `docs/sprints/052-multi-domain-imports.md`.
  Its walkthrough gate should use `scripts/walkthrough.py` rather than hand-rolling a fourth runner.

## 2026-08-31 — Sprint 052 (complete): one source, many libraries

- **Done.** The shared import boundary now holds N domains. `Importer.item_types` is an ordered
  tuple; `NormalizedImportRecord.item_type` names a row's own domain (`None` = the first declared);
  `ImportService.domains` replaces `.domain` and three call sites resolve per record — `_validate`,
  `ImportRepository.commit`/`commit_batch` (now `domains: Mapping[str, Domain]`, reading the type
  from the stored payload), and the enrichment guard (`any(... .enriches)`). `IMPORTERS_BY_DOMAIN`
  is derived from declarations rather than written out. The screen renders a checkbox per declared
  type, named from `/api/item-types`, none at all for a connector with one; the **service** applies
  the choice and drops unwanted rows before staging. `ImportSnapshot.skipped` is the reader's tally
  of rows no domain holds. Five commits, `8c05dbe` → `d91aaad`.
- **Verified.** Focused suites 319 passed (307 before). `make test` 1012 backend + 194 frontend.
  `make check` green. `make openapi` regenerated — `item_types` plus three `PreviewSummary` fields
  is the whole diff. Playwright serial 106 passed + 2 skipped in 1 m 43 s, the historical baseline.
- **Walkthrough gate, and Sprint 051's owed flow-through proof discharged with it.** Ran
  `cd backend && uv run python ../scripts/walkthrough.py --replay ../scripts/walkthrough_two_domains.py`
  (backend on an ephemeral port, fresh temp data dir, live provider boundary), then
  `BOOK_TRACKER_INCLUDE_SCRATCHPAD=1 BOOK_TRACKER_E2E_BACKEND=http://127.0.0.1:<port> npx playwright
  test --project=chromium --workers=1 e2e/scratchpad/sprint52-walkthrough.spec.ts` — passed in 8.1 s.
  **This is the first Playwright flow to run through the tracked launcher**, which is what Sprint 051
  left owed. Exercised: `/api/importers` publishing `two_domains → ["movie","series"]`; both
  checkboxes ticked and named "Movie"/"Series" from the registry; unticking Series giving 2 rows with
  "2 rows are for libraries you did not choose · 3 TV Episode — not a kind this tracks" and 0 errors;
  the **same file** previewed again with both ticked giving 4 rows rather than the cached 2 (the
  fingerprint trap, proved in a browser); one commit reporting "4 entries added; 0 already present";
  Triage showing `Apply Watchlist to Arrival`, `Apply Watchlist to Sicario`, `Apply Plan to watch to
  The Wire`, `Apply Watching to Breaking Bad` — each row its own domain's words in one inbox; a
  status change persisting on a series row; undo leaving items, entries and identifiers all at zero.
- **Sprint 050's owed live series search, discharged.** `GET /api/search?q=Breaking Bad&type=series`
  against live Wikidata and TVmaze returned 10 candidates; the top hit carried
  `{wikidata: Q1079, imdb: tt0903747, tmdb: 1396, tvmaze: 169, thetvdb: 81189}` — both adapters
  answered and merged on the IMDb id, so their request shape is still what those APIs answer today.
  DEC-108's carried debt is closed.
- **Deviations.** (1) The sprint named `tests/test_imports.py`, which does not exist — the suite is
  `tests/test_generic_imports.py`, and the new seam tests are `tests/test_multi_domain_imports.py`;
  corrected in the file. (2) The client mirror is `api/imports.ts`, not `api/library.ts`; corrected.
  (3) `test_goodreads_import.py` compared the whole `summary` for equality and the summary grew three
  fields, so that one assertion now names all seven — same strength, no behaviour changed. (4)
  `useItemTypes` gained an `enabled` flag so the Import screen fetches the registry only when a
  connector can fill more than one library. (5) DEC-112 records the two mechanisms DEC-106 left open.
  (6) The checkboxes read "Movie"/"Series" — the registry's own labels — not the plan's mock copy.
- **Two runner findings worth keeping.** The `--replay` seam is the launcher's only in-application
  hook, so `scripts/walkthrough_two_domains.py` uses it to *register* the fixture connector and
  returns the live transport unchanged; it imports `TwoDomainImporter` from the test suite so the
  browser flow and the unit suite exercise one definition. And navigating to `/import?tab=<id>` by
  URL does not record the source preference, so returning from Triage lands on the remembered
  connector and discards the batch — click the tab instead. Designed behaviour, not a defect
  (`ImportPage.tsx` comments it), but it cost a walkthrough iteration.
- **Also observed, out of scope.** Under six Playwright workers, axe intermittently reports
  `color-contrast [serious]` on `.text-muted-foreground/80` — one class, used once, at
  `frontend/src/features/library/VirtualLibrary.tsx:100`. Green every time serially; the failing
  spec moves between the two that render that caption. Computed statically it is 5.26:1 on the page
  background and 4.88:1 on a surface, both above the 4.5:1 that text size needs — so this looks like
  a sample taken mid-fade, surfaced by Sprint 051's parallel projects rather than caused by them.
  This sprint touches none of that file, class, palette or motion code. Separately:
  `movie.enrichment.identity_kind` is `letterboxd` while `series` is `imdb`, so an IMDb export will
  enrich shows and not films — carried into Sprint 053's baseline as a question it must answer.
- **Next.** Sprint 053 — the IMDb import. Two CSV shapes detected from the header, `Title Type`
  routing onto the skip channel this sprint built, and the negative criterion that decides whether
  the seam actually held: no change to `application/imports.py`, `api/imports.py`, `ImportPage.tsx`
  or `TriagePage.tsx`. Read `docs/sprints/053-imdb-import.md`.

## 2026-08-31 — Sprint 053 (complete): the IMDb import

- **Done.** One connector, `imdb`, declaring `("movie", "series")`, over both export shapes — a
  ratings CSV and a list CSV, told apart by their headers rather than by column position.
  `Title Type` routes each row through a declared table whose default is skip-and-count.
  `Runtime (mins)` lands in `runtime` for a film and `episode_minutes` for a show. Ratings map 1:1
  with no doubling; neither date column becomes a viewing date. Two commits, `60b7a1a` and `3d464e6`.
- **The sprint's negative criterion held.** The whole connector is
  `backend/src/book_tracker/domains/movie/imdb.py` plus one line in `REGISTERED_IMPORTERS`.
  `application/imports.py`, `api/imports.py`, `ImportPage.tsx` and `TriagePage.tsx` are untouched,
  and so is the entire frontend. Sprint 052's seam held for a connector it was not built for.
- **The one thing that did not hold was enrichment, and it is now DEC-113.** The movie domain
  enriched on `letterboxd` alone; an IMDb export carries no Letterboxd URI, so every film from it
  would have been permanently thin — no poster, no genres, no runtime — with nothing failing.
  `EnrichmentSpec.identity_kind` becomes `identity_kinds`, ordered; movies declare
  `("letterboxd", "imdb")`; the backfill runs one statement per key and queues an item once under the
  first it has. A pre-existing test asserted the defect as intended behaviour and was rewritten.
- **Verified.** `tests/test_imdb_import.py` 75 passed. `make test` 1090 backend + 194 frontend.
  `make check` green, `make openapi` no diff. Playwright serial 106 passed + 2 skipped.
- **Walkthrough gate, on the owner's real exports, live boundary.** Fresh backend per attempt via
  `scripts/walkthrough.py`; spec at `frontend/e2e/scratchpad/sprint53-walkthrough.spec.ts` with
  `IMDB_RATINGS` and `IMDB_LIST` in the environment. Passed in 8.2 s. Exercised: the IMDb tab with
  both target checkboxes; 2 rows, 0 errors; commit; Triage showing the film's `Watchlist`/`Watched`
  and the show's five words, scores 8 and 10 unmarked; **both rows approved through the UI**, inbox
  cleared; the list export as a second batch; undo taking it back and leaving the first alone.
  **This pays Sprint 047's debt (DEC-102)** — a movie has now been previewed, approved and undone
  through the real screens.
- **AC9 proved separately, because enrichment is a background job a browser test would race.** A
  scripted live run committed the real ratings export and polled: enriched in about 6 seconds, the
  film to Christopher Nolan, three genres, runtime 172, a description and a poster; the show to its
  creator, three genres, episode_minutes 25, a synopsis, Netflix, `Ended`, 77 episodes, 6 seasons and
  a poster. Before DEC-113 the film half of that was empty.
- **Deviations.** (1) The Verification block named `tests/test_imports.py` again; corrected. (2)
  DEC-093's fifth trap (`shelf_slug` on a punctuation tag) does not apply — this source has no tags
  and creates no shelves; a malformed `Year` and a truncated row are proved instead. (3) A
  structurally short row is a visible row error rather than a skip, so file damage is not hidden
  inside the "not a kind this tracks" count. (4) DEC-113 is a shared-contract change, which the
  sprint's baseline explicitly required be settled rather than left silent. (5) The guide's
  anime/series merge argument rested on `identity_kind` being one string; the verdict is unchanged
  but now rests on `provider_order`, which was the load-bearing half.
- **Harness lesson worth keeping.** Three walkthrough attempts failed on *state carried between
  runs*, not on the product: the launcher gives a fresh data dir per **launch**, and I reran the spec
  three times against one launch. A committed batch replays by fingerprint and approved rows leave an
  empty inbox, so every symptom looked like a product bug. One clean backend per attempt is the rule;
  a two-line wrapper that restarts it makes iteration cheap.
- **Also observed, out of scope.** The show's synopsis came back as Wikidata's one-line description
  ("serie de televisión animada") rather than TVmaze's real synopsis — the designed fill-empty rule
  working (DEC-110), but a poor synopsis on a real record; worth a scoped decision. An IMDb list row
  carries a `Description` this deliberately drops. The intermittent parallel-Playwright
  `color-contrast` finding on `VirtualLibrary.tsx:100` from Sprint 052 is unchanged.
- **Next.** Sprint 054 — the Trakt import, the last planned sprint. Read
  `docs/sprints/054-trakt-import.md`; its baseline was rewritten at this closure with what 053
  established.

## 2026-09-01 — Sprint 054 (complete): the Trakt import

- **Done.** One connector, `trakt`, in `backend/src/book_tracker/domains/movie/trakt.py` plus one
  import and one tuple entry in `domain/registry.py`. Six members read, 31 counted by the source's
  own word, four never opened (the sprint's two email-carrying members, plus
  `user-last-activities.json` and `user-stats.json` — account telemetry, same treatment). Progress
  is distinct `(show, season, number)` events excluding season 0; `plays` is the fallback and a row
  that used it says so in its entry notes. Two commits, `45fd3c4` and `a5f79d0`.
- **The negative criterion held.** `application/imports.py`, `api/imports.py`, `ImportPage.tsx` and
  `TriagePage.tsx` untouched, verified by diff against `7200758`; no other shared or frontend file
  changed either.
- **Two contract findings, both recorded in the Outcome.** (1) The Verification block named
  `tests/test_imports.py` again — corrected, as Sprint 053 did; the focused suites are the six
  import-flavoured files, 439 tests. (2) AC4's "visible warning" cannot be a row error (errors
  block commit, DEC-112) nor a UI change (AC11), and the shared entry-value allowlist refuses
  unknown names in `values` — so it rides `entry.notes`, rendered on the Detail page, with a
  `plays_used` marker in `source_fields`.
- **Verified.** `tests/test_trakt_import.py` 80 passed, every fixture synthetic. Neighbouring
  suites 359 green with the connector registered. `make check` green after four lint fixes and two
  mypy narrowings. `make test` 1172 backend (exactly 1092 + 80) + 194 frontend. Serial Playwright
  106 passed + 2 skipped.
- **Walkthrough gate, on the owner's real archive, live boundary, fresh backend per attempt.**
  `scripts/walkthrough_trakt_054.py` (API, 27 checks, all passed): preview 3 rows 0 errors;
  BoJack 76/76 and Ted Lasso 38/38, no `plays` fallback; commit 3; inbox 3; stored progress 76/38;
  detail payloads carry progress and total; the IMDb ratings export previews its 2 overlapping
  rows as `reuse_item` and commits 0 items 0 entries; undo takes back exactly the Trakt rows.
  `frontend/e2e/scratchpad/sprint54-walkthrough.spec.ts` (browser, 8.9 s): both target checkboxes
  and the VIP note on the Trakt tab; all three rows approved through the Triage UI; **the progress
  control reads "76 / 76 episodes" on BoJack's detail page**; the IMDb overlap commits without
  duplicating; both titles exactly once in their libraries.
- **Harness lessons this session paid for.** (1) The walkthrough script's first order ran the IMDb
  overlap *after* an undo — undo is terminal for a fingerprint, so the re-preview replayed the
  undone batch and the overlap compared against an empty library. Order matters: match checks
  need the rows, undo goes last. (2) The two IMDb CSVs are easy to swap: the `Const,...` header is
  the *ratings* export (the overlapping one); the `Position,...` header is a *list* export
  (House of the Dragon, no overlap). (3) The Library grid's rows are `button "Open <title>"`, not
  links, and the Library is domain-scoped via `/?type=series`. (4) The shared Import preview does
  not render entry values — progress is proven on the Detail page, not the preview screen.
- **Also observed, out of scope.** Nothing new: the recorded defects remain Sprint 055's list.
- **Process note.** The plan-revision-29 session (commit `7200758`) never appended a worklog entry
  despite AGENTS.md §2.6 — this entry covers both sessions' reality; the next session should not
  have to re-derive what revision 29 changed (Sprint 055 planned, FINAL_SPRINT 54→55).
- **Next.** Sprint 055 — the recorded defects and the gate repairs, the last planned sprint.
  Read `docs/sprints/055-recorded-defects.md`. The release decision (v1.5.0, tagging the movie
  line's v1.4.0) comes after it, and nothing is pushed unasked.

## 2026-09-01 — Sprint 055 (complete): the recorded defects fixed, the gates repaired; the plan is finished

- **Done.** Five commits: `33d0d92` (fuller-answer rule, DEC-115), `1fb916d` (the two
  DEC-100 defects, DEC-116), `0eaaf97` (parallel gate green + caption), `0d2597d`
  (coverage/lint/silence), `2c4f7da` (the add path, found by the walkthrough).
- **The synopsis.** `EnrichmentSpec.fuller_answer_fields` — the declaration the sprint
  preferred — with series declaring `("synopsis",)`. The enrichment handler keeps the
  first usable payload for everything else and asks the remaining providers for the
  declared fields alone; the longest string wins. Proved against Sprint 049/050's
  committed recordings with all three negatives intact.
- **The walkthrough earned its keep.** The first live run still stored the one-liner:
  the *add path* consults exactly one provider and never queues background enrichment,
  so a series added by hand kept the one-liner for ever — invisible to every unit suite
  that mocks the boundary. `prefer_fuller` moved to `domain/merge.py` and the add path
  applies it too; re-run live, BoJack stores TVmaze's 151-char synopsis with Wikidata's
  episodes and network kept. **Lesson: a merge rule fixed in one arrival path must be
  checked in every arrival path the item has.**
- **The two DEC-100 defects.** Cover and year are `wants_cover`/`wants_year`
  declarations (default True, what every registered domain means post-Sprint-048) rather
  than constants; `/api/search/resolve` answers a typed `record_not_found` with 404 and
  the provider's own message, keeping 502 for real failures.
- **The parallel gate held, so it was not withdrawn.** Three consecutive green runs at
  the default worker count: 44.5 s, 44.5 s, 45.3 s (a fourth, after the add-path change:
  43.7 s). Four load-sensitive tests moved to the serial `heavy-library` project —
  DEC-114's two plus one more crossfade it had not named (failed the first acceptance
  run, same class) and the three library-view axe checks. The caption at
  `VirtualLibrary.tsx:100` no longer fades.
- **The gates stopped double-charging.** Coverage left `addopts` (focused runs are 1–5 s
  again; `make test` and the new `make coverage` carry the flags). The gitignored
  scratchpad is out of Prettier's and ESLint's sight, so `make check` is green with
  walkthrough specs present. Motion's Reduced Motion notice is filtered at
  `console.warn`, vitest's empty stderr labels suppressed via `onConsoleLog: a green
  `npm test` is silent. TESTING.md's baseline table is this sprint's measurements.
- **Verified.** `make check` green (validator included). `make test` 1184 backend + 194
  frontend, coverage 90%. Focused suites: 342 tests across enrichment, pipeline,
  provider-api, conformance, cached-add, series providers, item types and search.
  Parallel Playwright 106 + 2 skipped, ×4 green. `heavy-library` 7 passed, 18.8 s.
  Walkthrough `scripts/walkthrough_synopsis_055.py` PASSED on the live boundary.
- **Deviations.** (1) The sprint's `tests/test_search_api.py` does not exist — the
  resolve tests live in `test_provider_api.py`. (2) Four tests moved, not two — the
  first acceptance run found the third crossfade and the caption renders in three axe
  checks. (3) `application/add.py` changed: the walkthrough's finding, recorded in the
  Outcome as this sprint's own criterion, not a scope drift.
- **The plan is finished.** All 55 sprints complete; state.json is `complete` with null
  active fields. Nothing is tagged or pushed. The release decision is the owner's:
  v1.5.0 (five domains, four import sources, the series line, all recorded defects
  closed), and whether the movie line's v1.4.0 gets tagged first. Sprint 018's
  procedure is unchanged and nothing moves without being asked.
- **Next.** Whatever the owner directs: the release, an epic from the roadmap's future
  list, or nothing at all. A new sprint would be a plan revision — the seeds skill's
  extension worked example is the shape.

## 2026-09-01 — Planning session: the deployment line (Sprints 056–059), plan revision 30

- Done: no runtime code. The owner asked for a pre-deployment assessment of v1.5.0 and then for the
  findings to be planned as sprints, one per minor release. Added four sprint files expanded from
  `TEMPLATE.md` — **056 deployment defaults** (`ready`), **057 a published image**, **058 nothing
  blocks the event loop** (gated), **059 storage housekeeping** (all `planned`). Recorded
  **DEC-117** with the whole assessment, moved `FINAL_SPRINT` 55→59, bumped `plan_revision` to 30,
  flipped state `complete → ready` with 056 active, extended ROADMAP (revision line, active-sprint
  pointer, tree, index rows, four contract sections, one shape-of-the-plan paragraph), and rewrote
  HANDOFF.
- Evidence the plan is built on, all taken 2026-09-01 on Docker 29.5.2 / Compose v5.1.4:
  `bash scripts/smoke_container.sh` **passed, exit 0**, from a clean build — so the image and its
  data handling are sound and none of these sprints is about them. The gaps are one layer out:
  (1) `compose.yaml` publishes `${AKASHA_PORT:-8000}`, declares no `logging:` (Docker's `json-file`
  default is unbounded and uvicorn's access log is on), passes five variables while `.env.example`
  documents `BOOK_TRACKER_ATTACHMENT_MAX_BYTES`/`BOOK_TRACKER_SQLITE_BUSY_TIMEOUT_MS` and
  `config.py` carries `TMDB_READ_TOKEN` — none of the three reaches the container; healthcheck
  `--start-period=10s --interval=10s --retries=3` is ~40 s against DEC-039's pre-migration backup;
  `compose.bind-mounts.yaml` overrides `/data` and `/backups` together, so DEC-040 cannot be
  satisfied without giving up DEC-075. (2) `build: .` means every install is a build; CI has no
  publish job and no `.github/dependabot.yml`; both `FROM` lines are floating tags. (3) Every API
  handler is `async def` and there is **no** `to_thread`/`run_in_threadpool` anywhere under
  `backend/src/book_tracker/`; `import_service.preview/commit` are sync calls inside `async def`
  handlers; DEC-036's 82 ms idle vs 312 ms contended is the only contended number and it was a read
  path on a workstation. (4) `/data/imports/<batch_id>` is written by every preview
  (`application/imports.py:271`, Calibre's `stage` writes one JPEG per book) and deleted by nothing;
  `ARCHIVED_DIRECTORIES = ("covers", "imports")` is re-tarred in full every backup where DEC-047
  hardlinks attachments; `enforce_retention` is label-scoped so `pre-migration` copies are pruned by
  nothing; no `statvfs`/`disk_usage`/ENOSPC handling exists. Also latent: `api/imports.py:359`'s
  upload branch uses the module constant and ignores `spec.max_bytes`, and hardcodes "5 MiB" in the
  refusal — no upload connector declares a larger cap today, so it is not live.
- Verified: `python scripts/validate_project.py` green after every edit; `git diff --check` clean.
  `make test` not owed — no application code changed (the post-gate matrix's plan-revision row).
- Deviations: the owner set the new default published port (**4441**) and reaffirmed that no auth is
  wanted, both recorded in DEC-117. The assessment also raised mounting an existing Calibre library
  read-only through `CALIBRE_DIR`; the owner rejected it — the library manager in question is being
  retired — so no sprint plans around a Calibre mount, and DEC-081's browser-folder path stays the
  Calibre route.
- Blocked/open: nothing. Sprint 057 carries three steps only the owner's GitHub account can perform
  (workflow package-write permission, pushing the tag, package visibility); they are written out with
  expected results in the sprint file and are not a blocker until that sprint runs.
- Next: execute Sprint 056 — read `docs/sprints/056-deployment-defaults.md`.

## 2026-09-01 — Planning session, second pass: the owner's three amendments (DEC-118)

- Done: no runtime code except one script fix (below). The owner reviewed the plan from the previous
  entry and raised three things.
  1. **Gates.** These sprints would each have owed `make test` under `AGENTS.md` §3, against diffs the
     suites cannot reach. Added **"Gate scope by what changed"** to `TESTING.md` and the enabling
     clause to `AGENTS.md` §3: a sprint may declare a **narrowed gate** —
     `validate_project.py` + `make check` + `make smoke-container`, with `make test` and
     `npm run test:e2e` not owed — only when its whole diff is deployment/CI configuration,
     operator and planning docs, and scripts not under test, touching nothing under `backend/src/`,
     `frontend/src/`, `backend/tests/`, `backend/alembic/versions/`, `uv.lock` or
     `package-lock.json`. It is a claim about the diff and is checked against it (`git diff --stat`
     in the Outcome); one file under `backend/src/` withdraws it for the whole sprint; CI's own
     `checks`/`e2e` jobs still run the full suites on every push. Sprints 056 and 057 declare it,
     058 declares it conditionally (Phase A only — Phase B owes the full gate), 059 owes the full
     gate outright.
  2. **Release numbers.** Minor versions are reserved for new domains and major features, so the
     line ships **v1.5.1–v1.5.4** rather than v1.6.0–v1.9.0. Renumbered across the four sprint
     files, ROADMAP, HANDOFF and the release-notes filenames; Sprint 057's published image tags
     become `1.5.2`, `1.5`, `latest`.
  3. **Personal data in the plans.** Scanned the four sprint files, DEC-117, ROADMAP, HANDOFF and the
     worklog entry: **clean** — no address, host, network, username or hardware anywhere in them.
     The scan did find two pre-existing hits elsewhere in the public repository, neither from this
     line: `scripts/walkthrough_trakt_054.py` carried the owner's Trakt export filename as an inline
     default (an account username), and `docs/sprints/041-myanimelist-import.md:44` names a
     MyAnimeList export filename carrying two account ids. **Fixed the first** — `TRAKT_ARCHIVE`
     now defaults to empty with an explicit refusal, which is what Sprint 055's handoff already
     asked of these scripts ("owner paths through the environment, never inline"). Left the second:
     it is a closed sprint file and historical records are not edited. Both strings remain in git
     history, which is pushed and public; rewriting that is the owner's call and was not taken.
- Recorded **DEC-118**. **DEC-117's version references were corrected in place** rather than
  superseded — same day, no sprint had run against it, and leaving four wrong version numbers inside
  the decision that plans them would have been a trap for the next session. The correction is stated
  in DEC-118, here, and in the commit message, which is what keeps it from being a silent edit.
- Verified: `python scripts/validate_project.py` green after every edit; `git diff --check` clean;
  `ast.parse` on the changed script. `make test` not owed — nothing under `backend/src/`,
  `frontend/src/` or either test tree changed; the one script touched is a walkthrough launcher that
  no suite executes. This is the first use of the rule added in this same entry, which is worth
  naming rather than glossing.
- Deviations: the script fix is outside every sprint's scope. It is recorded here as a prerequisite
  repair rather than folded into a sprint, because it removes an account identifier from a public
  repository and should not wait for 056 to be executed.
- Blocked/open: nothing. Sprint 056 is still `ready` and unchanged in scope.
- Next: execute Sprint 056 — read `docs/sprints/056-deployment-defaults.md`.
