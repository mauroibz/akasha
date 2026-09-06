# Sprint 072 — A wall of covers

**Status:** completed
**Depends on:** 071
**Roadmap revision:** 39

> Planned from [`../readability-proposal.md`](../readability-proposal.md) §1.1, §2 rules 8–10
> and §3.1. **Accepted by the owner as DEC-139.**

## Objective

The library shows covers at the size a library of covers deserves, states how big it is, and
spends about half the chrome it spends today — with fixed-size virtualization intact.

Measured targets, at the same three viewports the proposal measured: the first cover starts
**≤200px** down the document at 1440×900 (338px today) and **≤300px** at 390×844 (509px today);
the cover is **≥70%** of the card's area (31% today); and a 2560px window shows **≥6 columns**
(4 today).

## Required context

- [`../readability-proposal.md`](../readability-proposal.md) §1.1 findings 1–7, §2 rules 8–11,
  §3.1, §5.1 (the alternatives that were rejected and why), §7 (risks).
- `docs/decisions.md` **DEC-023** — the virtualization contract. This sprint moves its numbers
  and keeps its rule: a virtual row is one fixed-height band of fixed-height cards, the column
  count is derived from the measured container width, and the compact score picker expands as an
  overlay that stays geometrically inside its card. Read DEC-023 before touching `gridLayout`.
- `docs/decisions.md` DEC-026 (tokens and the score ramp), DEC-065 (the library always names one
  domain — the strip stays), DEC-136/DEC-137 (the `PageHeader`, `SegmentedControl` and
  `DomainStrip` primitives this sprint rearranges rather than replaces).
- `docs/specs/technical-spec.md` §8 (virtualization and motion contracts).
- Code, read fresh — not from this file's summary:
  - `frontend/src/features/library/library.ts:98-122` — `gridLayout`, `gridRowHeight`,
    `tableRowHeight`, `gridColumnCount`.
  - `frontend/src/features/library/VirtualLibrary.tsx` — all of it, especially `renderEntry`
    (`:239-306`), the region markers `data-card-cover` / `data-card-meta` / `data-card-controls`,
    and the `scrollMargin` measurement at `:162-180`.
  - `frontend/src/pages/HomePage.tsx:549-581` (header), `:587-643` (search), `:648-752`
    (controls), `:760-825` (the active-filter chips), `:887` (`total`, currently spent only on
    `aria-setsize`).
  - `frontend/src/components/ScorePicker.tsx` — the compact trigger and its in-card overlay.
  - `frontend/src/components/StatusSelect.tsx`, `frontend/src/components/CoverImage.tsx`.
- Tests: `frontend/src/features/library/library.test.ts` (asserts column count against the
  constants, so it moves with them by construction),
  `frontend/src/pages/HomePage.test.tsx`, `frontend/e2e/library.spec.ts` (the named tests below),
  `frontend/e2e/accessibility.spec.ts`.

## Current implementation baseline

Measured 2026-09-05 against the owner's running instance through Playwright:

- 1440×900: the first card's top is at `y=338`. Cards are 281×280 with a fixed 128×192 cover, so
  the metadata column is `281 − 32 − 128 − 16 = 105px` and about 90px of it is blank between the
  year and the controls.
- 390×844: the first card's top is at `y=509` — 60% of the viewport.
- 2560×1400: still 4 columns (`gridLayout.maxColumns`), first card at `x=688`, so 54% of the
  window is margin.
- The score is `h-9 … text-sm` beside a `flex-1` status select; the select is the widest control
  on the card.
- `total` reaches `aria-setsize` and nothing else. Nothing on screen says how many entries the
  library holds or how many a filter matched.
- Table mode is 84px rows carrying the same cover, select and chip — the card unrolled, not a
  denser mode.

## Deliverables

1. **One geometry block.** `gridLayout` gains a cover height and loses nothing: card minimum
   width ~190px, a pinned cover height (~300px), a card height that is cover + text block, and
   `maxColumns` 6. The page container grows from `max-w-7xl` to ~1600px. `gridColumnCount` keeps
   its shape — it reads the measured width and the constants, so its test moves with it.
2. **The vertical card.** Cover on top at the full card width (`object-cover` against the pinned
   height, so the poster crops rather than the row resizing), then the title on two lines at the
   full card measure, the creator, and one quiet line for year and formats.
3. **The score in the corner.** A ≥44px chip in the DEC-026 ramp, ~20px numeral, on a scrim at
   the foot of the cover, and it is still the `ScorePicker` trigger with its overlay contained
   inside the card (DEC-023, and `library.spec.ts`'s picker-containment test must keep passing
   untouched).
