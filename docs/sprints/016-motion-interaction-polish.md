# Sprint 016 — Motion and interaction polish

**Status:** completed
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

**Status: completed 2026-08-11.**

### Delivered

`motion` is imported for the first time since it became a dependency in Sprint 004. Every
microinteraction in product-spec section 7 exists, and two of them are named honestly as something
narrower than the spec's wording rather than filed as done (see Deviations).

- **Score picker.** The trigger transitions across the DEC-026 ramp; hovering *or focusing* a
  segment previews that band on both the segments and the trigger without committing; a committed
  value overshoots and settles on the trigger, which is the element that survives the commit. The
  panel enters and has no exit, because its disappearance is the confirmation that the commit
  landed. Measured in the running application: unscored `rgb(161,161,170)`, hovering 2
  `rgb(248,113,113)` (red-400), hovering 9 `rgb(53,211,153)` (emerald-400).
- **Container crossfade** on sort and filter change, `AnimatePresence mode="wait"` keyed on
  `libraryMotionKey` (DEC-031). No row animates; that is enforced structurally (DEC-030), by
  eslint, and by a per-frame sampler in the e2e suite.
- **Add flow.** Results stagger in with a clamped delay; the manual fallback is the last child of
  the same list. The selected card's cover is carried into the form header and the form enters.
  The post-add highlight ring now fades after 2.2s instead of persisting until the next navigation.
- **Optimistic rollback.** A failed inline write rolls back, shakes the row it happened to, and
  reports on the toast surface. Includes a prerequisite repair of the rollback query key
  (DEC-032).
- **Covers.** Decode-reveal with no layout shift, asserted against a cover held back 700ms
  (DEC-034).
- **Action bar and dialogs.** The triage bulk bar enters on transform and opacity only, with no
  exit. Radix dialogs keep their CSS transitions with a decelerating curve.
- **Reduced motion** through Motion's hook in the preset layer, with `index.css` retained as the
  CSS backstop, and proven in pairs (DEC-033).

### Commits

| Commit | Subject |
|---|---|
| `6bb995c` | feat: animate the score picker with the score ramp |
| `e6d117f` | feat: crossfade the library container on sort and filter change |
| `c4c3f81` | feat: stagger add results and animate selection into place |
| `192187e` | feat: add optimistic rollback feedback |
| `ca47f29` | feat: spring the bulk action bar and dialog transitions |
| `1943281` | feat: blur up covers without layout shift |
| `f218578` | test: assert reduced motion and virtualization budgets under animation |

Checkpoint 1 also carries the foundation — the preset module, the `LazyMotion` provider, the
eslint rules, the `matchMedia` shim and the `optimizeDeps` entry — because the first animated
surface is neither verifiable nor bounded without them. Checkpoint 5 is an added checkpoint: the
contract names action-bar and dialog transitions as a deliverable but folds them into no
checkpoint.

### Acceptance criteria

1. **Met.** Each microinteraction in product-spec section 7 is implemented and was exercised in a
   browser against a real backend; see Walkthrough.
2. **Met, and made structural.** `grep -rn "layout" frontend/src/features/library/VirtualLibrary.tsx`
   finds no layout prop, eslint bans Motion in that file, and `domAnimation` makes `layout` and
   `layoutId` inert application-wide (DEC-030). The proof is not a grep: a per-frame sampler
   watches every animation the browser starts across a sort change and asserts none was ever
   attached to a card or a virtual row, while the container itself did animate.
3. **Met, and the assertion is no longer vacuous.** It had sampled one `article`'s transition
   duration, on an element carrying no transition. It now covers six surfaces on both properties,
   including a portalled listbox, and is paired with a positive test (DEC-033). A third test
   proves Motion's own animations are suppressed, which no stylesheet can do.
4. **Met and re-measured.** Against the 5,000-entry fixture: 7 mounted rows / 28 mounted cards at
   rest, and at the peak of a crossfade 4 rows / 16 cards / exactly 1 container, against bounds of
   20 and 48. Against 30 real books in the walkthrough: 1/2/4 columns at 375/768/1440 with
   4/5/5 mounted rows and 4/10/20 mounted cards. The expanded panel containment test is unchanged
   and passing; the panel scales up from 0.96 towards its resting box, so it can only be more
   contained mid-animation.
5. **Met.** Unit and e2e both. In the walkthrough against a forced 500: marker set, toast shown,
   and the score still read 9 — the value the user had before the failed write.
6. **Met.** Twelve hard wheel gestures over the walkthrough library left 18 cards and 5 rows
   mounted. Animation is applied to the container and to controls, never to scroll-driven mounting.
7. **Met.** Chromium **53 passed, 2 skipped**. The two skips are `live-metadata.spec.ts` behind
   `LIVE_METADATA_MODE`. Zero uncaught page errors across the whole walkthrough except one
   deliberately injected 500.

### Verification

