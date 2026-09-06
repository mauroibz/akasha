# Handoff — Sprint 074 ready to start

`docs/agent/state.json` reads `project_status: "ready"`, `active_sprint: "074"`,
`active_sprint_file: "docs/sprints/074-a-shelf-is-a-place.md"`, `active_sprint_status: "ready"`,
`last_completed_sprint: "073"`. Plan revision 39, unchanged. A session picking this up starts at
`AGENTS.md` §1 and executes Sprint 074 — nothing is owed ahead of it.

## What just happened

Sprint 073 ("Insights with a shape") was implemented and closed in one session, immediately
after Sprint 072's deferred gate was closed in the same session. One backend addition
(`GET /api/insights/scores`, `LibraryService.score_distribution()`); everything else frontend:
the hero panel (leading key's top row promoted, superlatives folded inside), Decade/Year merged
into one card with a client-side grain toggle (`labels.ts`'s new `InsightKeyOption.grain`), the
chronology strip (time-ordered decades, zero-count gaps kept), the score distribution band, an
asymmetric 12-column grid, and the long tail drawn as clickable cards instead of a footnote.
Full detail — every acceptance criterion, every test changed and why, the benchmark numbers — is
in the sprint's own Outcome and DEC-141. Its own DEC-025 walkthrough found and fixed two real
defects (a chronology-led hero rendering with no superlatives; truncated superlative tiles at
390px) before closing — neither carried forward as known-degraded.

**Then, with both 072 and 073 closed**, the owner compared the shipped library card against the
accepted design proposal's own mockup and reported wasted space and a centered, hard-to-read
score/status readout. Reading the mockup's markup confirmed a specific bug: the wall card wrapped
the status pill and score chip in one shared, centred pill instead of drawing them at opposite
edges of the cover the way the mockup does. Fixed and recorded as **DEC-142**, landed as its own
commit outside the sprint sequence (the same pattern DEC-138 used for a prior closed-sprint fix):
`VirtualLibrary.tsx`'s `EntryControls` onCover branch now spans the cover's full width with
`justify-between`, each control carrying its own opaque backing rather than sharing one. Verified
with the full gate (`make check`, backend 1361, frontend 291, Playwright 124/0 failed) and a
before/after screenshot walkthrough. DEC-023's score-picker containment contract is unchanged and
was re-verified, not assumed.

## Known-degraded, deliberately not fixed (carried forward, still true)

- `/api/health/providers` reports configuration, not reachability.
- Kitsu's latency tail occasionally exceeds its budget.
- `languages` mixes vocabularies across movie/series sources.
- The book domain declares `Creators` where `Authors` would read better.
- Immediately after an inline status change on a library entry, the Filters popover's status
  option keeps its stale facet label (e.g. `To read 4`) until reload, even though the filtered
  response and the visible total are correctly `3 of 20`. A cache-invalidation gap in the
  facet-counts read (Sprint 072's Outcome, DEC-140). Not fixed — pick it up in whichever sprint
  next touches the status facet query, or a dedicated one if none does soon.
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
stays LAN-only; Calibre is opened read-only. This session's Sprint 073 walkthrough and the
library-card fix's screenshot walkthrough both ran against throwaway/mocked fixtures — the
owner's own instance was never touched.

## Sprint 074 in one paragraph

The shelves index becomes a board: each card draws its shelf's covers stood up in a scrolling
rail, names the domains it holds with a chip per domain and a count, and the index gets a domain
filter, sort and search. Every shelf gets its own page (`/shelves/:slug`) showing the set whole
across every domain it holds — a deliberate exception to the library's one-domain-at-a-time rule
(DEC-139 §2), since a shelf is a set the owner assembled by hand and "everything in this set" is
the question its page answers. A shelf can be pinned into the library's command bar
(`localStorage`, no backend). One backend addition: members-per-item-type on the shelves
response, the same `GROUP BY` shape the facets block already builds. This is the current final
planned sprint; saved views are accepted in principle and left unscheduled.
