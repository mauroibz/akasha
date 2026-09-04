# Handoff — the export line closed at 069; Sprint 070 is the UI-cohesion line's first sprint

`docs/agent/state.json` reads `project_status: "ready"`, `active_sprint: "070"`,
`active_sprint_file: "docs/sprints/070-one-surface.md"`, `active_sprint_status: "ready"`,
`last_completed_sprint: "069"`. Plan revision 38; `FINAL_SPRINT` in
`scripts/validate_project.py` is 71. `docs/sprints/070-one-surface.md`'s own `Status` is
`ready`.

**If you read a Sprint 070 called "Their formats, not ours" in an older summary or in
your own memory of this session, that sprint no longer exists.** It was built in full,
then reverted the same day at the owner's direction for exceeding scope. Read "What just
happened" below before doing anything else — this is not the export line's Sprint 070
any more, it is the UI-cohesion line's Sprint 070, a completely different piece of work.

## What just happened

**The export line closed at Sprint 069, not 070.** DEC-135 originally accepted three
sprints (068, 069, 070). 068 (the `ExportView` contract, a generic per-domain `table`
CSV) and 069 (the Export tab) shipped and are unaffected by anything below — see their
own Outcome sections. Sprint 070 as originally planned — `myanimelist`, `letterboxd` and
an IMDb-shaped series exporter, one `ExportView` per external ecosystem — was built in
full in this session (implemented, 1,367 backend tests passing, verified live against
real parsers and a real browser) and then **reverted in full** (`git reset --hard` back
to the commit closing 069) after the owner reviewed it and said the actual request was
narrower: *"a simple exporter for your data... complete enough that you can rebuild your
akasha later, but that's it,"* not exporters "compatible with every other provider," and
that a provider-specific exporter, if one exists, should be modular. **DEC-136** records
the full reasoning. `docs/sprints/070-their-formats-not-ours.md` no longer exists.

**In the same decision, the owner accepted the UI-cohesion proposal** and asked for it to
be the next work. `docs/sprints/071-one-surface.md` and
`docs/sprints/072-what-the-numbers-say.md` are renamed to `070-one-surface.md` and
`071-what-the-numbers-say.md` — filling the slot the withdrawal freed rather than leaving
a gap, the same renumbering precedent DEC-065 and DEC-127 already set. **Sprint 070 is
now "One surface"**, the first sprint of that line, and it is `ready` to start.

## What is actually true about export, right now

- `GET /api/export` — the lossless entity-shaped JSON (Sprint 024). This is the
  rebuild-your-Akasha artifact.
- `GET /api/exports` / `GET /api/export/{view}?type=<domain>` — the declared-view
  machinery (Sprint 068): `goodreads` (books, pre-existing) and a generic `table` CSV
  for every domain, driven entirely by that domain's own field declarations.
- The Export tab on `/import` (Sprint 069) renders all of the above with no view named
  in any `.tsx` file.
- **No MyAnimeList, Letterboxd, or other ecosystem-specific exporter exists.** If one is
  wanted later, it needs its own proposal, sized to what's actually being asked for, and
  — per DEC-136 — it needs to be modular: not compiled unconditionally into
  `domain/registry.py`'s `REGISTERED_EXPORTS`, which is how the reverted attempt worked
  and exactly what made it "not modular" in the owner's own words. This codebase has no
  optional-feature mechanism today; building one is new scope, not something to assume
  is free next time this comes up.

## What comes next: Sprint 070 — One surface

Read [`070-one-surface.md`](../sprints/070-one-surface.md) in full before starting —
this handoff is not a substitute for it. In one sentence: apply the `Panel`,
`PageHeader`, `SegmentedControl` and `DomainStrip` primitives (generalized from what
Sprints 066/067 built for `/insights`) across Detail, Shelves, Import, Add, Triage and
Library, put every cover through `CoverImage`, fix the import preview's score-ramp
misuse, and pay DEC-134's outstanding 390px domain-strip overflow once for both screens
it appears on. Frontend only; no screen changes what it does. Its own acceptance
criterion 9 is the load-bearing one: the existing component and e2e suites pass
unchanged except where a test asserts one of the proposal's eleven named findings.

`071-what-the-numbers-say.md` follows it (shelves as an openable ranking, an
active-filters row, weighted counts) — do not start it before 070 lands; it depends on
070's primitives.

## Still owed to the owner

- **Sprint 065's DEC-025 walkthrough against the owner's real imported library** — still
  outstanding, unrelated to either the export or UI-cohesion line, needs the owner's own
  container.
- **The 390px domain-radiogroup overflow on `/insights`** (DEC-134) — Sprint 070 (One
  surface) is where this finally gets paid, per its own deliverable 5.
- Cutting the `v1.6.0` and/or `v1.7.0` tags.
- **DEC-133's open product question** (album ranking ordering `Label` ahead of
  `Artists`) — still the owner's call.

## Branch and authorization

On **`main`**, committed directly — **nothing pushed**. The reverted Sprint 070 attempt
existed only as local commits (`0ec94dc`, `1f844ce`, `9c14629`, `3e4700d`, `d0ff170`)
that are no longer reachable on `main` after the reset this session performed; they were
never pushed, so nothing shared needed to change. Authorization does not carry forward:
a session picking this up was asked to work the active sprint and should do exactly
that. It does not extend to pushing, merging, tagging, or any remote action.

## Known-degraded, deliberately not fixed (carried forward, still true)

- `/api/health/providers` reports configuration, not reachability.
- Kitsu's latency tail occasionally exceeds its budget.
- `languages` mixes vocabularies across movie/series sources.
- The book domain declares `Creators` where `Authors` would read better.
- The domain radiogroup on `/insights` overflows at 390px with five real domains
  (DEC-134) — see "What comes next" above.

## Version

Unchanged at `1.7.0`. Nothing shipped this session (built, then reverted). A version
bump belongs to whoever closes the UI-cohesion line.

## Private data and operational constraints

Unchanged. Secrets, databases, uploaded imports and covers are never committed. v1 has
no auth and stays LAN-only; Calibre is opened read-only. **The owner's own instance runs
on this host at `127.0.0.1:8000`.** Any walkthrough for the UI-cohesion sprints needs a
throwaway seeded backend and a throwaway dev server on scratch ports, torn down at
close — do not point one at `:8000` without asking.
