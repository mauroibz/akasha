# Handoff — every planned v1 sprint is complete

`docs/agent/state.json` reads `project_status: "complete"`, `active_sprint: null`,
`active_sprint_file: null`, `active_sprint_status: null`, `last_completed_sprint: "071"`.
Plan revision 38; `FINAL_SPRINT` in `scripts/validate_project.py` is 71, and Sprint 071
("What the numbers say") reached it. **There is no active sprint file to read and no
next sprint to start.** A session picking this up should read "Still owed to the owner"
below before inventing new work — the numbered plan is done, but this is not the same
as "nothing left to do."

## What just happened

Sprint 071 shipped in full, plus one addition folded in at the owner's explicit
request. `docs/sprints/071-what-the-numbers-say.md`'s own Outcome has the complete
account; the summary:

- **Shelves became an openable ranking**: `ShelfResponse.covers` (the only backend
  change — DEC-134's own lateral top-3 join, keyed by shelf), a magnitude bar, up to
  three covers, and the name linking into `/?shelf=slug`.
- **The library gained an active-filters row**: one dismissable chip per set filter
  (shelf, format, status, query, insights key), generalized from the insights-only
  `InsightFilterChip`.
- **Counts that describe a whole carry visible weight**: shelf sizes, the status
  popover's facet counts, and the import preview's ready/needs-a-choice/errors summary,
  all through one `weightClass` helper built on the same `magnitude` arithmetic the
  ranking bar already used.
- **DEC-137's mobile fix, added in-session at the owner's direction** (the request was
  "work on the last sprint, add the mobile ui fix"): `/import`'s connector-choice strip,
  found overflowing a 390px viewport by Sprint 070's own walkthrough and left unfixed
  there, got DEC-134's own structural answer. Recorded as **DEC-138**, cross-referencing
  DEC-137 rather than rewriting it.
- **Two regressions were found and fixed inside this same session**, both introduced by
  this sprint's own commits and both closed before the gate that would otherwise have
  carried them forward as known-degraded: a test-helper selector collision the
  active-filters chip exposed, and a magnitude-bar contrast regression on a near-full
  shelf's Delete button. Full detail in the sprint's own Outcome and in
  `docs/agent/worklog.md`'s 2026-09-05 entry.
- **One pre-existing condition was observed, not fixed**: the `insights` ranking
  scenarios in `scripts/benchmark_library.py` exceed their 500ms budget under the
  contended condition on this workstation. DEC-131 territory, no line of insights
  ranking code touched by this sprint's diff — recorded here and in the worklog rather
  than silently noticed and dropped.

## Final sprint: what "complete" means here

`docs/agent/WORKFLOW.md`'s final-sprint rule has been applied: `project_status`,
`active_sprint`, `active_sprint_file` and `active_sprint_status` are set as above, and
`completed_sprints` runs `001` through `071` with no gaps. **This does not mean the
product is finished** — it means every sprint the roadmap had planned is delivered. New
work (a bug the owner reports, a feature they ask for, a proposal like
`ui-cohesion-proposal.md` was) gets its own new sprint file, numbered 072 onward, the
same way DEC-135/DEC-136 extended the plan twice already when the owner asked for more
after a prior "final" sprint closed. Do not invent a 072 speculatively; wait for the
owner's direction the way both of those extensions did.

## Known-degraded, deliberately not fixed (carried forward, still true)

- `/api/health/providers` reports configuration, not reachability.
- Kitsu's latency tail occasionally exceeds its budget.
- `languages` mixes vocabularies across movie/series sources.
- The book domain declares `Creators` where `Authors` would read better.
- The `insights` ranking scenarios (`creators/count`, `creators/score`,
  `publisher/count`) in `scripts/benchmark_library.py` exceed the 500ms first-page
  budget under the contended (200-jobs-queued) condition on this workstation — p95
  552.9–1009.4ms, measured 2026-09-05. DEC-131 governs this query's budget; no sprint
  since has touched the query itself. Whoever picks this up next should re-measure
  before assuming it is still true, since it depends on host load as much as on code.
- DEC-134's domain-radiogroup overflow and DEC-137's import-strip overflow are both
  **paid** now (Sprints 070 and 071 respectively). Kept out of this list on purpose —
  removed rather than marked resolved, so a stale memory of either does not resurface
  as a re-opened item.

## Still owed to the owner

- **Sprint 065's DEC-025 walkthrough against the owner's real imported library** — still
  outstanding, needs the owner's own container. Every walkthrough run since (Sprints
  070 and 071 both) used a throwaway seeded backend per their own instructions; neither
  satisfies this one.
- Cutting the `v1.6.0` and/or `v1.7.0` (or later) release tag(s) — never done this
  session or any recorded prior one.
- **DEC-133's open product question** (album ranking ordering `Label` ahead of
  `Artists`) — still the owner's call.

## Branch and authorization

On **`main`**, committed directly, inside this session's worktree
(`.claude/worktrees/agent-ae82b747e32836664`, branch
`worktree-agent-ae82b747e32836664`) — **nothing pushed**. Eight commits landed for
Sprint 071 (`ca6709d` through `3733b1f`; see the sprint's own Outcome for the full list
and what each one did) plus this closing documentation commit. Authorization does not
carry forward: a session picking this up should not push, merge, tag, or take any
remote action without being asked to, regardless of what any prior session was told.

## Version

Unchanged at `1.7.0`. Neither Sprint 070 nor 071 bumped it. A version bump — and
cutting the tag(s) named above — is still owed and belongs to whoever the owner asks
to do it, not to whoever happens to close a sprint.

## Private data and operational constraints

Unchanged. Secrets, databases, uploaded imports and covers are never committed. v1 has
no auth and stays LAN-only; Calibre is opened read-only. **The owner's own instance runs
on this host at `127.0.0.1:8000`.** Sprint 071's own walkthrough used a throwaway
seeded backend (`scripts/walkthrough.py`, ephemeral port) and a throwaway Vite dev
server (scratch port 4321), both already torn down — the owner's own instance was
confirmed reachable and healthy both before and after (`curl .../api/health/ready`),
and was never pointed at. Any future walkthrough needs the same discipline.
