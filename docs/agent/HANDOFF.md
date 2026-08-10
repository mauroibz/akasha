# Handoff — current reality

**Last completed:** Sprint 014 (metadata-correctness-search), 2026-08-09.
**Next:** Sprint 015 (design-system-components) — status `ready`, file at
`docs/sprints/015-design-system-components.md`.

## Read this first

The backend now does what the product promised. Search returns the intended edition first, every
result carries an edition year, and imported and added books acquire real metadata and locally
cached covers. This was verified by using the application against live providers with the owner's
Google Books key, not only by tests — see the walkthrough section of the Sprint 014 worklog entry.

**The enrichment pipeline had never run at all** (DEC-027). Sprint 014 was planned around a broken
Open Library URL; that URL was never reached, because nothing in production code called
`JobRepository.enqueue` and nothing called `JobRunner.tick`. Sprint 011 built a correct durable job
queue that no code path used. Both ends are connected now: importers enqueue on commit, and the
application lifespan drives the runner. If you touch either end, there is no test that will notice
you disconnected them again except `test_enrichment_pipeline.py` — keep it.

`AGENTS.md` section 3 carries the **walkthrough gate**, and it earned its place this sprint: two
defects were found by running the application and none of them by the test suite.

## Plan shape

| Sprint | Scope | Status |
|---|---|---|
| 015 | Design system, shadcn/ui, visible feedback | `ready` |
| 016 | Motion and interaction polish | `planned` |
| 017 | Scale, accessibility, resilience | `planned` |
| 018 | Container, backup, release | roadmap contract |

## What Sprint 015 must know

- **It will break e2e selectors by construction.** `selectOption()` and
  `input[type="checkbox"]` across `library.spec.ts`, `triage.spec.ts`, and `import.spec.ts` stop
  matching once controls become Radix primitives. Rewriting them is in scope, not a regression.
- **Two components stay bespoke** (DEC-026). `ScorePicker` must not become a Radix `Popover`:
  Radix portals to `document.body`, and `frontend/e2e/library.spec.ts` asserts the expanded panel
  stays geometrically inside its card. The library card must not become a shadcn `Card`.
- **The Sprint 013 grid contract is not reopened.** `gridColumnCount`, the 280px pinned card
  height, rows-of-cards virtualization with `overscan: isGrid ? 2 : 4`, and the `data-card-*` /
  `data-score-panel` / `data-mounted-count` / `data-columns` attributes are load-bearing
  (DEC-023, technical-spec section 8).
- **The shelf filter's data source changed.** `HomePage` reads `GET /api/shelves` through a
  `useQuery`, not `entries.flatMap(...)`. Converting the control to a shadcn `select` must keep
  that source. It refetches on every navigation; a `staleTime` would be welcome.
- **The degraded-search indicator has its data already.** `GET /api/health/providers` returns a
  row per provider plus a `degraded` flag, and `getProviderHealth` in `src/api/health.ts` types
  it. Render it; do not invent a new endpoint.

## Provider recordings

`backend/tests/fixtures/providers/` holds verbatim responses captured from Open Library and Google
Books on 2026-08-09, with a README naming the exact URL behind each file. They exist because
DEC-025 forbids proving provider behavior with a mock of the method under test. **Never re-record
them silently** — a fixture is a pinned observation of an external contract, and quietly
refreshing one turns a regression test into a rubber stamp. `scripts/validate_project.py` exempts
that directory from text hygiene so the bytes stay as captured.

## Things noticed and deliberately left

- `100 años de Soledad` (ISBN 9781516909629) has no cover: Open Library returns an edition but all
  its cover URLs 404, and Google Books is not consulted because the edition is otherwise usable.
  Enrichment falls back on a miss, never to complete individual empty fields. If per-field
  completion across providers is wanted, that is a product decision, not a bug fix.
- Entries added through the UI carry no score; the detail page shows an unset control. Correct,
  but it reads oddly beside imported rows.

## State

- Planning revision 6; state points to Sprint 015, project status `ready`.
- Gates at close: validator passed, `make check` passed, `make test` backend **154** / frontend
  **39**, Playwright chromium **33 passed / 2 skipped**, `make build` succeeded,
  `git diff --check` clean.
- The two skipped e2e tests are `live-metadata.spec.ts`, which needs `LIVE_METADATA_MODE` and a
  live backend. Run them with
  `BOOK_TRACKER_E2E_BACKEND=http://127.0.0.1:8100 LIVE_METADATA_MODE=add npx playwright test e2e/live-metadata.spec.ts`.
- Migration head is `0006_job_error_code`.
- `.env` exists locally with the owner's `GOOGLE_BOOKS_API_KEY` and is gitignored. It is never
  committed.
- Commit messages in this repository carry no `Co-Authored-By` trailer.
