# Handoff — Sprint 073 closed; a library-card follow-up is owed before Sprint 074 starts

`docs/agent/state.json` reads `project_status: "ready"`, `active_sprint: "074"`,
`active_sprint_file: "docs/sprints/074-a-shelf-is-a-place.md"`, `active_sprint_status: "ready"`,
`last_completed_sprint: "073"`. Plan revision 39, unchanged.

**Before Sprint 074's own implementation starts**, the owner asked for a follow-up pass on
Sprint 072's library card: the covers do not match the accepted mockup closely enough, there is
still wasted space, and the total/status readout reads centered and hard to parse at a glance.
This is out-of-band from the sprint sequence — 072 is closed — and should land as its own small
commit with a decision record, the same way DEC-138 recorded an owner-directed fix to an
already-closed sprint's finding, before a session moves on to Sprint 074's actual deliverables.
A session picking this up should do that pass first, then start Sprint 074 at `AGENTS.md` §1.

## What just happened

Sprint 073 ("Insights with a shape") was implemented and closed in one session, immediately
after Sprint 072's deferred gate was closed in the same session. One backend addition
(`GET /api/insights/scores`, `LibraryService.score_distribution()`); everything else frontend:
the hero panel (leading key's top row promoted, superlatives folded inside), Decade/Year merged
into one card with a client-side grain toggle (`labels.ts`'s new `InsightKeyOption.grain`), the
chronology strip (time-ordered decades, zero-count gaps kept), the score distribution band, an
asymmetric 12-column grid, and the long tail drawn as clickable cards instead of a footnote.
Full detail — every acceptance criterion, every test changed and why, the benchmark numbers — is
in the sprint's own Outcome and DEC-141.

**The DEC-025 walkthrough found two real defects, both fixed before closure:**

1. In a real seeded library, *Decade* led rather than a metadata field — every fixture built
   during implementation happened to keep a metadata field in the lead, so `ChronologyCard` had
   no hero mode, and the hero rendered with zero superlatives when it was the leading key. Fixed:
   `ChronologyCard` gained the same `hero` prop `InsightsCard` has.
2. Three superlative tiles squeezed into one row at 390px truncated their labels. Fixed:
   `SuperlativeStrip` stacks one tile per row below `sm`.

Neither is carried forward as known-degraded — both were fixed in-session, and the fixes were
re-verified with a second walkthrough render plus a full clean re-run of `make check`, `make
test`, and `npx playwright test`.

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

- **The library-card follow-up above** — the owner's own words: covers don't match the accepted
  mockup, still-wasted space, a centered total/status readout that is hard to parse at a glance.
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
stays LAN-only; Calibre is opened read-only. This session's Sprint 073 walkthrough ran a
throwaway backend (`scripts/walkthrough.py`) seeded via its own API with invented book data, torn
down afterward — the owner's own instance was never touched.

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
