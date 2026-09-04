# Handoff — Sprint 066 closed; Sprint 067 is active

`docs/agent/state.json` reads `project_status: "ready"`, `active_sprint: "067"`.

## What just happened

The owner used what Sprint 065 shipped, said the data was right and the screen was
not, and accepted `docs/insights-redesign-proposal.md` as **DEC-132**. That scheduled
two sprints; **066 is closed** and **[067 — Insights with faces](../sprints/067-insights-with-faces.md)**
is `ready`. Plan revision 36; `FINAL_SPRINT` in `scripts/validate_project.py` is 67.

**`/insights` is redrawn.** One card per key instead of a popover and one table; the
row *is* its own bar; the count/score toggle is a sort order with both numbers on every
row; rows too thinly rated to place sit under a divider instead of being dropped; a row
opens in place over the `key`/`value` filter; and the library says which ranking filtered
it. Which keys get a card, and in what order, is a stated rule (`features/library/insights.ts`)
rather than `__init__.py` order.

**Read DEC-133 before Sprint 067.** Three findings: `GET /api/insights?key=year` had
returned **500 since Sprint 065 shipped it** and was repaired in 066 as a prerequisite
defect; the batched `keys=` parameter was **measured and deliberately not added**, so do
not add it on a hunch; and the ordering rule puts **Label above Artists** on an album
library, which is left as designed because which judgement should lead is the owner's
call, not an agent's.

**Sprint 067 owes a re-measurement, not an assumption.** It adds a lateral top-3 to a
query whose budget DEC-131 already had to repair once. The benchmark harness
(`insights_scenarios()`) exists; AC7 is written to be measured.

## Current numbers

- Backend **1,328** tests, frontend **231**, Playwright **113 passed / 2 skipped / 0
  failed**. `make check` green. `docs/decisions.md` ends at **DEC-133**.
- `scripts/benchmark_library.py --entries 5000 --jobs 100`: every scenario inside the
  500 ms budget; `insights creators/count` 277.8 ms p95.

## Still owed to the owner

- **Sprint 065's DEC-025 walkthrough against the owner's real imported library** —
  Sprint 064's Spotify albums and the Calibre books — and the report of whether score
  density makes the score order worth having. Sprint 066's walkthrough ran on seeded
  data and does **not** discharge it. That data lives in the owner's own container.
- Cutting the `v1.6.0` tag (`docs/operations/publishing-images.md`).

## Branch and authorization

This work is on **`insights-redesign`**, branched from `ui-search-refresh-mini-sprint`,
which itself sits on unmerged Sprint 063/064/065 work off `main`. **Nothing has been
merged, pushed, or opened as a PR.** Authorization does not carry forward: this session
was asked to propose the redesign, schedule it, and build it, and did exactly that. It
does not extend to merging into `main`, pushing, any remote action, or cutting the
`v1.6.0` tag.

## What Insights is, in one paragraph

`GET /api/insights` ranks one domain's entries by a declared groupable metadata field
(`creators`, `publisher`, `genres`, …) or by the built-in `year`/`decade`. Scope is
deliberately per-domain: DEC-052 and DEC-077 twice declined to build the cross-domain
creator identity a merged ranking would need, and this feature exists to keep it that
way. A `key`/`value` filter on `/api/entries` is how a ranking row reaches the entries
behind it — used by both the library link and, since Sprint 066, the in-place expansion.
The query, the `groupable` declaration, the suppression list and the per-request
temp-table materialization that keeps it inside budget are **DEC-131**; the screen in
front of them is **DEC-132** and **DEC-133**.

## Known-degraded, deliberately not fixed (carried forward, still true)

- `/api/health/providers` reports configuration, not reachability.
- Kitsu's latency tail occasionally exceeds its budget.
- `languages` mixes vocabularies across movie/series sources, and a `language` insights
  ranking lists raw ISO codes because that is what the metadata holds (DEC-133).
- The book domain declares `Creators` where `Authors` would read better on an insights
  card. One line in `domains/book/__init__.py`; a vocabulary decision, not a screen one.

## Version

`1.6.0` across `backend/pyproject.toml`, `main.py`'s FastAPI `version=`,
`frontend/package.json` and the generated `frontend/openapi.json`. Release notes at
`docs/operations/release-notes-v1.6.md`. Sprint 066 changed no version and no OpenAPI
surface beyond correcting an insights row key from an integer to the string the schema
had always declared.

## Private data and operational constraints

Unchanged. Secrets, databases, uploaded imports and covers are never committed. v1 has
no auth and stays LAN-only; Calibre is opened read-only. **The owner's own instance runs
on this host at `127.0.0.1:8000`** — Sprint 066's walkthrough used a throwaway backend on
`:8010` and frontend on `:5180` against a `/tmp` data directory precisely to avoid it,
and removed both at close. Do not point a walkthrough at `:8000` without asking.
