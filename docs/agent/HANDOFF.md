# Handoff — Sprint 069 closed; Sprint 070 is next

`docs/agent/state.json` reads `project_status: "ready"`, `active_sprint: "070"`,
`active_sprint_status: "ready"`. Plan revision 37; `FINAL_SPRINT` in
`scripts/validate_project.py` is 70 (unchanged — 070 is the last sprint of the accepted
export line). `docs/sprints/070-their-formats-not-ours.md`'s own `Status` is `ready`.
This is the last sprint of the accepted export line (DEC-135); no further sprint is
scheduled after it unless the owner accepts the UI-cohesion line (071–072, still
proposed and unaccepted).

## What just happened

**[Sprint 069 — A door out of the app](../sprints/069-a-door-out-of-the-app.md)**
closed. Export is now reachable without reading the API: `/import` gained a third,
unnumbered tab (`?tab=export`, and `/export` redirects to it exactly the way `/triage`
already redirects) rendering `GET /api/exports`'s declarations generically — a row per
`(view, domain)` pair, plus the hand-written lossless-JSON row placed first and marked
as such. The nav item is renamed **Import → Data**. Guide steps render through
`DeclarationGuide`, split out of `ConnectorGuide.tsx` so the import and export sides
share one renderer rather than each having their own.

**This sprint spanned two sessions**, worth knowing if anything about the history looks
odd: the first session made three commits (`e0c92d8`, `6ce461d`, `c568ab8`) and was cut
off by an API rate limit while about to start the required walkthrough. Not a blocker,
not a defect — the second session verified the inherited commits fresh against the
sprint's own acceptance criteria (reading the actual code, not trusting the commit
messages) before building on them, found them correct, and closed the sprint without
needing a fourth production commit.

**Read the sprint's own Outcome for the interpretive call it had to make:** AC1's "reach
a file... in two clicks from the nav" is satisfied as *reach the point where a domain's
file is one click away* (nav → Export tab), the same reachability DEC-079 already
established for Triage. Actually downloading is inherently a further click in any such
flow; the e2e suite and this sprint's own walkthrough both prove that click works.

## Current numbers

- Backend unchanged at **1,352** (no backend file touched this sprint, confirmed by
  diff). Frontend **253** passed (was 243, +10). Full Playwright **118 passed, 2
  skipped, 0 failed** (was 113/2/0, +6). `make check` green. `docs/decisions.md` still
  ends at **DEC-135** — no deviation needed recording.

## Still owed to the owner

- **Sprint 065's DEC-025 walkthrough against the owner's real imported library** — still
  outstanding, unrelated to this sprint line, needs the owner's own container. None of
  066, 067, 068 or 069's own walkthroughs discharge it.
- **The 390px domain-radiogroup overflow on `/insights`** (DEC-134). Still real, still
  unfixed, still not urgent — unrelated to this sprint's own (clean) 390px result on the
  export tab.
- Cutting the `v1.6.0` and/or `v1.7.0` tags.
- **DEC-133's open product question** (album ranking ordering `Label` ahead of
  `Artists`) — still the owner's call.
- **Series' export target is still undecided** — proposal §2.3 flags it as the one open
  product question in the export line, and **Sprint 070 is where it gets resolved**:
  measured and built, or recorded as "the `table` floor is the answer for series," per
  DEC-088/DEC-127's precedent of measuring rather than guessing.
- **The nav label ("Data") is the owner's call**, shipped as this sprint's own
  recommendation over the proposal's other option ("Import & export"). One line
  (`AppShell.tsx`'s `navItems`) to change if the owner prefers otherwise.

## Branch and authorization

On **`main`**, committed directly — **nothing pushed**. Three commits for Sprint 069:
`e0c92d8`, `6ce461d`, `c568ab8` (first session), no further production commit needed
(second session verified and closed only). Authorization does not carry forward: this
session was asked to work the active sprint and did exactly that. It does not extend to
pushing, merging, or any remote action.

## What export is, in one paragraph

Backend (Sprint 068, unchanged this sprint): `GET /api/export` is the lossless JSON;
`GET /api/exports` lists every registered `ExportView`'s declaration with a live entry
count; `GET /api/export/{view}?type=<domain>` streams one. Frontend (this sprint):
`/import`'s third tab (`ExportPanel.tsx`) renders `GET /api/exports` with no view's id,
label or domain named in any `.tsx` file — a row per `(view, item_type)` pair, each
showing its label, what it carries, its live count, a download control that reports
in-progress/success/failure, and its guide steps through `DeclarationGuide`. A
zero-entry domain shows a disabled, explained control rather than being hidden. The nav
item is **Data**; `/export` and `?tab=export` both land there and the tab survives a
reload.

## Known-degraded, deliberately not fixed (carried forward, still true)

- `/api/health/providers` reports configuration, not reachability.
- Kitsu's latency tail occasionally exceeds its budget.
- `languages` mixes vocabularies across movie/series sources.
- The book domain declares `Creators` where `Authors` would read better.
- The domain radiogroup on `/insights` overflows at 390px with five real domains
  (DEC-134). The export tab's own 390px result (this sprint) is clean, for contrast —
  the difference is that the export tab was designed against three items, not five.

## Version

Unchanged at `1.7.0`. Sprint 069 added a route and a nav rename but no OpenAPI surface
of its own (068 already shipped the endpoints this sprint renders) — a version bump, if
any, belongs to whoever closes the export line (070, if it ships as planned).

## Private data and operational constraints

Unchanged. Secrets, databases, uploaded imports and covers are never committed. v1 has
no auth and stays LAN-only; Calibre is opened read-only. **The owner's own instance runs
on this host at `127.0.0.1:8000`** — this sprint's walkthrough used a throwaway seeded
backend on an ephemeral port and a throwaway Vite dev server on a scratch port, both
torn down at close, precisely to avoid it. Do not point a walkthrough at `:8000` without
asking.
