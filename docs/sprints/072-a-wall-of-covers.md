# Sprint 072 — A wall of covers

**Status:** in_progress
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

_Not started._
