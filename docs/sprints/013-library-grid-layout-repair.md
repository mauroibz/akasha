# Sprint 013 — Library grid layout diagnosis and repair

**Status:** completed
**Depends on:** 012
**Roadmap revision:** 5

## Objective

Diagnose and repair the library grid view so book content and controls never overlap across supported viewport sizes, while preserving virtualization, keyboard behavior, and the table view.

## Required context

1. `AGENTS.md`
2. `docs/specs/product-spec.md` sections 5.1 (library) and 6 (non-functional requirements)
3. `docs/specs/technical-spec.md` sections 11 (frontend architecture), 12 (performance budgets), and 13 (accessibility)
4. `docs/decisions.md` DEC-017, DEC-021, and DEC-022
5. Sprint 012 Outcome and `docs/agent/WORKFLOW.md`
6. `frontend/src/pages/HomePage.tsx`, `frontend/src/features/library/VirtualLibrary.tsx`, `frontend/src/components/CoverImage.tsx`, and `frontend/src/components/ScorePicker.tsx`
7. `frontend/src/index.css`, `frontend/src/pages/HomePage.test.tsx`, `frontend/src/features/library/library.test.ts`, and `frontend/e2e/library.spec.ts`

## Diagnosed defect and current implementation baseline

The overlap is caused by the grid view's DOM and CSS contract in
`VirtualLibrary.tsx`, not by bad source data:

- The outer `article` declares exactly two columns, `128px 1fr`, but has three
  visual responsibilities: cover, metadata, and controls.
- Cover and metadata are nested together inside the first grid child, a flex
  button constrained to the 128px column. The grid-mode `CoverImage` has only
  `aspect-[2/3]`, with no explicit grid-mode width or height, while the adjacent
  metadata also needs space. They therefore compete inside a column intended to
  be cover-width.
- `EntryControls` becomes the second grid child. Its status select plus score
  control have intrinsic minimum widths. When the score picker expands it renders
  ten 32px buttons plus gaps (over 320px before the status control), but neither
  the controls container nor the grid defines wrapping/stacking behavior.
- Every grid item is still a full-width virtual row with a hard-coded 310px
  height. There is no responsive multi-column card grid despite the UI calling
  this mode “Grid”. Fixed virtual offsets cannot absorb wrapped or overflowing
  content, so overflow can paint over neighboring rows.

The defect is structurally most severe at narrow widths and when the score picker
is open, but the malformed cover/metadata placement exists at every width. Existing
tests prove only mounted-row count and keyboard behavior; they do not assert
spatial separation, long-content behavior, expanded controls, or responsive layout.

## Deliverables

- Encode the diagnosed failure with a deterministic browser test before changing implementation.
- Repair the library grid structure and responsive sizing in `VirtualLibrary.tsx` and related styles/components as evidence requires.
- Add regression coverage for card/content/control bounding boxes at representative mobile, tablet, and desktop widths, including long titles/authors and populated score controls.
- Preserve table layout, view-preference persistence, inline status/score editing, entry navigation, keyboard focus, lazy pagination, and bounded virtualization.

## Acceptance criteria

1. A failing browser regression test reproduces the diagnosed cover/metadata/control overflow, including the expanded score picker, before implementation and passes after the fix.
2. At 375px, 768px, and 1440px viewport widths, visible grid items remain within the library viewport and their cover, metadata, and controls do not overlap each other or adjacent items, including long title/author fixtures.
3. Grid view presents a coherent multi-column card layout where space permits and a readable single-column layout on narrow screens; resizing does not leave stale virtual positions or clipped controls.
4. Table view, grid/table preference persistence, entry navigation, inline status/score editing, keyboard shortcuts/focus, pagination, and the 5,000-entry mounted-row bound continue to pass.
5. The focused Playwright checks run in Chromium with no uncaught page errors; the repair introduces no horizontal page overflow at the tested widths.

## Required tests (TDD)

- Playwright: deterministic overlap reproduction using bounding-box assertions for covers, metadata, controls, cards, and adjacent virtual rows/cards.
- Playwright: responsive checks at 375x812, 768x1024, and 1440x900 with long metadata and both populated and empty covers.
- Playwright: grid/table toggle, resize, inline editing, entry navigation, and bounded 5,000-entry virtualization regressions.
- Component/unit tests only where layout calculation or responsive grouping is extracted into testable logic.

## Verification

Run and record:

```bash
python scripts/validate_project.py
make format
make check
make test
cd frontend && npm run test:e2e -- --project=chromium e2e/library.spec.ts
cd .. && make build
git diff --check
```

Also inspect the seeded grid in Chromium at 375px, 768px, and 1440px widths and record the observed layout in the Outcome. Browser verification is required; unit tests alone cannot complete this sprint.

## Explicit non-scope

- No broad visual redesign, new library features, or changes to product branding.
- No triage-page redesign unless shared component changes are required to prevent a verified regression.
- No performance/accessibility/security hardening beyond regressions directly affected by this repair (Sprint 014).
- No container, backup, or release work (Sprint 015).

