# Sprint 091 — Primitives

**Sprint:** 091
**Status:** completed
**Roadmap revision:** 45
**Depends on:** 090
**Owner:** Mauro

## Objective

Every control and loading state looks designed in both themes: no browser-default file input,
select or "Loading…" text remains, and pages compose shared primitives instead of hand-rolled
boxes.

## Required context

- [`../production-grade-proposal.md`](../production-grade-proposal.md) §2.1 D5–D9; DEC-167.
- `frontend/src/components/ui/` (button, dialog, popover, select, tabs, checkbox, input,
  textarea, command), `components/Panel*`, `App.tsx` (route fallback).

## Current implementation baseline

Measured after Sprint 090: 5 native `<select>`, 5 native `type="file"` inputs (Add, Import,
detail *Replace cover*, attachments), the route fallback and `DetailPage` say "Loading…", 18
`title=` tooltips, no Skeleton, EmptyState, Tooltip, DropdownMenu, Sheet or Kbd primitive.

## Deliverables

1. Primitives in `components/ui/`: `Skeleton`, `EmptyState` (the empty arch, a sentence, one next
   action), `Tooltip` (Radix), `Kbd`, `FilePicker` (a styled button and drop target over a hidden
   input, announcing the chosen file).
2. Every native `<select>` outside `ui/` uses `ui/select`; every file input uses `FilePicker`.
3. Skeletons replace "Loading…" on the route fallback, Detail, People, the cover dialog and
   attachments; library and shelf grids keep their cover pulse.
4. Empty states on Shelves, Insights cards and the empty library use `EmptyState`.

## Acceptance criteria

1. `grep` finds no `<select` and no `type="file"` outside `components/ui/`, and no "Loading…"
   text in a rendered state.
2. The file picker can be operated by keyboard, says which file is chosen, and still accepts a
   drop.
3. Existing behaviour tests pass unchanged except where they named the native control.

## Verification

Per DEC-167: `vitest related` on changed files, `make check`, the Playwright specs for the
screens changed (add, import, triage, detail), and screenshots of one changed control per theme.

## Explicit non-scope

Motion and the property-row detail page (092); the phone layout (093).

## Outcome

Delivered 2026-10-21. Verified per DEC-167: `primitives.test.tsx` (5), `vitest related` on every
touched file (220, then 219, then 67), `make check`, and the add/detail, import, triage, library,
accessibility and ebook browser specs (105). Screenshots: the file picker on Detail (Paper), the
select on Import (Ink), Shelves (Paper).

- **AC1.** `Skeleton`/`Loading`, `EmptyState`, `Kbd`, `Tooltip`, `NativeSelect`, `FilePicker` in
  `components/ui/`. No `<select` and no visible native file input outside `ui/`; the attachments
  input was already hidden behind its own button and stays. The add form's "Loading…" is a
  button's busy label, not a loading state, and stays.
- **AC2.** `FilePicker` keeps the real input focusable and labelled; the drawn button opens it.
- **AC3.** One test changed meaning on purpose: an empty library with books in the Inbox now says
  "3 waiting in your Inbox" with a way there (the 087 walkthrough's complaint).

**Deviation.** `NativeSelect` rather than Radix Select: the phone's own picker is the better
control, and Triage renders dozens per page. **Found:** an `aria-live` region anywhere on the page
stops a Radix modal hiding the rest of the page from assistive technology (the `aria-hidden`
library keeps live regions and their ancestors); `Loading` and `FilePicker` carry none. Two triage
specs pinned Ink-era colours and now run on Paper (Playwright's light default); 090 had not run
that spec. Tooltip and Kbd are built for the command bar (094) and not yet used.

Commit: `9e2853e`.
