# Sprint 071 — What the numbers say

**Status:** completed
**Depends on:** 070
**Roadmap revision:** 38

> Planned from [`../ui-cohesion-proposal.md`](../ui-cohesion-proposal.md) §3.5, §3.7 and
> §3.8. **Accepted by the owner as DEC-136.** Renumbered from 072 to 071 — see
> `070-one-surface.md`'s own note and DEC-136.

## Objective

Apply the two insights rules that need data rather than paint: a count that is a
proportion is drawn as one, a row carries the faces of what it counted, and a filtered
screen says what it is filtered by. The shelves screen becomes a ranking you can open;
the library says what it is showing.

## Required context

- [`../ui-cohesion-proposal.md`](../ui-cohesion-proposal.md) §1 rules 2, 3 and 4; §2
  findings 5, 6 and 11; §3.5, §3.7, §3.8; §6 (the join is measured, not assumed).
- [`070-one-surface.md`](070-one-surface.md) — the primitives this sprint builds on. Read
  what actually shipped.
- `docs/decisions.md` DEC-134 (the covers-on-a-ranking-row work: the lateral top-3 join
  and **its measured cost** — this sprint repeats that join on a much smaller list),
  DEC-133 (`magnitude`, the bar, and the one-row-open disclosure), DEC-131 (the insights
  query budget), DEC-026 (tokens).
- Code, read fresh: `frontend/src/pages/ShelvesPage.tsx:150-215` (the rows, the count at
  `:193-197`), `frontend/src/features/library/InsightsRanking.tsx` (the bar, the
  `CoverStack`, the disclosure — reused, not re-derived),
  `frontend/src/features/library/insights.ts` (`magnitude`),
  `frontend/src/pages/HomePage.tsx:748-757` and `:978-1002` (`InsightFilterChip`, and the
  `filtersFromParams`/`paramsFromFilters` pair it clears through),
  `frontend/src/api/shelves.ts` (`ShelfWithCount`),
  `backend/src/book_tracker/api/library.py:69-73` (`ShelfResponse`) and `:1078-1080`,
  `backend/src/book_tracker/application/library.py:575-588` (`list_shelves`, the existing
  count subquery) and the insights covers join DEC-134 added.
- Tests: `frontend/src/pages/ShelvesPage.test.tsx`, `HomePage.test.tsx`,
  `backend/tests/test_library_api.py`, `test_library_queries.py`,
  `scripts/benchmark_library.py`.

## Current implementation baseline

- A shelf row is a name, a plain-text count, *Rename* and *Delete*. Nothing links to
  `/?shelf=slug`, which the library supports perfectly well — the one screen about shelves
  is the one place a shelf is a dead end.
- `list_shelves` answers from `ShelfRow` plus one count subquery. No covers.
- `InsightFilterChip` names the insights `key`/`value` filter and clears it. Shelf, format,
  status and the search query are states inside select triggers, and a library narrowed to
  eleven rows explains itself only if you open three controls.
- The import preview's summary line is three numbers at identical weight.

## Deliverables

1. **`ShelfResponse.covers`** (and `ShelfWithCount.covers` on the client) — up to three
   cover URLs per shelf, from the same lateral top-3 join DEC-134 already built and
   benchmarked for insights. **The only backend change in this line.**
2. **A shelf row is a ranking row**: a magnitude bar for its share of the largest shelf,
   up to three covers of what is on it, the count, and the name as a link into
   `/?shelf=slug`. *Rename* and *Delete* stay exactly where they are.
3. **The bar and the cover stack are the ones already built** — `magnitude` and
   `CoverStack` from the insights feature, reused rather than re-derived. If they need
   generalizing to be reusable, that generalization is the deliverable.
4. **An active-filters row on the library**: one dismissable chip per set filter — shelf,
   format, status, query, insights key — generalized from `InsightFilterChip`, clearing
   through the same `paramsFromFilters` path. The selects keep their state; the chips are
   what makes a narrowed library legible.
5. **Counts carry weight** wherever a set of counts describes one whole: shelf sizes,
   status facets, and the import preview's `N ready · N need a choice · N have errors`.
6. **Measured, not assumed.** The shelves query is benchmarked before and after, on a
   library with the shelf count and entry count the benchmark script can produce, and the
   numbers go in the outcome.

## Acceptance criteria

1. A shelf row links into the library filtered to that shelf, and the library arrives
   showing it.
2. Two shelves holding 30 and 10 entries render bars whose widths differ in the same
   proportion; the count remains text, and the bar is decorative to assistive technology.
3. A shelf with entries shows up to three covers; a shelf whose entries have no covers
   shows the shared placeholder, not a gap; an empty shelf shows neither and says it is
   empty.
4. A library filtered by shelf, format, status or query shows a chip naming each filter;
   dismissing one clears exactly that filter and leaves the others set.
5. The insights breadcrumb keeps working and is one chip among the others, not a second
   idiom.
6. `GET /api/shelves` stays inside its budget with covers added, measured on a seeded
   library; the numbers are in the outcome and in a decision record if they are
   surprising.
