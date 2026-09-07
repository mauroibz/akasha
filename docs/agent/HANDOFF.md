# Handoff — the plan is reopened at Sprint 075

`docs/agent/state.json` reads `project_status: "ready"`, `active_sprint: "075"`,
`active_sprint_file: "docs/sprints/075-identity-in-the-schema.md"`, `active_sprint_status:
"ready"`, `last_completed_sprint: "074"`, `plan_revision: 40`. `completed_sprints` runs `001`
through `074`. `FINAL_SPRINT` in `scripts/validate_project.py` is `82`.

**Read [`../auth-and-multiuser-proposal.md`](../auth-and-multiuser-proposal.md) and DEC-146 before
Sprint 075's own file.** The proposal is the design and the sprint files are its schedule; a
sprint file assumes you have read it.

## What is being built

The owner asked on 2026-09-07 for authentication and multiuser: one install serving at least two
independent libraries, a username and password, an admin with unrestricted access, minimum
friction on mobile behind Tailscale, and a single-user deployment that still needs no
authentication at all. Accepted whole as **DEC-146** and scheduled as Sprints 075–082, ending in
`2.0.0`.

Eight sprints: the schema (075), a user on every request (076), password and session (077), the
login and setup screens (078), the second user and the isolation suite (079), admin view-as (080),
friction — trusted header, long sessions, mobile (081), and the release (082). The roadmap's
"Two people, one install" section summarizes each.

**The three facts that shape all of it:**

1. **Half the data-model work was already done.** `entries.user_id` and `shelves.user_id` have
   existed since migration `0002`, with `uq_entries_user_item`, `uq_shelves_user_slug` and six
   user-leading indexes. `LibraryService` takes a `user_id` and filters on it in ten places.
   Product spec §9's instruction to build the list view as `render(entries WHERE user = X, …)` was
   kept, and the query plans multiuser needs already exist and are already benchmarked.
2. **`AKASHA_AUTH` defaults to `off`, and `off` is bit-for-bit v1.8.0.** 213 backend tests call
   `create_app(`. Authentication on by default breaks every one of them. Every sprint owes the
   criterion that the existing 1364 backend, 305 frontend and 130 e2e tests pass **unchanged**
   with auth off; a sprint that has to edit the suite broadly has the boundary wrong.
3. **Sprint 076 must not be merged into its neighbour.** It ships zero user-visible change across
   24 call sites in 8 files, and it is what makes 077–081 small.

## Known defect, already scheduled

`backend/src/book_tracker/application/export.py:248` (`iter_entries`) walks every entry row with
no `WHERE user_id`, and `export_json` calls it. Harmless with one user; a data leak the day Sprint
079 lands. **Sprint 076 fixes it** — do not fix it earlier and do not leave it for 079 to discover
as a failure.

## Four defaults adopted, overridable before their sprint

DEC-146 adopted the proposal's own recommendations rather than blocking eight sprints on four
questions. Each is cheap to flip **before** its sprint and expensive after:

1. Attachments stay shared, hanging off `items` (affects 075's schema and 079's criterion 8).
2. An admin acting as another user can write, not only read (affects 080).
3. The trusted-proxy header is built, off by default, refusing to start without a peer allowlist
   (affects 081).
4. Calibre stays deployment-wide; a per-user mount is not scheduled.

## Known-degraded, deliberately not fixed (carried forward, still true)

- `/api/health/providers` reports configuration, not reachability.
- Kitsu's latency tail occasionally exceeds its budget.
- `languages` mixes vocabularies across movie/series sources.
- The book domain declares `Creators` where `Authors` would read better.
- Immediately after an inline status change on a library entry, the Filters popover's status
  option keeps its stale facet label until reload, even though the filtered response and the
  visible total are correct. A cache-invalidation gap in the facet-counts read (Sprint 072's
  Outcome, DEC-140). Pick it up in whichever future sprint next touches the status facet query.
- `ScoreDistributionCard` (Insights) spans twelve columns and stretches its ten score bars to fill
  it, the same way the chronology strip did before DEC-143 capped that one.
- The shelf page's mean score chip is a client-side mean over currently-loaded entries, not a
  server aggregate — accurate for any shelf that fits on one page, approximate beyond it.
- "Sort by recently added to" on the shelves board reads a shelf's own `updated_at`, not a true
  last-member-addition time — `entry_shelves` has no timestamp column (DEC-144).
- If `scripts/validate_project.py` ever fails for a reason unrelated to real doc/state
  inconsistency, check first for a leftover agent worktree under `.claude/worktrees/`. Deleting it
  clears a false failure.

## Still owed to the owner

- **Sprint 065's DEC-025 walkthrough against the owner's real imported library** — still
  outstanding; needs the owner's own container. **Sprint 081's tailnet walkthrough is the second
  of this kind** and cannot be faked with a seeded container either. Plan for both.
- **DEC-133's open product question** (album ranking ordering `Label` ahead of `Artists`).
- **Saved views ("smart shelves")** — accepted in principle by DEC-139, still unscheduled. It was
  promised the number 075; that number is now the first authentication sprint, so it becomes a
  sprint after 082.
- The rest of the shelf menu costed in `readability-proposal.md` §5.3 and deferred there: bulk
  shelving from the library, manual order and queues, shelf goals, merging shelves, auto-shelving
  rules.
- **A cheap version-surface check.** Nothing in `make check` verifies that
  `backend/pyproject.toml`, `frontend/package.json`, `main.py` and `frontend/openapi.json` agree;
  only `make smoke-container` does, and it costs minutes (DEC-145). **Sprint 082 owes it** as
  deliverable 7.

## Version and pipeline state

`1.8.0`, tagged, with all four version surfaces in agreement. CI on `main` is **green** as of
`11db2c5` — it had been red from the 1.6.0 bump until 2026-09-07, on three test defects and no
product defect (DEC-145). GitHub Releases exist for v1.6.0, v1.7.0 and v1.8.0; the four v1.5.x
patch tags deliberately have none.

Two lessons from that repair worth carrying:

- **The serial `heavy-library` Playwright project is a scarce resource, not a quarantine to grow.**
  Adding a fourth axe check to it broke the two crossfade DOM-budget probes it shares a worker
  with. Sprints 078–081 add auth and isolation specs; keep them in the parallel project.
- **The documented release procedure never published a GitHub Release**, which is why the page
  stood seven tags behind. Sprint 082 deliverable 10 adds the step.

## Branch and authorization

The authentication plan — the proposal, DEC-146, the eight sprint files, the roadmap, the state
file and `FINAL_SPRINT` — is on **`auth-and-multiuser`**, branched from `main` at `11db2c5` at the
owner's explicit request ("branch before committing the proposal"). `main` carries only the
DEC-145 CI repairs and is pushed. The branch is **not** pushed and no pull request exists.

Authorization does not carry forward. Do not push, merge, tag, open a PR, or take any remote
action without being asked, even though this session pushed `main` and published three Releases
when asked to.

## Private data and operational constraints

Secrets, databases, uploaded imports and covers are never committed. **Calibre is opened
read-only.** The exposure rule still stands in its v1 form until Sprint 082 rewrites it narrower:
no public DNS, port-forwarding, tunnel or internet-reachable proxy while `AKASHA_AUTH` is `off`.
Nothing in Sprints 075–082 puts Akasha on the internet — authentication is the precondition for
that, not the same thing.
