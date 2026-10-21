# Sprint 092 — Motion, and the detail page as property rows

**Sprint:** 092
**Status:** completed
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

Delivered 2026-10-21. Verified per DEC-167: Detail unit tests (31, one new), `vitest related` on
each slice (168, 200), `make check`, and the add/detail, editorial, formats, accessibility, auth
and library browser specs. A real Chromium confirmed one view transition opening a book and one on
Back, with a frame captured mid-morph; screenshots of Detail in both themes.

- **AC1.** The cover morphs from card to detail and back. **Deviation:** the browser's View
  Transitions API rather than Motion's `layoutId`/`domMax`. React Router's `viewTransition` needs
  its data router, so `lib/viewTransition.ts` starts the transition around a `flushSync`
  navigation; Detail starts from the list's cached entry (`placeholderData`) and is no longer
  lazy, so its cover exists in the first frame. Firefox without the API navigates plainly.
- **AC2.** Reduced motion turns off view transitions, the route fade, button press and the
  breathing mark (CSS block plus the helper's own check).
- **AC3.** Library spec's DEC-023 bounds pass.
- **AC4.** Property rows open the same opinion dialog; the Change button sits inside `dd`, named by
  `aria-label` and worded by CSS, so the definition list stays valid and `dd` text is the value.

Also: buttons scale while pressed; drop zones already had a drag-over state (the proposal's D4
overstated that) and now lift and tint more; pages fade in (opacity only); the whole-page skeleton
shows the breathing mark. **Found:** a route animation with a fill mode stays in
`document.getAnimations()` after finishing, which the accessibility spec polls; and 091's
`EmptyState` drew its title as a paragraph, which the auth spec (not run in 091) caught; it is a
heading now. The score's settle animation already existed (`commitPop`).

Commits: `5d1cc25`, `6488cef`, and the property-row commit.
