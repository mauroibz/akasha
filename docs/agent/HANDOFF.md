# Handoff — the plan is extended; Sprint 072 is ready to start

`docs/agent/state.json` reads `project_status: "ready"`, `active_sprint: "072"`,
`active_sprint_file: "docs/sprints/072-a-wall-of-covers.md"`, `active_sprint_status:
"ready"`, `last_completed_sprint: "071"`. Plan revision 39; `FINAL_SPRINT` in
`scripts/validate_project.py` is now **74**.

**Nothing has been implemented for this line.** The three new sprint files are plans, and
`started_at` is empty. A session picking this up starts at `AGENTS.md` §1 and executes
Sprint 072.

## What just happened

No product code changed. The owner asked for another look at the library UI, the insights
page and the shelves tab; the three screens were **measured** on the owner's own running
instance (`ghcr.io/mauroibz/akasha:1.5.7` on `127.0.0.1:8000`, read-only through its HTTP
API) with Playwright at 1440×900, 2560×1400 and 390×844, and the result is
[`../readability-proposal.md`](../readability-proposal.md) — nineteen findings, each traced
to a line, with alternatives, non-goals and risks. The owner accepted it (**DEC-139**) and
asked for the plans to be committed.

- **`docs/readability-proposal.md`** — the proposal, revised once on the owner's reading of
  the first draft (the shelf card wastes its width on three overlapping faces; are shelves
  multi-domain?). That revision added findings 18 and 19 and rewrote §3.3.
- **`docs/decisions.md` DEC-139** — the acceptance, and the four decisions inside it:
  DEC-023's numbers move while its rule stands; a shelf page spans domains; findings 18/19
  are answered on the shelves screen; saved views are accepted in principle and left
  unscheduled.
- **Sprints 072, 073, 074** — new files, `ROADMAP.md` extended, `FINAL_SPRINT` 71 → 74,
  `state.json` at revision 39 pointing at 072.
- **A visual mockup was published as an artifact for the owner** (before/after for all
  three screens, drawn with their real covers). It is not in the repository and nothing
  depends on it; the proposal is the record.

## Sprint 072 in one paragraph

The library card becomes cover-first: the cover takes the full card width at a pinned
height, the title gets the whole card measure instead of 105px, and the score becomes a
44px chip in the ramp on the corner of the poster. Four rows of chrome collapse into one
sticky command bar, the match count (fetched on every response, today spent only on
`aria-setsize`) becomes visible, wide screens gain columns, and the second density becomes
genuinely dense. **Frontend only.** `gridLayout` is the single place the geometry lives;
DEC-023's contract — fixed-size virtualization, derived column count, the score picker's
overlay contained inside its card — is preserved, and its two mounted-DOM bounds are
re-measured because both row heights change.

Two tests are known in advance to need changing, and both are named in the sprint:
`library.spec.ts`'s "grid cards keep cover, metadata and controls separated" (controls now
sit on the cover deliberately) and `library.test.ts`'s column expectations (which read the
constants and move with them). Everything else must pass unchanged.

## Known-degraded, deliberately not fixed (carried forward, still true)

- `/api/health/providers` reports configuration, not reachability.
- Kitsu's latency tail occasionally exceeds its budget.
- `languages` mixes vocabularies across movie/series sources.
- The book domain declares `Creators` where `Authors` would read better.
- The `insights` ranking scenarios (`creators/count`, `creators/score`,
  `publisher/count`) in `scripts/benchmark_library.py` exceeded the 500ms first-page budget
  under the contended condition on this workstation — p95 552.9–1009.4ms, measured
  2026-09-05, before this session. Sprint 073 touches this path and must re-measure rather
  than inherit the number or blame its own diff for it.
- `scripts/validate_project.py` currently fails on this workstation for a reason unrelated
  to the repository: a leftover agent worktree at
  `.claude/worktrees/agent-ae82b747e32836664/` is git-excluded but still walked by the
  text-hygiene check, so its provider fixtures report "no trailing newline". Deleting that
  directory clears it. Run the validator from a clean checkout before believing a failure.

## Still owed to the owner

- **Sprint 065's DEC-025 walkthrough against the owner's real imported library** — still
  outstanding; needs the owner's own container.
- Cutting the `v1.6.0` and/or `v1.7.0` release tag(s).
- **DEC-133's open product question** (album ranking ordering `Label` ahead of `Artists`).

## Branch and authorization

On **`ui-readability-proposal`**, branched from `main` at `1914ffe`, three commits, nothing
pushed and nothing merged. `main` is untouched. Whoever implements Sprint 072 should decide
with the owner whether to continue on this branch or merge the plans to `main` first —
neither has been authorized. Authorization does not carry forward: do not push, merge, tag
or take any remote action without being asked.

## Version

Unchanged at `1.7.0`.

## Private data and operational constraints

Unchanged. Secrets, databases, uploaded imports and covers are never committed. v1 has no
auth and stays LAN-only; Calibre is opened read-only. **The owner's own instance runs on
this host at `127.0.0.1:8000`** — this session read from it (`/api/entries`, `/api/shelves`,
`/api/insights`, cover images) to measure the screens and to draw the mockup with real
data, and wrote nothing to it. A second backend was run briefly on port 8010 against a
**copy** of `data/` in the scratchpad and has been stopped; the Vite dev server used for
the screenshots is stopped too. Any future walkthrough uses a throwaway seeded backend, not
the owner's instance.