## Commit checkpoints

1. `test: reproduce library grid overlap`
2. `fix: repair responsive virtual library grid`
3. `test: cover grid layout regressions across viewports`
4. final `docs(sprint-013): close sprint and hand off`

## Risks and decisions to surface

- The confirmed defect combines incorrect CSS grid placement, intrinsic control widths, and fixed-height virtualization; use computed layout and bounding boxes to select fixed versus measured sizing.
- A true multi-column virtual grid may require row grouping or lanes. Preserve stable keys, focus movement, pagination thresholds, and the mounted-DOM budget.
- Avoid screenshot-only assertions for overlap; use spatial assertions, with screenshots as review evidence if useful.

## Outcome

**Status:** completed 2026-07-23.

### Reproduced failure and root cause

`test: reproduce library grid overlap` (8f47088) added bounding-box assertions and failed for the
diagnosed reasons before any implementation change:

- `entry 1 cover width: expected >= 48, received 32` at all three widths — the grid cover had only
  `aspect-[2/3]` and shared the 128px grid column with the metadata block, so it collapsed to the
  intrinsic width of the placeholder glyph.
- `mobile: score panel x=286 y=616 w=338 h=64 escapes card x=20 y=493 w=335 h=310` — the expanded
  compact picker rendered ten 32px buttons in a non-wrapping flex row inside the `1fr` column.
- `desktop columns: expected >= 2, received 1` — grid mode was one full-width virtual row per entry.

### Delivered behavior

- `gridColumnCount` (`frontend/src/features/library/library.ts`) derives columns from the measured
  scroll-container width, capped at 4 and floored at 1, never below `cardMinWidth` 260px.
- `VirtualLibrary` virtualizes rows of cards: `count = ceil(entries / columns)`, fixed 300px row
  band (280px card + 20px gap), grid overscan 2, `ResizeObserver` on the scroll container, and
  `scrollToIndex(floor(entryIndex / columns))` for focus restoration.
- A card is a fixed box: 128x192 cover, `line-clamp` metadata, and an `h-11` control row whose status
  select absorbs free width so the score control cannot be pushed out.
- The compact `ScorePicker` expands into an overlay (`absolute bottom-full right-0 z-20`, two rows of
  five) anchored inside the card, so expanding never changes the card's layout box.
- Table mode keeps `role="table"`, its 84px fixed rows, overscan 4, and truncating metadata.

### Verification (actual results)

| Command | Result |
|---|---|
| `python scripts/validate_project.py` | passed |
| `make format` | clean, no residual changes |
| `make check` | ruff, prettier, eslint, mypy (33 files), tsc, OpenAPI export check, frontend type check, validator — all passed |
| `make test` | backend 122 passed; frontend 38 passed (8 files) |
| `npm run test:e2e -- --project=chromium e2e/library.spec.ts` | 8 passed |
| `npx playwright test --project=chromium` (full suite) | 33 passed, 2 skipped (pre-existing), 0 failed |
| `make build` | backend wheel/sdist built; frontend 343.79 kB JS (105.40 kB gzip), 19.21 kB CSS |
| `git diff --check` | clean |

### Chromium inspection (required browser check)

Seeded grid with one long-title/long-author fixture, score picker expanded on entry 1, screenshots
reviewed at each width:

| Viewport | Columns | Mounted rows | Mounted cards | Horizontal page overflow |
|---|---|---|---|---|
| 375x812 | 1 | 4 | 4 | 0px |
| 768x1024 | 2 | 5 | 10 | 0px |
| 1440x900 | 4 | 5 | 20 | 0px |

Observed layout: covers render at full 128x192 in every card, long titles clamp to three lines and
long authors to two, the status select shrinks instead of overflowing, and the expanded score panel
sits over its own card's cover area without touching any neighbor. Table mode at 1440 renders
unchanged single-line rows with the full long title visible.

### Commits

- `8f47088` test: reproduce library grid overlap
- `64f3cf9` fix: repair responsive virtual library grid
- `6aac5c5` test: cover grid layout regressions across viewports
- closing documentation/state commit

### Deviations and decisions

- **DEC-023.** The mounted-DOM budget is now expressed as two bounds — mounted virtual rows under 20
  (unchanged) and mounted cards under 48 — because a grid row mounts `columns` cards. The existing
  e2e assertion on `data-mounted-count` was kept at `< 20`; the card-count assertion was moved from
  `< 20` to `< 48` and grid overscan reduced from 4 to 2 to keep the budget tight. No test was
  weakened in intent: the DOM is still bounded and still asserted after deep scrolling.
- The technical spec's frontend section gained an explicit grid-virtualization and card-box contract.
- Non-behavioral `data-card-cover` / `data-card-meta` / `data-card-controls` / `data-score-panel`
  test hooks were added so spatial assertions can address layout regions directly.
- No API, schema, or product-behavior change.
