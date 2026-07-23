# Handoff — current reality

**Last completed:** Sprint 012 (bulk-first-triage), 2026-07-22.
**Next:** Sprint 013 (library-grid-layout-repair) — status `ready`, file at
`docs/sprints/013-library-grid-layout-repair.md`.

## Diagnosed issue

- `VirtualLibrary` calls the mode a grid but renders one full-width, fixed-height virtual row per
  entry; there is no responsive multi-column card layout.
- The grid article declares `grid-cols-[128px_1fr]` but cover and metadata share the first 128px
  grid child. The grid-mode cover has an aspect ratio but no explicit width/height.
- Status and score controls occupy the second grid cell without wrapping. Expanded score editing
  alone needs more than 320px for ten buttons, so controls overflow at constrained widths.
- Fixed 310px virtual offsets allow overflowing/wrapped content to paint into adjacent entries.

## Next-agent boundary

- Start with a failing Playwright spatial regression, including the expanded score picker and long
  metadata, then implement the smallest coherent responsive/virtualization repair.
- Preserve table mode, preference persistence, editing/navigation/keyboard behavior, pagination,
  and the 5,000-entry mounted-DOM bound.
- Browser-check 375px, 768px, and 1440px widths. Unit tests alone cannot close the sprint.
- Hardening is now Sprint 014; container/release is Sprint 015 (DEC-022).

## State

- Planning revision 5 points to Sprint 013; no Sprint 013 implementation has started.
- Sprint 012's recorded quality gates were green. Re-run the Sprint 013 required checks during work.