4. **The status pill beside it**, on the same scrim, still the `StatusSelect` with its full
   vocabulary and a ≥44px target. **Neither control is hover-revealed**: both are in the DOM and
   visible at rest, on every pointer type.
5. **One command bar.** The brand lockup, the domain strip, the search field and the density
   toggle in a single sticky row; sort, shelf, format and status collapse into one *Filters*
   control carrying a count when any is set. The Sprint 071 chips stay and become the only place
   a set filter is stated.
6. **The library states its size.** `firstPage.total` rendered at ~`text-3xl` tabular beside the
   domain, and as "18 of 342" when a filter narrows it.
7. **A dense second density.** The `List` mode becomes ~56px rows (32×48 cover, title, creator,
   year, formats, status, score chip) — about 16 rows in a 900px viewport against today's 9.
8. **The mounted-DOM budget re-measured, not assumed.** Both row heights changed, so DEC-023's
   two bounds (<20 rows, <48 cards) are measured again at 10,000 entries and the numbers go in
   the Outcome.

## Acceptance criteria

1. At 1440×900 the first card's `getBoundingClientRect().top + scrollY` is ≤200; at 390×844 it is
   ≤300. Both measured in `library.spec.ts`, not asserted in prose.
2. The cover region's area is ≥70% of its card's area at 390, 768 and 1440.
3. Columns: 1 at 390, ≥5 at 1440, ≥6 at 2560, and reflow between them leaves no overlapping card.
4. The score chip's box is ≥40×40 CSS px with a computed font size ≥18px; the status control's
   target is ≥44px; both are visible with no pointer over the card and reachable by keyboard.
5. A card's controls may overlap its cover (they sit on it by design) but never its metadata,
   never escape the card box, and no two cards overlap. `library.spec.ts`'s
   "grid cards keep cover, metadata and controls separated" test is **rewritten to this rule** and
   the change is named in the Outcome.
6. DEC-023's bounds hold at 10,000 entries in both densities: fewer than 20 mounted rows, fewer
   than 48 mounted cards.
7. The library shows its total; with a filter set it shows both numbers; the value equals the
   `total` the response carried.
8. List density renders ≥14 rows in a 900px-tall viewport.
9. The expanded score picker still stays geometrically inside its card at every width — the
   existing test passes **unchanged**.
10. `/` holds at 390px with no horizontal body scroll, 44px targets, and zero serious axe
    violations in both densities.
11. Every other component and e2e suite passes unchanged. Any test that does change is named in
    the Outcome with the finding it was asserting.

## Required tests (TDD)

| Behavior | Layer | File |
|---|---|---|
| `gridColumnCount` yields 1/≥5/≥6 at 390/1440/2560 against the new constants | unit | `library.test.ts` |
| A card renders cover, title, creator and the year/format line, in that order | component | `HomePage.test.tsx` |
| The score chip is the picker trigger and carries the ramp class for its band | component | `HomePage.test.tsx` |
| The library states its total, and both numbers when filtered | component | `HomePage.test.tsx` |
| Filters collapse into one control that counts what is set; chips still clear individually | component | `HomePage.test.tsx` |
| First cover ≤200px down at 1440, ≤300px at 390 | e2e | `library.spec.ts` |
| Cover ≥70% of card area at three widths | e2e | `library.spec.ts` |
| Controls overlap the cover but not the metadata; no card overlaps another | e2e | `library.spec.ts` |
| Mounted rows <20 and cards <48 at 10k, both densities | e2e | `library.spec.ts` |
| List density shows ≥14 rows at 900px height | e2e | `library.spec.ts` |
| Score and status are visible without hover and reachable by keyboard | e2e | `accessibility.spec.ts` |
| Zero serious violations on `/` in both densities | e2e | `accessibility.spec.ts` |

## Verification

- `make check`, `make test`, `python scripts/validate_project.py`.
- `npx playwright test` — the whole suite, not only the library spec.
- No backend change, so no `openapi` regeneration and no `benchmark_library.py` run is owed.
- **Walkthrough (DEC-025):** a throwaway seeded backend with real covers on most entries and none
  on a few (the Sprint 067 discipline), driven at 390×844, 1440×900 and 2560×1400. Record what
  the wall actually looked like, what the crop did to a wide poster, and whether the scrim keeps
  the chip readable over a light cover. **The owner's own instance on `127.0.0.1:8000` is not to
  be pointed at.**

## Explicit non-scope

