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