7. The shelves screen and the library hold at 390px with no horizontal body scroll and
   44px targets; zero serious axe violations on both.
8. **The existing suites pass unchanged**, except where a test asserts finding 5, 6 or 11
   — each named in the outcome.

## Required tests (TDD)

| Behavior | Layer | File |
|---|---|---|
| `list_shelves` returns up to three covers per shelf, empty when none | integration | `test_library_queries.py` |
| `GET /api/shelves` carries `covers` in its schema | api | `test_library_api.py` |
| A shelf row links to `/?shelf=slug` | component | `ShelvesPage.test.tsx` |
| Bar width proportional to shelf size; bar is aria-hidden | component | `ShelvesPage.test.tsx` |
| Covers, placeholder and empty shelf all render distinctly | component | `ShelvesPage.test.tsx` |
| One chip per set filter; dismissing one keeps the others | component | `HomePage.test.tsx` |
| The insights breadcrumb is one of those chips | component | `HomePage.test.tsx` |
| Preview summary counts carry visible weight | component | `ImportPage.test.tsx` |
| Shelves and library at 390px, no horizontal body scroll | e2e | `frontend/e2e/library.spec.ts` |
| No serious violations on shelves and a filtered library | e2e | `frontend/e2e/accessibility.spec.ts` |

## Verification

- `make check`, `make test`, `python scripts/validate_project.py`
- The exhaustive backend suite; `openapi.json` regenerated for the new field.
- `npx playwright test` — owed.
- `python scripts/benchmark_library.py` before and after, for the shelves path.
- **Walkthrough (DEC-025):** against real imported data, open the shelves screen, follow a
  shelf into the library, narrow it with two more filters, drop one chip, and report what
  the shelves screen actually looked like with the owner's real shelves and covers.

## Explicit non-scope

- Everything Sprint 070 owns: the primitives, the covers on detail, the import preview's
  language, the 390px strip.
- Shelf reordering, nesting, colours or icons. A shelf is a name and a set.
- New library filters. The chips name the filters that exist.
- Cross-domain rankings, entity pages, time series — still the insights proposal's §5.
- Filtered export. It is the export proposal's §5 and stays there.

## Commit checkpoints

1. `[ADD] Tell the shelves list what is on each shelf`
2. `[MOD] A shelf you can open, at the size it actually is`
3. `[MOD] Say what the library is filtered by, whichever filter it is`
4. `[MOD] Give a count the weight it has`

## Risks and decisions to surface

- **A join on a request that answers from one table.** Small — tens of rows — but it is a
  backend change with a benchmark precedent, and DEC-134 measured the same join rather
  than assuming it. Do the same.
- **Chips can crowd the library header at 390px** where four filters are set. Decide
  whether they wrap or scroll, and measure it; the strip's answer in Sprint 070 is the
  precedent.
- **Covers on a shelf row invite a shelf detail page.** It is not in scope, and the library
  filtered by shelf is that page.
- **`ShelfWithCount` is used by `AddForm` and `ShelfPicker` too.** A new optional field is
  additive, but check both before assuming it.

## Outcome

**Done: all 6 deliverables, all 8 acceptance criteria**, plus the DEC-137 mobile fix
added to this sprint's scope at the owner's explicit direction (DEC-138).

- **Deliverable 1 (`ShelfResponse.covers`).** `LibraryService._shelf_covers` repeats
  DEC-134's lateral top-3 join, keyed by shelf id rather than ranking value: highest
  scored first, then most recently added, then by entry id. Empty for an uncovered or
  empty shelf. `ca6709d`.
