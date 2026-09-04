# Handoff — Sprint 067 closed; every planned sprint (001–067) is complete

`docs/agent/state.json` reads `project_status: "complete"`, `active_sprint: null`. Plan
revision 36; `FINAL_SPRINT` in `scripts/validate_project.py` is 67 and matches
`completed_sprints`' length. **No sprint is active.** The next session's first job, per
`AGENTS.md`, is to establish context and confirm with the owner what comes next — there is
nothing queued.

## What just happened

**[Sprint 067 — Insights with faces](../sprints/067-insights-with-faces.md)** closed. It
finished what Sprint 066 started from `docs/insights-redesign-proposal.md`
(**DEC-132**/**DEC-133**): a ranking row now carries the covers of what it counted, a
superlative strip above the fold says what's most collected/highest rated/steadiest about
the library's leading key, and Insights can rank inside the library's own current
status/shelf/format/search filters — off by default, stated in words when it is on.

**Read DEC-134 before touching Insights again.** One corrected reading of the sprint's own
text: covers are gated on whether a row's members actually have a cover (`ItemRow.cover_path`),
**not** on a domain's `chooses_covers` — that flag is the Open Library manual cover-picker
(DEC-067 row 7) and is `False` for every domain but book, even though album, anime, movie and
series entries all carry real cover art from their own providers. Gating on it as the sprint
doc literally said would have shipped covers for one domain only. Also in DEC-134: the AC7
benchmark seed had `cover_path=None` on every item since it was written, which would have
measured an always-empty join — fixed before trusting the number. And one out-of-scope defect
the walkthrough found and did **not** fix: at 390px the domain radiogroup (book/album/anime/
movie/series, five real domains) overflows the viewport by about 39px, unchanged code from
Sprint 066 that neither sprint's own mocked tests ever exercised past one or two domains.

## Current numbers

- Backend **1,333** tests, frontend **243**, Playwright **113 passed / 2 skipped / 0
  failed**. `make check` green. `docs/decisions.md` ends at **DEC-134**.
- `scripts/benchmark_library.py --entries 5000 --jobs 100` (seed now gives most items a
  cover): every insights scenario inside the 500ms budget — `creators/count` 294.2ms p95,
  `publisher/count` 365.9ms p95 (the largest jump now that covers are computed).

## Still owed to the owner

- **Sprint 065's DEC-025 walkthrough against the owner's real imported library** — Sprint
  064's Spotify albums, the Calibre books — and the report of whether score density makes the
  score order worth having. Sprint 066's and 067's own walkthroughs both ran on seeded data and
  do **not** discharge it. That data lives in the owner's own container.
- **The 390px domain-radiogroup overflow** (DEC-134). Not urgent — it is a five-domain layout
  edge that neither prior sprint's tests caught — but it is real and unfixed.
- Cutting the `v1.6.0` tag (`docs/operations/publishing-images.md`).
- **A product decision the redesign proposal's DEC-133 already raised and did not answer:**
  the ordering rule puts an album library's `Label` ahead of `Artists`. Left as designed;
  whether concentration or "who made it" should lead is the owner's call, not an agent's.

## Branch and authorization

Still on **`insights-redesign`**, off `ui-search-refresh-mini-sprint`, off unmerged Sprint
063/064/065 work off `main`. **Nothing has been merged, pushed, or opened as a PR.**
Authorization does not carry forward: this session was asked to work the active sprint and
did exactly that. It does not extend to merging into `main`, pushing, any remote action, or
cutting the `v1.6.0` tag.

## What Insights is, in one paragraph

`GET /api/insights` ranks one domain's entries by a declared groupable metadata field
(`creators`, `publisher`, `genres`, …) or by the built-in `year`/`decade`, by count or mean
score. Scope is per-domain: DEC-052 and DEC-077 twice declined to build the cross-domain
creator identity a merged ranking would need. A `key`/`value` filter on `/api/entries` is how
a ranking row reaches the entries behind it, used by the library link and the in-place
expansion alike. The query, `groupable`, suppression and the per-request temp-table
materialization are **DEC-131**; the redesigned screen is **DEC-132**/**DEC-133**; the covers,
superlative strip, library totals and filter passthrough are **DEC-134**.

## Known-degraded, deliberately not fixed (carried forward, still true)

- `/api/health/providers` reports configuration, not reachability.
- Kitsu's latency tail occasionally exceeds its budget.
- `languages` mixes vocabularies across movie/series sources, and a `language` insights
  ranking lists raw ISO codes because that is what the metadata holds.
- The book domain declares `Creators` where `Authors` would read better on an insights card.
- The domain radiogroup on `/insights` overflows at 390px with five real domains (DEC-134,
  this sprint's own walkthrough finding, out of scope for it).

## Version

`1.6.0` across `backend/pyproject.toml`, `main.py`'s FastAPI `version=`,
`frontend/package.json` and the generated `frontend/openapi.json`. Release notes at
`docs/operations/release-notes-v1.6.md` (written for Sprint 065; Sprint 066's and 067's
changes are additive to the same release and are not yet reflected in that file's prose —
worth a pass before the tag is cut). Sprint 067 changed OpenAPI surface:
`InsightRowResponse.covers`, `InsightResponse.total_entries`/`rated_entries`, and four new
query parameters on `GET /api/insights`.

## Private data and operational constraints

Unchanged. Secrets, databases, uploaded imports and covers are never committed. v1 has no
auth and stays LAN-only; Calibre is opened read-only. **The owner's own instance runs on this
host at `127.0.0.1:8000`** — this sprint's walkthrough used a throwaway backend on `:46005`
and frontend on `:5180` against a `/tmp` data directory precisely to avoid it, and removed
both at close. Do not point a walkthrough at `:8000` without asking.
