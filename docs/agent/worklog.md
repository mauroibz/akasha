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
