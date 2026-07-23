# Sprint 013 — Library grid layout diagnosis and repair

**Status:** ready
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

_Not started. On completion record the reproduced failure and root cause, delivered behavior, commands and actual results, commit IDs, deviations/decisions, and impact on every future sprint._
