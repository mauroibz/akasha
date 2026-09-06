# Handoff — Sprint 072 closed; Sprint 073 ready

`docs/agent/state.json` reads `project_status: "ready"`, `active_sprint: "073"`,
`active_sprint_file: "docs/sprints/073-insights-with-a-shape.md"`, `active_sprint_status: "ready"`,
`last_completed_sprint: "072"`. Plan revision 39, unchanged. A session picking this up starts at
`AGENTS.md` §1 and executes Sprint 073.

## What just happened

Sprint 072 ("A wall of covers") was implemented in a prior session (commits `edc1fe3`..`e3aeacb`)
which then deferred the exhaustive verification gate at the owner's request. This session ran that
gate: `make check`, `make test` (backend 1356, frontend 279, both green), and the full
`npx playwright test`. The first full Playwright run surfaced four failures, all inside this
sprint's own new e2e coverage and none in application code; each was root-caused with direct
instrumentation rather than assumed transient, three were genuine test bugs and fixed, and one
(a `ProviderHealthNotice` axe sample, unrelated file) reproduced as green in isolation — a known
parallel-worker timing sample already on record from the implementation session. Full details,
including exactly what each fix does and why, are in the sprint's own Outcome section and DEC-140.
The closing commit for this reconciliation is `[DOCS] Close sprint 072 and hand off`.

Sprint 072 delivered: the library card is cover-first (cover ≥70% of card area), the score is a
44px chip on the cover's scrim, one sticky command bar replaces four rows of chrome behind a single
**Filters** popover, the response total is visible (plain `N`, or `N of M` filtered), six columns at
2560px, and the second (list) density is genuinely dense (~52px rows, ≥14 visible in 900px).
DEC-023's virtualization contract (fixed-size rows, derived columns, the score picker's in-card
overlay) is unchanged; its two mounted-DOM bounds were re-measured for the new row heights and hold.

## Known-degraded, deliberately not fixed (carried forward, still true)

- `/api/health/providers` reports configuration, not reachability.
- Kitsu's latency tail occasionally exceeds its budget.
- `languages` mixes vocabularies across movie/series sources.
- The book domain declares `Creators` where `Authors` would read better.
- The `insights` ranking scenarios (`creators/count`, `creators/score`, `publisher/count`) in
  `scripts/benchmark_library.py` have exceeded the 500ms first-page budget under contended
  conditions on this workstation in past measurements (DEC-133). Sprint 073 touches this exact
  path and must re-measure rather than inherit an old number or blame its own diff for one it
  didn't cause.
- **New this session:** immediately after an inline status change on a library entry, the Filters
  popover's status option kept its stale facet label (e.g. `To read 4`) until reload, even though
  the filtered response and the visible total were correctly `3 of 20`. A cache-invalidation gap in
  the facet-counts read (Sprint 072's Outcome and DEC-140 have the full context). Not this sprint's
  diff, not fixed here — pick it up in whichever sprint next touches the status facet query, or a
  dedicated one if none does soon.
- If `scripts/validate_project.py` ever fails for a reason unrelated to real doc/state
  inconsistency, check first for a leftover agent worktree under `.claude/worktrees/` — a prior
  instance of this was git-excluded but still walked by the text-hygiene check. Deleting it clears
  a false failure. Run from a clean checkout before believing a failure.

## Still owed to the owner

- **Sprint 065's DEC-025 walkthrough against the owner's real imported library** — still
  outstanding; needs the owner's own container.
- Cutting the `v1.6.0` and/or `v1.7.0` release tag(s).
- **DEC-133's open product question** (album ranking ordering `Label` ahead of `Artists`).

## Branch and authorization

On **`ui-readability-proposal`**, branched from `main` at `1914ffe`. Nothing pushed, nothing
merged; `main` is untouched. Authorization does not carry forward: do not push, merge, tag or take
any remote action without being asked.

## Version

Unchanged at `1.7.0`.

## Private data and operational constraints

Unchanged. Secrets, databases, uploaded imports and covers are never committed. v1 has no auth and
stays LAN-only; Calibre is opened read-only. This session ran the frontend's own test suites and
Playwright against its dev/preview servers only — no backend container was launched, and the
owner's own instance was not touched.

## Sprint 073 in one paragraph

Insights stops saying one thing twice in one idiom: the leading key becomes a hero carrying its own
superlatives, Decade and Year become one card at two grains drawn in time order, the score
distribution is drawn (today it isn't drawn at all), and the keys that were a grey footnote become
cards sized by how much they have to say. One read-only endpoint (per-score counts) is the only
backend change. Sprint 074 ("A shelf is a place") follows: the shelves index becomes a board, every
shelf gets a cross-domain page, and a shelf can be pinned into the library bar — the current final
planned sprint. Saved views are accepted in principle and left unscheduled.
