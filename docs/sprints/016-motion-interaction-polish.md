# Sprint 016 — Motion and interaction polish

**Status:** planned
**Depends on:** 015
**Roadmap revision:** 6

## Objective

The interactions the product spec identifies as carrying the feel are implemented, and the
application responds to every action instantly and legibly.

## Required context

1. `AGENTS.md`, including the walkthrough gate in section 3
2. `docs/specs/product-spec.md` section 7, specifically "Microinteractions worth building",
   "Rendering at scale", and "Interaction notes"
3. `docs/specs/technical-spec.md` section 8, specifically the crossfade and optimistic-mutation
   contracts and the reduced-motion token requirement
4. `docs/decisions.md` DEC-023, DEC-024, and DEC-026
5. Sprint 013 Outcome (grid contract) and Sprint 015 Outcome (token and component inventory)
6. `frontend/src/features/library/VirtualLibrary.tsx`, `frontend/src/components/ScorePicker.tsx`, `frontend/src/components/CoverImage.tsx`, and `frontend/src/pages/AddPage.tsx`
7. `frontend/src/index.css` reduced-motion block and `frontend/e2e/library.spec.ts` reduced-motion assertion

## Current implementation baseline

`motion` v12 is a dependency and, as of Sprint 015, still imported zero times. Every
microinteraction listed in product spec section 7 is unimplemented: the score picker has no
hover fill, spring, or colour shift; sort and filter changes swap content with no transition;
add-flow results appear without stagger and the selected card does not animate into place;
optimistic writes have no failure feedback; covers pop in without a blur-up.

The `prefers-reduced-motion` block in `index.css` currently guards animations that do not exist.
`frontend/e2e/library.spec.ts` asserts computed `transitionDuration` is effectively zero under
reduced motion, so that assertion passes vacuously today and becomes meaningful in this sprint.

Technical-spec section 8 already fixes the hard constraint: "Sort/filter changes crossfade the
container; rows do not use layout animations." Product spec section 7 gives the same rule and its
reason — layout animations fight the virtualizer, because rows unmount as they scroll out and
re-animate on return.

## Deliverables

- Score picker: fill animates on hover, spring on commit, and colour shifts across the DEC-026
  ramp (red-400 through emerald-400) as the value changes.
- Sort and filter crossfade at the **container** level, keyed on the active sort and filter set,
  implemented with `AnimatePresence` on the list container only.
- Add flow: search results stagger in; the selected card animates into place rather than
  navigating abruptly, per product spec section 7.
- Optimistic writes: instant local render, background reconcile, and a shake on rollback. No
  spinner for a local database write.
- Cover load: blur-up or skeleton in `CoverImage.tsx` with no layout shift, preserving the fixed
  128x192 grid cover box.
- Action bar and dialog spring transitions — surfaces that do not scroll.
- Reduced-motion handling through Motion's hook, with the existing `index.css` media block
  retained as the CSS-level backstop.

## Acceptance criteria

1. Each microinteraction listed in product spec section 7 is implemented and demonstrable in a
   browser.
2. No row-level `layout` prop or per-row enter/exit animation exists in any virtualized list.
   Crossfade is applied to the list container only, keyed on sort and filter.
3. Under `prefers-reduced-motion: reduce`, every animation is disabled or reduced to an
   imperceptible duration, and every flow remains fully usable. The existing reduced-motion
   assertion in `frontend/e2e/library.spec.ts` passes non-vacuously.
4. The Sprint 013 grid contract holds unchanged after animation is added: mounted virtual rows
   under 20, mounted cards under 48, correct column counts at 375/768/1440, no region overlap,
   and the expanded score panel still contained inside its card.
5. A failed score or status write visibly rolls back with a shake and announces an accessible
   error; the user's input is never silently lost.
6. Scrolling a 5,000-entry library remains smooth; animation is not applied to scroll-driven
   mounting and unmounting.
7. The full Chromium e2e suite passes with no uncaught page errors.

## Required tests (TDD)

- Reduced motion: with the media feature forced, computed transition and animation durations on
  animated surfaces are effectively zero, and add, score, and delete flows still complete.
- Rollback: a mocked failing `PATCH` leaves the prior value rendered, announces an error, and
  applies the failure treatment.
- Virtualization budget: both DEC-023 mounted-DOM bounds re-asserted with animation enabled.
- Crossfade: changing sort re-keys the container once rather than animating individual rows;
  assert no per-row animation is registered.
- Cover: an image that loads late causes no layout shift in the card box.

## Verification

Run and record:

```bash
python scripts/validate_project.py
make format
make check
make test
cd frontend && npm run test:e2e -- --project=chromium
cd .. && make build
git diff --check
```

Then perform the mandatory walkthrough required by `AGENTS.md` section 3 and record it in the
worklog. In a browser, score a book from the list and from detail, change sort and filter
repeatedly, search and add a book, force a write failure, and scroll a large library hard. Repeat
the pass with reduced motion enabled at the OS or DevTools level. Record which interactions feel
right, which feel slow or excessive, and any dropped frames observed while scrolling. Command
output alone cannot complete this sprint.

## Explicit non-scope

- No new screens, routes, or component primitives (Sprint 015 closed that surface).
- No performance benchmarking against documented budgets, axe automation, or security limits
  (Sprint 017). Scroll smoothness here is qualitative.
- No container, backup, or release work (Sprint 018).
- Do not reintroduce in-flow expansion of the score picker; it stays an in-card overlay per
  DEC-023, and animating it must not change the card's layout box.
- Do not add layout animation to virtualized rows under any framing.

## Commit checkpoints

1. `feat: animate the score picker with the score ramp`
2. `feat: crossfade the library container on sort and filter change`
3. `feat: stagger add results and animate selection into place`
4. `feat: add optimistic rollback feedback`
5. `feat: blur up covers without layout shift`
6. `test: assert reduced motion and virtualization budgets under animation`
7. final `docs(sprint-016): close sprint and hand off`

## Risks and decisions to surface

- Motion increases bundle size. Record the delta against the Sprint 013 baseline of 343.79 kB JS
  (105.40 kB gzip) and flag it if the growth is material.
- Crossfading a container whose children are absolutely positioned by the virtualizer can produce
  a visible jump. If a clean crossfade proves incompatible with virtualization, record that and
  prefer no animation over a broken one.
- Animated components mount extra nodes; if the mounted-card bound tightens, report the measured
  number rather than relaxing DEC-023.
- Decide whether the shake on rollback is Motion-driven or CSS keyframes, given the reduced-motion
  requirement applies either way.

## Outcome

_Not started. On completion record delivered behavior, commands and actual results, commit IDs,
deviations/decisions, and impact on every future sprint._