- Insights (Sprint 073) and shelves (Sprint 074), including the shelf card's cover rail.
- Masonry or natural-aspect covers. That ends fixed-size virtualization; §5.1 rejected it.
- A cover-only third density. Offered in §3.1 as optional and deliberately not scheduled.
- New filters, a light theme, a second accent, any new dependency.
- Detail, Add, Import and Triage. Sprint 070 settled their shapes.

## Commit checkpoints

1. `[MOD] Give the card its cover back`
2. `[MOD] Put the score where the eye lands`
3. `[MOD] One bar above the library, not four`
4. `[ADD] Say how big the library is`
5. `[MOD] Make the second density actually denser`

## Risks and decisions to surface

- **This is the one virtualized surface in the product.** Change `gridLayout` and the card in one
  commit, run `library.spec.ts` before any cosmetic follow-up, and keep the axe and 390px checks
  inside this sprint.
- **`object-cover` crops.** A poster with its title at the edge can lose a few pixels at the
  widest column. Centre the crop; do not make the cover height flexible.
- **Controls on artwork is the classic contrast failure.** Use an opaque backing, not a tint —
  the same repair Sprint 071 made on the shelf row's Delete button — and let axe check it with a
  light cover behind.
- **A collapsed Filters control can hide state.** The chips are what prevent that; if the popover
  and the chips ever disagree, the chips are right.
- **The sticky bar and `scrollMargin`.** The window virtualizer measures where the list starts; a
  sticky header that changes height on scroll would move it. Keep the bar's height constant.

## Outcome

Delivered as planned, frontend only. Commits, in order:

1. `edc1fe3` [MOD] Repin the grid and container to Sprint 072 geometry — `gridLayout`:
   `cardMinWidth` 190, `coverHeight` 300, `textHeight` 112 (96 was the plan's placeholder; the
   two-line title plus creator and year/format line measured wider, named here as the deviation
   deliverable 1 owed), `cardHeight = coverHeight + textHeight`, `maxColumns` 6, container
   `max-w-[1600px]`.
2. `565e6aa` [MOD] Give the card its cover back, and its score where the eye lands — the vertical
   cover-first card, the `ScorePicker`/`StatusSelect` pair riding an opaque scrim on the cover
   (deliverables 2–4).
3. `060792a` [MOD] Put one bar above the library and state its size — the sticky command bar,
   sort/shelf/format/status collapsed into one **Filters** popover, the chips as the sole record
   of active state, and `firstPage.total` / "N of M" (deliverables 5–6). The plan assumed summing
   `facets.status_counts_by_type[domain]` gave the unfiltered denominator; validation showed that
   sum is filtered by whatever shelf/query/format is also set, so it silently produced the wrong
   `M` under those filters. Fixed with a `limit=1` companion query (`wholeLibrary`,
   `frontend/src/pages/HomePage.tsx:290-303`) that reads the true per-domain total from its own
   response, fetched only when a filter is active.
4. `3bacbc3` [MOD] Make the second library density honestly dense — `tableRowHeight` 52 (net; the
   sprint file's own baseline table row was already 84px, called out at variance in the plan
   itself), 32×48 covers, 44px status/score targets, overscan reduced to 2 (deliverable 7).
5. `e3aeacb` [FIX] Keep the real command bar above the fold — moved the Filters trigger into the
   command row itself (it had drifted into the second, conditionally-empty row) and stopped that
   row from rendering when no chip is set, which is what the 1440×900/390×844 fold measurements
   below depend on.
6. This session (no separate commit list beyond the closing one below): three e2e tests fixed, all
   named under "Tests changed" below, and this Outcome/DEC/state/worklog/HANDOFF reconciliation.

### Acceptance criteria

