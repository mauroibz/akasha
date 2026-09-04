# Handoff — Sprint 070 closed; Sprint 071 (What the numbers say) is ready

`docs/agent/state.json` reads `project_status: "ready"`, `active_sprint: "071"`,
`active_sprint_file: "docs/sprints/071-what-the-numbers-say.md"`,
`active_sprint_status: "ready"`, `last_completed_sprint: "070"`. Plan revision 38;
`FINAL_SPRINT` in `scripts/validate_project.py` is 71 — **071 is the last planned
sprint**, so closing it correctly triggers `WORKFLOW.md`'s final-sprint rule (project
`complete`, active fields `null`) rather than advancing to a 072 that does not exist.
`docs/sprints/071-what-the-numbers-say.md`'s own `Status` is `ready`.

## What just happened

Sprint 070 ("One surface") shipped in full: the `Panel`, `PageHeader`,
`SegmentedControl` and `DomainStrip` primitives (generalized from what Sprints 066/067
built for `/insights`) now cover Library, Detail, Shelves, Add, Import and Triage; every
cover routes through `CoverImage` including Detail's; the import preview stopped
misusing the score ramp, painting a staged cover like a 9 or a 10, and printing raw
`field: code` at a reader. All 8 deliverables, all 10 acceptance criteria — see
`docs/sprints/070-one-surface.md`'s own Outcome for the full account, and DEC-137 for
the three things worth a decision record: what AC3's field-label fix can honestly do
with no backend change, the actual mechanism behind DEC-134's fix (one flex-item level
higher than the strip itself), and one new out-of-scope defect the walkthrough found.

**Read `070-one-surface.md`'s Outcome before touching any of the six screens it
touched** — it names five new shared components, where each one is now used, and three
deliberately kept differences (the library's translucent virtualized cards, the
connector guide's quieter box, Detail's title staying beside the cover rather than
becoming a `PageHeader`).

## What comes next: Sprint 071 — What the numbers say

Read [`071-what-the-numbers-say.md`](../sprints/071-what-the-numbers-say.md) in full
before starting — this handoff is not a substitute for it. In one sentence: shelves
becomes an openable ranking (a magnitude bar, up to three covers, the count, a link into
`/?shelf=slug`), the library gains an active-filters row generalized from
`InsightFilterChip`, and counts that describe a whole carry visible weight. It depends
on Sprint 070's primitives, which are built and available now.

**This is the final planned sprint** (`FINAL_SPRINT` = 71). Closing it correctly means
following `WORKFLOW.md`'s final-sprint rule: `project_status` becomes `complete`,
`active_sprint`/`active_sprint_file`/`active_sprint_status` become `null`, and
`completed_sprints` gains `071` — not "advance to the next ready sprint," because there
isn't one yet.

## Known-degraded, deliberately not fixed (carried forward, still true, plus one new one)

- `/api/health/providers` reports configuration, not reachability.
- Kitsu's latency tail occasionally exceeds its budget.
- `languages` mixes vocabularies across movie/series sources.
- The book domain declares `Creators` where `Authors` would read better.
- **New, found by Sprint 070's own walkthrough (DEC-137):** `/import`'s "Choose an
  import source" connector strip (`ImportPage.tsx`'s `sourceStrip`, a bare shadcn
  `TabsList`) overflows a 390px viewport by about 205px against the real backend's seven
  registered importers (Goodreads, Calibre, MyAnimeList, Letterboxd, IMDb, Trakt,
  Spotify). Confirmed pre-existing (not something Sprint 070 touched) and distinct from
  DEC-134's domain-radiogroup overflow, which Sprint 070 did pay for. Belongs to whichever
  future sprint next touches `ImportPage.tsx`'s connector strip, or a dedicated one if
  none does soon.
- The domain radiogroup's 390px overflow (DEC-134) — **paid**, Sprint 070, for both `/`
  and `/insights`. No longer degraded; kept here only so a stale memory of it does not
  resurface as a re-opened item.

## Still owed to the owner

- **Sprint 065's DEC-025 walkthrough against the owner's real imported library** — still
  outstanding, needs the owner's own container. (Sprint 070's own walkthrough used a
  throwaway seeded backend, per its own instructions — it does not satisfy this one.)
- Cutting the `v1.6.0` and/or `v1.7.0` tags.
- **DEC-133's open product question** (album ranking ordering `Label` ahead of
  `Artists`) — still the owner's call.
- **DEC-137's new finding**, above: the import connector strip's 390px overflow — the
  owner has not been asked whether it is worth a dedicated fix or should wait for
  whichever sprint next touches that screen.

## Branch and authorization

On **`main`**, committed directly (this session's worktree) — **nothing pushed**. Eight
commits landed for Sprint 070 (`bc0323f` through `d48817d`; see the Outcome for the full
list) plus this closing documentation commit. Authorization does not carry forward: a
session picking this up was asked to work the active sprint and should do exactly that.
It does not extend to pushing, merging, tagging, or any remote action.

## Version

Unchanged at `1.7.0`. Sprint 070 was frontend-only presentation work; a version bump
belongs to whoever closes the UI-cohesion line (Sprint 071) or decides one is warranted
sooner.

## Private data and operational constraints

Unchanged. Secrets, databases, uploaded imports and covers are never committed. v1 has
no auth and stays LAN-only; Calibre is opened read-only. **The owner's own instance runs
on this host at `127.0.0.1:8000`.** Sprint 070's walkthrough used a throwaway seeded
backend and a throwaway dev server on scratch ports (35251/38755/5180 in that session,
all ephemeral and already torn down) — the owner's own instance was confirmed reachable
and healthy both before and after, and was never pointed at. Sprint 071's own
walkthrough needs the same discipline: a throwaway backend and dev server, never `:8000`,
torn down at close.
