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
