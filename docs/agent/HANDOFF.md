# Handoff — current reality

**Last completed:** Sprint 013 (library-grid-layout-repair), 2026-07-23.
**Next:** Sprint 014 (scale-accessibility-resilience) — status `ready`, file at
`docs/sprints/014-scale-accessibility-resilience.md`.

## What the library looks like now

- Grid mode is a real multi-column card grid. `gridColumnCount`
  (`frontend/src/features/library/library.ts`) derives the column count from the measured scroll
  container: 1 column at 375px, 2 at 768px, 4 at 1440px, never below a 260px card.
- `VirtualLibrary` virtualizes rows of cards, not entries: `count = ceil(entries / columns)`, a fixed
  300px band holding fixed 280px cards, grid overscan 2, table overscan 4.
- A card is a fixed box — 128x192 cover, clamped metadata, a non-wrapping `h-11` control row. The
  compact score picker expands into an overlay anchored inside the card, so expanding a control never
  changes the card's layout box.
- Table mode is unchanged: `role="table"`, 84px fixed rows, truncating metadata.
- `frontend/e2e/library.spec.ts` now holds spatial regressions at 375/768/1440, an expanded-picker
  containment check, a resize/reflow check, and a grid/table editing-and-persistence check.

## Next-agent boundary

- Mounted-DOM budget is two bounds (DEC-023): mounted virtual rows `< 20` and mounted cards `< 48`.
  Benchmark Sprint 014 against both; do not collapse them back into a single row count.
- Accessibility work must keep the compact score picker as an overlay. In-flow expansion is the exact
  defect Sprint 013 repaired.
- Sprint 014 extends the grid coverage rather than replacing it.
- Container/release remains Sprint 015.

## State

- Planning revision 5; state points to Sprint 014, project status `ready`.
- Sprint 013 gates were green: `make check`, `make test` (backend 122, frontend 38), full Chromium
  suite 33 passed / 2 pre-existing skips, `make build`, `git diff --check` clean.
- Commit messages in this repository carry no `Co-Authored-By` trailer.
