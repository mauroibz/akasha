# Sprint 093 — The phone pass

**Sprint:** 093
**Status:** in_progress
**Roadmap revision:** 45
**Depends on:** 092
**Owner:** Mauro

## Objective

At 390px Akasha is a phone app: the library header fits in one short band, the grid shows two
covers a row, dialogs rise as bottom sheets, and the mark (activity) and Settings are in the
phone's own top bar. This is the PhoneLibrary board of the approved mock.

## Required context

- [`../production-grade-proposal.md`](../production-grade-proposal.md) §2.2 A6; DEC-165, DEC-167.
- The mock's PhoneLibrary boards; `components/AppShell.tsx` (phone header is auth-only since 090),
  `pages/HomePage.tsx` (the sticky header), `features/library/VirtualLibrary.tsx` (`gridLayout`),
  `components/ui/dialog.tsx`, `e2e/library.spec.ts` (column counts, "first cover at 390px").

## Current implementation baseline

Measured at 390×844 on a copy of the owner's data: the library header takes about 280px (lockup,
domain tabs, search, Search/Grid/Table/Filters, Inbox/Add on four rows); the grid is one column, so
one cover fills the screen; there is no Settings entry or activity indicator without auth.

## Deliverables

1. A phone top bar on every page: the mark (the activity control) and Settings, plus the account
   control when signed in.
2. The library header at <640px: one row of domain chips scrolling sideways, then search with the
   view/filter controls as icon buttons beside it; Inbox and Add move into that row or the bar.
3. Two grid columns at 390px (cover and title only, controls on the cover as today).
4. Dialogs as bottom sheets under 640px.

## Acceptance criteria

1. At 390px the first cover starts within 300px of the top (the library spec's bound) with the new
   top bar, and two covers sit side by side.
2. Every control reachable at 1440px is reachable at 390px.
3. Desktop layout unchanged (the library spec's 1440px column counts).

## Verification

Per DEC-167: `vitest related`, `make check`, the library, accessibility and triage specs, and
390px screenshots of Library, Detail and a dialog.

## Explicit non-scope

The command bar (094) and the share target (097).

## Outcome

_Not started._
