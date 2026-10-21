# Sprint 092 — Motion, and the detail page as property rows

**Sprint:** 092
**Status:** in_progress
**Roadmap revision:** 45
**Depends on:** 091
**Owner:** Mauro

## Objective

Things move with intent: a cover grows into its detail page and back, pages and lists enter
rather than appear, presses and drags answer the hand, and the brand's arch-and-dot appears where
the app waits or is empty. The detail page's reading data becomes the Notion-like property rows the
owner approved in the mock (DEC-165), replacing the rejected index card.

## Required context

- [`../production-grade-proposal.md`](../production-grade-proposal.md) §2.1 D3, D4, §3.2; DEC-165.
- The mock's Motif and Detail boards: https://claude.ai/artifact/KRWdo67P7QfirBsBK4mdRa
- `frontend/src/components/AppShell.tsx` (`LazyMotion features={domAnimation} strict`),
  `frontend/src/lib/motion.ts`, `features/library/VirtualLibrary.tsx` (cards), `pages/DetailPage.tsx`,
  `components/ScorePicker.tsx`, the drop zones in `features/import/` and `features/add/`.
- DEC-023 (mounted-DOM budget), the reduced-motion specs in `e2e/library.spec.ts`.

## Current implementation baseline

`domAnimation` excludes layout animation, so `layoutId` cannot work; no `active:` press states; no
drag-over state on drop zones; Detail's reading data is a bordered two-column grid.

## Deliverables

1. `domMax` instead of `domAnimation`; the cover shares a `layoutId` between the library card and
   the detail page, both directions, 260 ms, one ease-out curve.
2. Route content fades and rises 8 px on entry; press feedback (`active:scale-[0.98]`) on cards and
   buttons; drop zones show a drag-over state.
3. The arch motif: the breathing dot on the route skeleton; the score settles once when chosen.
4. Detail: *Your reading data* as property rows (muted label with icon, plain value, hover fill,
   click to edit in place where the field is editable today), status and shelves as soft pills,
   the note as a callout marked with the arch.
5. Everything off under `prefers-reduced-motion`.

## Acceptance criteria

1. Opening a book from the grid animates its cover into the detail cover; Back reverses it.
2. Reduced motion: no transform animation anywhere (the existing reduced-motion specs pass).
3. The DEC-023 mounted-DOM bounds still hold.
4. Every value editable on Detail before is still editable; nothing new is editable.

## Verification

Per DEC-167: `vitest related`, `make check`, the library, detail and accessibility specs, and
screenshots of Detail in both themes.

## Explicit non-scope

Phone layout (093). New editable fields.

## Outcome

_Not started._
