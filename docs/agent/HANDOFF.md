# Handoff — the plan is complete

`docs/agent/state.json` reads `project_status: "complete"`, `active_sprint: null`,
`active_sprint_file: null`, `active_sprint_status: null`, `last_completed_sprint: "074"`.
`completed_sprints` runs `001` through `074` — every planned sprint, including the three the
owner's 2026-09-05 readability feedback added (DEC-139) after Sprint 071 closed the original v1
plan. `FINAL_SPRINT` in `scripts/validate_project.py` is `74`; nothing raises it further without
the owner asking for a new sprint. A session picking this up should not assume there is an active
sprint to continue — check with the owner what, if anything, comes next, rather than inventing one.

## What the three readability sprints delivered

The owner's report — *"there is a lot of wasted space everywhere... covers and the main number
should be larger... the insights page reads bland... the shelves tab is too bland"* — became
`docs/readability-proposal.md`, accepted whole as DEC-139, and built as:

- **Sprint 072 — A wall of covers.** The library card is cover-first (cover ≥70% of card area,
  pinned height, DEC-023's fixed-size virtualization unchanged), the score and status sit at
  opposite edges of the cover, one sticky command bar replaces four rows of chrome behind a single
  **Filters** popover, the response total is visible, six columns at wide widths, list density
  genuinely dense. Frontend only.
- **Sprint 073 — Insights with a shape.** A hero panel promotes the leading key with its own
  superlatives folded in; Decade and Year are one card with a grain toggle; a chronology strip
  draws decades in time order; a score-distribution band (the sprint's one backend addition,
  `GET /api/insights/scores`) draws the 1-10 spread; an asymmetric grid sizes cards by rank; the
  long tail is clickable cards instead of a footnote.
- **Sprint 074 — A shelf is a place.** The shelves index is a board of cards, each with a
  scrolling cover rail, a magnitude bar, and one chip per domain it holds (`members_by_type`, the
  sprint's one backend addition). A domain filter, sort and search work the board. Every shelf
  gets its own page (`/shelves/:slug`) showing the set whole across every domain it holds — a
  deliberate, owner-accepted exception to the library's one-domain-at-a-time rule (DEC-065,
  DEC-139 §2) — with rename and delete moved there off the index, and a shelf can be pinned into
  the library's command bar.

Two owner-directed layout fixes landed between and after these, outside the sprint sequence, the
same pattern DEC-138 established:

- **DEC-142** — the wall card's score and status were one shared, centred pill instead of two
  controls at the cover's opposite edges (the accepted mockup's own layout). Fixed.
- **DEC-143** — the library caption had dead space under a visibly pale `bg-surface` fill, and the
  Insights hero/chronology strip wasted the width they were given. Both fixed; the caption's
  height is now the content's actual height, and the hero/chronology bars use their space.

Every sprint's own Outcome section (`docs/sprints/07{2,3,4}-*.md`) has full delivered-behaviour
detail, every acceptance criterion, and every test that changed and why. DEC-140 through DEC-144
have the decisions worth reading independent of the code.

## Known-degraded, deliberately not fixed (carried forward, still true)

- `/api/health/providers` reports configuration, not reachability.
- Kitsu's latency tail occasionally exceeds its budget.
- `languages` mixes vocabularies across movie/series sources.
- The book domain declares `Creators` where `Authors` would read better.
- Immediately after an inline status change on a library entry, the Filters popover's status
  option keeps its stale facet label (e.g. `To read 4`) until reload, even though the filtered
  response and the visible total are correctly `3 of 20`. A cache-invalidation gap in the
  facet-counts read (Sprint 072's Outcome, DEC-140). Pick it up in whichever future sprint next
  touches the status facet query, or a dedicated one if none does soon.
- `ScoreDistributionCard` (Insights) spans twelve columns and stretches its ten score bars to
  fill it, the same way the chronology strip did before DEC-143 capped that one. Out of scope for
  both owner reports that drove DEC-143; recorded there for whenever Insights is next touched.
- The shelf page's mean score chip is a client-side mean over currently-loaded entries, not a
  server aggregate — accurate for any shelf that fits on one page, approximate beyond it
  (Sprint 074's Outcome).
- "Sort by recently added to" on the shelves board reads a shelf's own `updated_at` (bumped on
  creation and rename), not a true last-member-addition time — `entry_shelves` has no timestamp
  column of its own. Adding one is a migration nobody has asked for yet (Sprint 074's Outcome,
  DEC-144).
- If `scripts/validate_project.py` ever fails for a reason unrelated to real doc/state
  inconsistency, check first for a leftover agent worktree under `.claude/worktrees/` — a prior
  instance of this was git-excluded but still walked by the text-hygiene check. Deleting it clears
  a false failure. Run from a clean checkout before believing a failure.

## Still owed to the owner

- **Sprint 065's DEC-025 walkthrough against the owner's real imported library** — still
  outstanding; needs the owner's own container. Every walkthrough since has run against a
  throwaway seeded backend instead.
- **DEC-133's open product question** (album ranking ordering `Label` ahead of `Artists`).
- **Saved views ("smart shelves")** — accepted in principle by DEC-139, needs a `saved_views`
  table and a migration, deliberately left unscheduled. Becomes a sprint the day the owner asks;
  `docs/sprints/ROADMAP.md`'s "Not scheduled" section has the design note it carries forward
  (a saved view must still parse after a filter is added or renamed).
- The rest of the shelf menu costed in `readability-proposal.md` §5.3 and deferred there: bulk
  shelving from the library, manual order/queues, shelf goals, merging shelves, auto-shelving
  rules. None scheduled.

## Branch and authorization

`ui-readability-proposal` (branched from `main` at `1914ffe`) was merged into `main`
(fast-forward — `main` had no commits of its own past that point), pushed, and tagged `v1.8.0` at
the owner's explicit request ("commit, merge to main, push and tag a new version"). `main` is now
current with all of Sprints 072-074 and both layout fixes. Authorization does not carry forward to
future sessions: do not push, merge, tag, open a PR, or take any remote action again without being
asked, even though this session did.

## Version

`1.8.0`, tagged. `docs/operations/release-notes-v1.8.md` has the release notes.

## Private data and operational constraints

Unchanged. Secrets, databases, uploaded imports and covers are never committed. v1 has no auth and
stays LAN-only; Calibre is opened read-only. Every walkthrough across Sprints 072-074 and both
layout fixes ran against throwaway or mocked fixtures — the owner's own instance was never
touched, and Sprint 065's walkthrough against it remains the one still owed.

## If a session picks this up with nothing specific asked

There is no active sprint and no numbered work queued. Do not start Sprint 075 or invent new
scope on your own initiative — saved views is the only named-but-unscheduled candidate, and even
that is "the day the owner asks," not before. A session with no specific instruction should read
this file, confirm the state above against `docs/agent/state.json`, and ask the owner what they
want next rather than guessing.
