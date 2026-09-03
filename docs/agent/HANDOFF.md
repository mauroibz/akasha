# Handoff — Sprint 065 closed; nothing queued next

`docs/agent/state.json` reads `project_status: "complete"`, `active_sprint: null`.
Sprint 065 was the last sprint this roadmap had planned — `FINAL_SPRINT = 65` in
`scripts/validate_project.py` — not a claim that the product is finished.
`docs/sprints/ROADMAP.md`'s "Owner feedback" and "Not scheduled" sections hold real,
already-costed candidates for a Sprint 066 the owner hasn't chosen yet.

## This work is on `ui-search-refresh-mini-sprint`, not a new branch

Same branch as the session before this one (the DEC-129/130 mini-sprint), which itself
sits on unmerged Sprint 063/064 work off `main`. The owner explicitly chose to continue
on this branch rather than open a new `sprint-065-insights` one. **Nothing has been
merged, pushed, or opened as a PR.**

## What Sprint 065 was, in one paragraph

`GET /api/insights` ranks one domain's entries by a declared groupable metadata field
(`creators`, `publisher`, `genres`, …) or by the built-in `year`/`decade`, by count or
mean score — "which authors do I rate highest," "which bands do I own most of." Scope
is deliberately per-domain: DEC-052 and DEC-077 twice declined to build the
cross-domain creator identity a merged ranking would need, and this feature exists to
keep it that way. A `key`/`value` filter added to `/api/entries` lets a ranking row
link straight into the library, filtered to exactly the entries it counted. The
`/insights` screen: domain picker, key picker, count/score toggle, a minimum-rated
threshold, a suppressed-values toggle (the album domain suppresses `Various Artists`),
and a ranked table. Full account and every material decision: **DEC-131**.

## A real performance finding, and the fix

The sprint's own required benchmark (`scripts/benchmark_library.py --entries 5000
--jobs 100`, matching AC9) caught a genuine budget breach: `creators`/`score` measured
670 ms p95 against the library's own 500 ms budget, under write contention. Not because
`json_each` is slow — because the first working version re-ran its own `json_each` +
`normalize_text` pass three separate times per request (the aggregate, the
best-spelling window function, and an eagerly-computed `no_rated_groups` check).
Fixed by materializing the exploded rows once per request into a SQLite `TEMP TABLE`
rather than the sprint doc's named fallback (a maintained key table via migration) —
no schema change needed. Re-measured stable at ~290 ms p95. See DEC-131 for the
`normalize_text`-UDF decision this sits beside (DEC-036 removed that exact
registration from the *hot* search/sort path; Insights is registering it again for a
much colder one, and the two are explicitly reconciled there, not left in tension).

## Verified, with one real limitation stated plainly

Full backend (1,326) and frontend (206) suites, `make check`, `make smoke-container`,
and the full Playwright suite (111; 7 failed only under parallel-worker contention and
passed individually on re-run — the same flakiness Sprint 064's handoff already
recorded, none touching Insights) are all green. Also walked through manually in a
real browser: a throwaway backend on an unused port (`8010`), seeded through the real
HTTP API, driving Chromium directly via the `playwright` package already in
`frontend/node_modules` (`chromium-cli`/Claude-in-Chrome was not available in this
environment) — domain switching, metric switching, the suppressed-state and
zero-rated-state renders, and a ranking row's click landing on the library filtered to
exactly its members, all confirmed with screenshots and an empty console-error log.

**What this is not**: the sprint doc's own DEC-025 walkthrough, which asks for this
against the *owner's real, already-imported* library — Sprint 064's 157 real Spotify
albums, the Calibre books. That data lives in the owner's own running container, which
this session did not have access to. Recorded as open in the sprint file's Outcome.
**The owner's own instance is running on this host, on `127.0.0.1:8000`** (noticed
while looking for a free port for the throwaway backend above — its `/api/item-types`
response predates this sprint, confirming it wasn't started by this session). It was
not touched, inspected further, or used for anything; the throwaway backend used
`8010` instead precisely to avoid it.

## Current state, concretely

- **Backend:** 1,326 tests passing (1,306 at this session's start + 20 new).
  **Frontend:** 206 passing (203 + 3 new). `make check` green. `make smoke-container`
  green. Full e2e green (see above).
- **`docs/decisions.md`** ends at **DEC-131**.
- **New surface:** `GET /api/insights`, `/api/entries`'s `key`/`value` params,
  `FieldSpec.groupable`, `Domain.insight_suppressed_keys`, `LibraryService.rank()`,
  `frontend/src/pages/InsightsPage.tsx`, the `/insights` route and nav entry.
- **Version bumped to `1.6.0`** (`backend/pyproject.toml`, `main.py`'s FastAPI
  `version=`, `frontend/package.json`, regenerated `frontend/openapi.json`). Release
  notes at `docs/operations/release-notes-v1.6.md`, covering this sprint and Sprint
  064's Spotify import together, per the sprint doc's own instruction. **Cutting the
  `v1.6.0` tag is the owner's action** (`docs/operations/publishing-images.md`) —
  nothing here pushed a tag.

## Known-degraded, deliberately not fixed (carried forward, still true)

- `/api/health/providers` reports configuration, not reachability.
- Kitsu's latency tail occasionally exceeds its budget.
- `languages` mixes vocabularies across movie/series sources.

## Private data and operational constraints

Unchanged. Secrets, databases, uploaded imports and covers are never committed. v1 has
no auth and stays LAN-only; Calibre is opened read-only. The owner's own instance runs
on `127.0.0.1:8000` (or `4441` published) — see above; this sprint's manual browser
verification ran on an isolated throwaway backend (port `8010`) and frontend (port
`5180`) against a `/tmp` data directory, both stopped and removed at close.

Authorization does not carry forward: this session was asked to continue sprint work
on this branch and did exactly that. It does not extend to merging into `main`,
pushing, or any remote action, or to cutting the `v1.6.0` release tag.
