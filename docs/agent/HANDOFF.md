# Handoff — current reality

**Last completed:** Sprint 013 (library-grid-layout-repair), 2026-07-23.
**Last session:** 2026-08-08, assessment and replan to roadmap revision 6. Planning only; no
source was changed.
**Next:** Sprint 014 (metadata-correctness-search) — status `ready`, file at
`docs/sprints/014-metadata-correctness-search.md`.

## Read this first

`docs/assessment.md` explains why the plan changed. Summary: thirteen sprints closed green on a
product that does not work. Three libraries required by technical-spec section 8 — shadcn/ui,
Motion, and React Hook Form with zod — were never installed, and four defects were confirmed
against live systems. The backend is sound and is kept; the frontend is rebuilt on the specified
stack.

`AGENTS.md` section 3 now carries a **walkthrough gate**. A sprint touching user-visible behavior
is not complete until you have run the application, performed its flow end to end against
realistic data, and recorded what you saw in the worklog. Passing tests are not evidence that a
flow works. A test that mocks the unit under test does not satisfy a correctness criterion.

## Plan shape

| Sprint | Scope | Status |
|---|---|---|
| 014 | Metadata correctness and search relevance (backend only) | `ready` |
| 015 | Design system, shadcn/ui, visible feedback | `planned` |
| 016 | Motion and interaction polish | `planned` |
| 017 | Scale, accessibility, resilience (was 014, renamed) | `planned` |
| 018 | Container, backup, release (was 015, roadmap-only) | roadmap contract |

## What Sprint 014 must fix

Four defects, all confirmed on 2026-08-08 and detailed in the sprint file:

1. `OpenLibraryProvider.fetch_by_isbn` requests `/books/{isbn}.json`, which takes an OLID.
   Measured: that URL returns 404, `/isbn/{isbn}.json` returns 302. Every enrichment job has
   failed since Sprint 011. Fixing the URL alone is insufficient — the shared `httpx.AsyncClient`
   in `main.py` does not set `follow_redirects=True`, so a 302 would pass `raise_for_status` and
   then fail JSON parsing.
2. `merge_and_rank` re-sorts merged results alphabetically by title, discarding provider
   relevance.
3. Google Books never registers; there is no `.env`, so search runs on Open Library alone with no
   warning.
4. Only the first search result resolves an edition year (`and not enriched` gate).

Plus one frontend data-correctness fix: the `/` shelf filter is derived from loaded pages rather
than `GET /api/shelves`.

**The enrichment defect survived because `backend/tests/test_jobs.py` replaces `fetch_by_isbn`
with an `AsyncMock` in all five places it appears.** The replacement test must replay a committed
recorded Open Library response, including the redirect.

## Boundaries for the next agent

- **Owner action outstanding.** Sprint 014's walkthrough needs `GOOGLE_BOOKS_API_KEY` in `.env`.
  Code and tests can proceed without it; the walkthrough cannot. If it is still missing, leave the
  sprint `in_progress` and say so rather than closing it.
- **The Sprint 013 grid contract is not reopened.** `gridColumnCount`, the 280px pinned card
  height, the rows-of-cards virtualization with `overscan: isGrid ? 2 : 4`, and the
  `data-card-*` / `data-score-panel` / `data-mounted-count` / `data-columns` attributes are
  load-bearing (DEC-023, technical-spec section 8).
- **Two components stay bespoke** (DEC-026). `ScorePicker` must not become a Radix `Popover`:
  Radix portals to `document.body`, and `frontend/e2e/library.spec.ts` asserts the expanded panel
  stays geometrically inside its card. The library card must not become a shadcn `Card`.
- Sprint 015 will break `selectOption()` and `input[type="checkbox"]` selectors across
  `library.spec.ts`, `triage.spec.ts`, and `import.spec.ts` by construction. Rewriting them is in
  that sprint's scope, not a regression.

## State

- Planning revision 6; state points to Sprint 014, project status `ready`.
- Gates at the end of the planning session: `python scripts/validate_project.py` passed,
  `make check` passed, `make test` backend 122 / frontend 38, `git diff --check` clean.
- `.github/workflows/ci.yml` now has a `playwright` job; the Chromium suite had never run in CI.
- `scripts/validate_project.py` bounded the complete-project check at `range(1, 13)` while the
  plan had reached 015; corrected to 018 along with the same hardcode in `AGENTS.md` and
  `WORKFLOW.md`.
- Commit messages in this repository carry no `Co-Authored-By` trailer.