```text
python scripts/validate_project.py   passed
make format                          clean
make check                           passed (ruff, mypy 33 files, tsc, openapi, validator)
make test                            backend 154 passed / frontend 68 passed
npm run test:e2e -- --project=chromium   53 passed, 2 skipped
make build                           backend wheel + frontend bundle
git diff --check                     clean
```

Frontend tests went 51 -> 68; e2e 44 -> 53.

**Bundle.** 696.24 kB JS (219.66 kB gzip), 36.88 kB CSS. Against the Sprint 015 predecessor of
610 kB that is **+86 kB raw**, materially more than the 30-45 kB estimated in the contract's risk
section; against the Sprint 013 baseline of 343.79 kB (105.40 kB gzip) it is roughly double. Most
of the growth to 610 kB predates this sprint, but this sprint's share is not small and the build
still emits a chunk-size warning. Flagged for Sprint 017, which already owns the code-split
decision.

### Walkthrough (AGENTS.md section 3)

Run against a real backend on `:8100` with the owner's `GOOGLE_BOOKS_API_KEY`, both providers
reporting available, and a **throwaway data directory** so the owner's `data/` was untouched.
Thirty rows of Spanish-language and translated fiction imported from a Goodreads CSV, then driven
in Chromium at 375/768/1440. Twenty-five screenshots.

Exercised: import preview and commit; triage accept-all and bulk status with the action bar;
library at three widths; scoring from the list with pointer hover, keyboard focus and commit; four
consecutive sort changes including a return to a cached sort; a hard scroll; a forced write
failure; provider search, selection and add; the post-add highlight; the detail page; and the
whole pass again under `prefers-reduced-motion: reduce`.

Observed:

- Enrichment ran live during the pass. 30 of 32 entries acquired a cover and 32 of 32 a year;
  31 cover files landed on disk.
- Four sort changes left **exactly one** library container mounted, which is the property
  `mode="wait"` exists to guarantee (DEC-031).
- Under reduced motion, 522 animations were observed across sorts, a score commit and a search, and
  **none** had a duration above a hundredth of a second. Every flow still completed: the score
  committed, the search returned.
- The add flow: 20 provider results plus the manual fallback, all staggering; focus landed on the
  status control on the frame the form mounted; the selected cover appeared in the form header; the
  highlight ring was present 0.9s after the add and gone by 3.1s.
- The forced failure reported `Your change could not be saved / The previous value was restored.`,
  set `data-rollback`, and left the score at its prior value.

Things noticed and deliberately left:

- **Several covers are wrong** — a Mariana Enriquez title showing a Luisgé Martín cover, and so on.
  This is an artefact of the walkthrough fixture, not a defect: the ISBN13s in that CSV were
  invented for this pass and resolve to real but unrelated editions. Recorded so a later session
  does not chase it.
- **A provider "image not available" placeholder is accepted as a cover.** `La invención de Morel`
  shows a white JPEG reading "image not available", which is a successful HTTP response carrying a
  non-cover. Nothing in the pipeline detects this. Genuinely worth a decision; not this sprint.
- **The edition-year truncation is still there** (`Edition year: 201…`), as recorded against
  Sprint 017. Untouched, because fixing it means changing the card box DEC-023 pins.
- Entries added through the UI still carry no score, so the detail page shows an unset control.

### Deviations and decisions

Five decisions recorded: **DEC-030** (the Motion feature set as a structural guardrail, and why
Radix dialogs stay CSS-animated), **DEC-031** (`mode="wait"` and the scroll reset), **DEC-032**
(the shake is visual state, not a second announcement channel, plus the rollback query-key repair),
**DEC-033** (reduced motion is only meaningful proven in pairs), **DEC-034** (decode-reveal, not a
blur-up).

Two deliverables ship as something narrower than the contract's wording, both named rather than
quietly redefined:

- **Cover blur-up → decode-reveal.** A blur-up needs a server-supplied low-resolution placeholder;
  the API exposes none (DEC-034).
- **"The selected card animates into place" → a carried-identity enter.** A shared-layout morph
  needs Motion's projection features, which DEC-030 removes application-wide on purpose, and its
  source element is a cover that may not have loaded when the morph would measure it. The card the
  reader clicked visibly becomes the card at the top of the form instead, with no navigation
  (DEC-030).

One prerequisite repair was made under AGENTS.md section 2.4 and is recorded in DEC-032: the
optimistic rollback wrote its snapshot into the wrong query key.

### Impact on future sprints

- **Sprint 017** inherits a larger bundle (696 kB, +86 kB) and now owns that decision with a
  sharper number. Its reduced-motion and E2E-coverage items are partly discharged: a reusable
  animation sampler lives at `frontend/e2e/motion.ts`, and the unit suite runs under reduced motion
  by default. Its two cosmetic defects are confirmed still present. One new observation is added
  for it to weigh: a provider placeholder image is accepted as a cover.
- **Sprint 018** is unaffected. No backend, schema, migration or API change was made this sprint;
  migration head remains `0006_job_error_code`.