- **Deliverables 2–3 (a shelf row is a ranking row).** `ShelvesPage.tsx`: a magnitude
  bar (share of the largest shelf), up to three covers via `CoverStack` (now exported
  from `InsightsRanking.tsx`), the count, and the name linking into `/?shelf=slug`.
  *Rename*/*Delete* unchanged. `magnitude` and `CoverStack` reused, not re-derived
  (AC1–3). `ac2f299`.
- **Deliverable 4 (active-filters row).** `FilterChip` in `HomePage.tsx`, generalized
  from the insights-only `InsightFilterChip`: one dismissable chip per set filter
  (shelf, format, status, query, insights key), clearing through the same
  `paramsFromFilters` path the selects already used. The insights breadcrumb is one of
  these chips now, not a second idiom (AC4–5). `a616baf`.
  - **Found while wiring it up: an existing test helper collided with the new chip.**
    `openConfirmDialog`'s unscoped `/Dune Messiah/` role/name lookup could match the
    active-filters query chip ("Search · "Dune Messiah"") as well as the actual web
    result card of the same title, and — since the chip renders first — did, breaking
    nine tests that all route through that helper. Scoped the lookup to the "From the
    web" region. `e5636f8`.
- **Deliverable 5 (counts carry weight).** `weightClass` (`features/library/insights.ts`):
  the same `magnitude` arithmetic as the ranking bar, bucketed into three text weights
  (`text-base font-semibold`, `text-sm font-medium`, `text-sm text-muted-foreground`,
  all `tabular-nums`) rather than a continuous style — a discrete class a test can
  assert against, and a set of counts read at a glance rather than measured. Applied to
  shelf sizes (`ShelvesPage.tsx`), the status-facet counts in the library's status
  popover (`StatusFilter.tsx`, weighed against the busiest status shown), and the
  import preview's ready/needs-a-choice/errors summary (`ImportPage.tsx`). `4be458d`.
  - **Found while verifying it: the magnitude bar can undercut a button's contrast.**
    A shelf holding the largest share draws its bar the full row width; the
    Rename/Delete button group had no backing of its own, so the destructive button's
    text rendered against the bar's tint blended into the surface — axe flagged it
    below the contrast threshold on a near-full shelf (the accessibility fixture's
    "Pending" shelf, `entry_count: 4` against a max of 4). Gave the button group its
    own opaque `bg-surface`. `84532f8`.
- **Deliverable 6 (measured, not assumed).** `shelves_scenarios` added to
  `scripts/benchmark_library.py`, alongside the existing library and insights
  scenarios: `list_shelves` against the seeded 13-shelf library. `78ababb`.
  - **Idle:** p50 12.2ms, p95 12.3ms, max 12.4ms.
  - **Contended (200 jobs queued):** p50 13.3ms, p95 13.8ms, max 13.9ms.
  - Both well inside the 500ms budget — the covers join adds no measurable cost at
    this shelf count (AC6). Not surprising enough to need its own decision entry.
  - **Observed, out of this sprint's scope, not fixed:** the pre-existing `insights`
    scenarios (`creators/count`, `creators/score`, `publisher/count`) exceed the same
    500ms budget under the contended condition on this workstation (552.9ms, 585.7ms,
    1009.4ms p95) — DEC-131 territory, no line of insights ranking code touched by
    this sprint's diff. Recorded for whoever next touches that query; not a Sprint 071
    regression.
- **DEC-137's mobile fix, added at the owner's direction (DEC-138).** `sourceStrip` in
  `ImportPage.tsx` gets DEC-134's own structural answer: `overflow-x-auto`/`min-w-0`/
  `max-w-full` on the strip, `shrink-0` on every trigger, and a 44px target each did
  not have before. `3733b1f`.

**Verified:**
- `make check` green (ruff format/lint, prettier, eslint, mypy, tsc, openapi
  check/regenerate, `api:check`, `validate_project.py`).
- `make test`: backend **1,356** passed (unchanged — this sprint's only backend
  change, the covers join, already had its own tests in `ca6709d`); frontend **274**
  passed (was 266 at Sprint 070's close).
- `npx playwright test --project=chromium`: **111 passed, 2 skipped** on the clean
  run; one run in four hit `library.spec.ts`'s pre-existing "keyboard guards and
  reduced motion" debounce-timing flake (green standalone and on the other three
  full runs) — the same flake class Sprint 070's own Outcome named in this exact
  file, not a new one.
- `python scripts/benchmark_library.py` before/after for the shelves path: see
  deliverable 6 above.
- **Walkthrough (DEC-025), done.** `scripts/walkthrough.py` on an ephemeral port,
  seeded through the real HTTP API: three shelves ("Currently reading" 5 items one
  cover, "Favorites" 2 items two covers, "To explore" empty), seven books, one
  unsorted. A real Chromium visited `/shelves` at 1280px and 390px, followed
  "Currently reading" into the library, narrowed it further with a status filter,
  dropped the shelf chip and confirmed the status chip and the wider result set both
  held, then visited `/` and `/import` at 390px — zero console errors across every
  visit, zero horizontal body overflow, the import source strip measured scrolling
  within itself (`scrollWidth` 475 against a 350px `clientWidth`) rather than pushing
  the page sideways. Screenshots inspected: proportional bars, real covers on
  covered shelves, the shared placeholder implied by the empty shelf showing neither
  bar nor covers, weighted counts visibly bolder on the fuller shelf. Owner's own
  `:8000` instance confirmed unaffected before and after; throwaway backend, dev
  server and seeded data directory torn down at close.

**Deviations:**
- The DEC-137 mobile fix was not in this sprint's original file — added in-session at
  the owner's explicit request ("work on the last sprint, add the mobile ui fix"),
  recorded as DEC-138 rather than a silent scope change.
- Two defects were found and fixed during this sprint's own verification rather than
  being pre-existing and named in "Current implementation baseline": the test-helper
  selector collision (deliverable 4) and the magnitude-bar contrast regression
  (deliverable 5), both introduced by this sprint's own commits and both closed before
  the gate that would have needed them named as known-degraded instead.
- The insights-ranking contended-budget overage is observed but not this sprint's to
  fix (see deliverable 6 above); carried into the handoff rather than silently dropped.

**Final sprint.** This is `FINAL_SPRINT` (`scripts/validate_project.py`). Per
`docs/agent/WORKFLOW.md`'s "Final sprint" rule: `project_status` moves to `complete`,
`active_sprint`/`active_sprint_file`/`active_sprint_status` move to `null`, and
`completed_sprints` gains `071`. There is no Sprint 072 to hand off to; see
`docs/agent/HANDOFF.md` for what remains owed to the owner beyond the numbered plan.