1. First card top ≤200px at 1440×900, ≤300px at 390×844 — held (`library.spec.ts` "the wall
   starts near the top…").
2. Cover ≥70% of card area at 390/768/1440 — held (measured 72.8% in the realistic walkthrough,
   asserted in `library.spec.ts`).
3. Columns 1/≥5/≥6 at 390/1440/2560, no overlap on reflow — held
   (`library.spec.ts` "the wall reaches one, five, and six columns…").
4. Score chip ≥40×40 with ≥18px numeral; status target ≥44px; both visible at rest and keyboard
   reachable — held (`accessibility.spec.ts` "wall-card score and status controls…").
5. Controls may overlap the cover, never the metadata, never escape the card, no card overlaps
   another — held; `library.spec.ts`'s containment test was **rewritten** to this rule, as
   anticipated by the sprint file (see Tests changed).
6. DEC-023's mounted-DOM bounds hold at 10,000 entries in both densities — held. Freshly measured
   this session: grid 7 rows / 35 cards, table 19 rows / 19 cards, grid+web-results 35 cards,
   crossfade peak 4 rows / 20 cards / 1 container — all inside <20 rows / <48 cards. (These are
   viewport-dependent counts, not fixed constants; the worklog's earlier 6/30 sample from the same
   suite is the same bound read at a different column count, not a regression.)
7. The library shows its total, and both numbers filtered, equal to the response's `total` — held,
   via the companion query described above.
8. List density ≥14 rows in a 900px viewport — held, measured 15 visible rows.
9. The expanded score picker stays inside its card at every width, test **unchanged** — held.
10. `/` holds at 390px, no horizontal scroll, 44px targets, zero serious axe violations in both
    densities — held.
11. Every other suite passes unchanged except the tests named below.

### Tests changed (AC5/AC11)

- `frontend/e2e/library.spec.ts` — "grid cards keep cover, metadata and controls separated"
  rewritten to "grid cards keep controls on the cover and off the metadata", per AC5 above.
  Anticipated by the sprint file.
- `frontend/src/features/library/library.test.ts` — column-count expectations moved with the new
  `gridLayout` constants. Anticipated by the sprint file.
- `frontend/e2e/library.spec.ts` "reduced motion reaches the animations no stylesheet can touch" —
  was missing the `openFilters(page)` call every neighboring test in the file uses now that sort
  lives inside the Filters popover; added. Pre-existing since the D5 commit, only surfaced when
  this session ran the deferred exhaustive gate.
- `frontend/e2e/formats.spec.ts` "the status filter offers the chosen domain's vocabulary…" — after
  switching domains, the test reopened the Filters popover only `if (!(await status.isVisible()))`.
  The domain radio sits outside the popover, so Radix closes Filters on that click, but the status
  combobox can still read `isVisible() === true` for one more tick while its exit animation runs —
  a real race, reproduced 3/3 in isolation before the fix. Rewritten to wait for the Filters
  trigger's own `data-state="closed"` (which settles deterministically, confirmed by direct
  instrumentation) before unconditionally reopening it.
- `frontend/e2e/accessibility.spec.ts` "library in table view has no serious accessibility
  violations" — measured the score chip's height immediately after switching to Table view, which
  can land mid-entrance-animation (observed as low as 42.5px against the 44px target, settling to
  exactly 44px within ~300ms). Added a wait for `document.getAnimations().length === 0` before
  measuring, the same signal `e2e/motion.ts`'s sampler already trusts elsewhere in this suite.

None of the four fixes above touched application code — all four were latent test races or
omissions in this sprint's own new coverage, found only because the exhaustive gate that surfaces
them had been deferred past the implementation session. Each reproduced reliably in isolation
before its fix and passed 3-5/5 repeats after.

### Verification

- `make check` — green.
- `make test` — backend 1356 passed, frontend (Vitest) 279 passed.
- `npx playwright test` (full suite, both `chromium` and the serial `heavy-library` project) — 124
  passed, 2 skipped, 0 failed, after the four test fixes above. A first exhaustive run surfaced
  those four failures; each was root-caused (not assumed transient) before being fixed, and the
  full suite was rerun clean afterward.
- `python scripts/validate_project.py` — passed, both standalone and inside `make check`.
- Walkthrough (DEC-025): carried from the prior session's realistic run against a fresh throwaway
  backend (20 API-created books, 19 generated covers, one missing) — never the owner's own
  instance. Wall top 293px/144px/144px at 390/1440/2560; columns 1/6/6; cover area 72.8%; dense
  table 15 visible rows; no horizontal body overflow or console errors; score/status persisted;
  filtering showed the correct `3 of 20`. The 3:1 poster centre-cropped strongly to the pinned
  frame, as specified; the opaque backing kept controls readable over a near-white cover. Not
  rerun this session because no application code changed after that walkthrough — only e2e test
  files were touched to close the deferred gate.

### Known, out-of-scope defect recorded by the walkthrough (not fixed here)

Immediately after an inline status change, the Filters popover's status option kept its stale
facet label (e.g. `To read 4`) until a reload, even though the filtered response and the visible
total were correctly `3 of 20`. This is a cache-invalidation gap in the facet counts, not in the
total this sprint's AC7 owns, and touches no file this sprint's diff reaches. Carried forward in
`docs/agent/HANDOFF.md`'s known-degraded list for whichever sprint next touches the status facet
query, or a dedicated one if none does soon.
