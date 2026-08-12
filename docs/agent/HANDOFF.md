# Handoff — current reality

**Last completed:** Sprint 016 (motion-interaction-polish), 2026-08-11.
**Next:** Sprint 017 (scale-accessibility-resilience) — status `ready`, file at
`docs/sprints/017-scale-accessibility-resilience.md`.

## Read this first

The application has a motion layer, and it is deliberately a small one with hard edges.

**Every timing lives in `frontend/src/lib/motion.ts`.** `useMotionPresets()` returns each preset in
a full and a reduced form, so respecting `prefers-reduced-motion` is a property of the construction
rather than something a new surface has to remember. A `transition={{...}}` literal in a component
is a defect.

**`layout` and `layoutId` do nothing anywhere in this application, on purpose.** `AppShell` mounts
`<LazyMotion features={domAnimation} strict>`, and `domAnimation` omits Motion's projection
features. That is DEC-030: the rule "virtualized rows never carry layout animations" is structural
now, not a sentence in a spec. Two eslint rules back it up — the eager `motion` factory is banned
everywhere, and Motion is banned outright inside `VirtualLibrary.tsx`. If you want a shared-layout
transition you must first justify `domMax`, and you would be re-arming the DEC-023 hazard.

**Import `m` from `motion/react`.** Not from `motion/react-m` — that subpath exports the tag
components individually, so `import { m } from "motion/react-m"` gives you `undefined`.

## Plan shape

| Sprint | Scope | Status |
|---|---|---|
| 017 | Scale, accessibility, resilience | `ready` |
| 018 | Container, backup, release | roadmap contract |

## What Sprint 017 must know

- **The bundle is 696 kB of JavaScript** (219.66 kB gzip), up 86 kB this sprint and roughly double
  the Sprint 013 baseline. The chunk-size warning is still emitted. Sprint 017 owns the decision to
  code-split or to raise the limit deliberately; it now has the real number.
- **Reduced motion is partly discharged.** DEC-033 requires every reduced-motion assertion to be
  paired with a positive one, because the old assertion sampled an element that carried no
  transition and passed vacuously for eleven sprints. The unit suite defaults to `reduce` through
  `src/test/matchMedia.ts`; opt out with `setPrefersReducedMotion(false)` **before** `render`.
- **There is a reusable animation sampler** at `frontend/e2e/motion.ts`: `sampleAnimations` watches
  every animation the browser starts across an interaction and reports what it was attached to.
  That is how "no row ever animated" is proven rather than asserted. Reuse it; do not re-derive it.
- **The DEC-023 bounds still have headroom and are printed on every e2e run.** 7 of 20 rows and 28
  of 48 cards at rest; 4 rows, 16 cards and exactly one container at the peak of a crossfade.
- **Two cosmetic defects are still open and are yours**: the truncated `Edition year: 201…` line on
  library cards, and the triage score cell rendering a provisional score as `6·` with no legend.
  Both were confirmed present in this sprint's walkthrough.

## Gotchas that will cost you an hour each

- **`tailwindcss-animate` redefines `duration-*` to set `animation-duration`**, later in the
  cascade than the core rule. An element carrying both a `duration-*` transition and an `animate-*`
  keyframe runs the keyframe at the transition's duration. `VirtualLibrary`'s card uses
  `[transition-duration:500ms]` for exactly this reason.
- Motion's `useReducedMotion` is one-shot per component and reads a module global updated only by a
  `change` event. If `matchMedia` is missing altogether, Motion assumes animations are allowed.
- `m` and `useAnimationControls` work outside a `LazyMotion` provider — features just are not
  loaded and nothing animates. That is what lets component tests render in isolation.
- The non-compact `ScorePicker` replaces its trigger with the panel while open. A test asserting
  the trigger recolours on hover must use `compact`.
- A raw `element.focus()` in a unit test is not act-wrapped, so React does not flush before the
  assertion.
- Everything Sprint 015 recorded still applies: `eslint --max-warnings=0` means a component file
  exports components only; jsdom has neither Pointer Capture nor `scrollIntoView`; a Radix
  `AlertDialog` is addressed by its visible title; `e2e/radix.ts` has `chooseOption`; and
  `e2e/feedback.spec.ts` asserts rendered geometry, not `toBeVisible()`.
- A new runtime dependency must be added to `optimizeDeps.include` in `vite.config.ts` or the dev
  server force-reloads mid-run and drops whatever Playwright was doing.

## Things noticed and deliberately left

- **A provider "image not available" placeholder is accepted and stored as a cover.**
  `La invención de Morel` acquired a white JPEG reading "image not available". It arrives as a
  successful response carrying a non-cover, and nothing in the pipeline detects that. Added to the
  Sprint 017 roadmap entry as a question to decide, not a task to do.
- **`100 años de Soledad` (ISBN 9781516909629) still has no cover.** `OQ-001` in
  `docs/sprints/ROADMAP.md`, open and unassigned. Do not implement it or fold it into a sprint
  until the owner decides.
- Entries added through the UI carry no score; the detail page shows an unset control.
- Imports land `unsorted`, so the library looks briefly as though the import did nothing.

## Walkthrough notes for whoever runs the next one

Run the backend with `BOOK_TRACKER_DATA_DIR` pointed at a throwaway directory rather than deleting
`data/`. The owner's `data/` was not touched this sprint and does not need to be. Two things cost
time: the import page needs `Preview import` clicked before a commit button exists at all, and
provider search takes about five seconds, so a four-second wait reports zero results and looks like
a defect. If you invent ISBNs for a fixture CSV they will resolve to real but unrelated editions
and every cover will be wrong — that is the fixture, not the application.

## Provider recordings

`backend/tests/fixtures/providers/` holds verbatim responses captured from Open Library and Google
Books on 2026-08-09, with a README naming the exact URL behind each file. They exist because
DEC-025 forbids proving provider behavior with a mock of the method under test. **Never re-record
them silently** — a fixture is a pinned observation of an external contract, and quietly refreshing
one turns a regression test into a rubber stamp.

## State

- Planning revision 6; state points to Sprint 017, project status `ready`.
- Gates at close: validator passed, `make check` passed, `make test` backend **154** / frontend
  **68**, Chromium e2e **53 passed / 2 skipped**, `make build` succeeded, `git diff --check` clean.
- The two skipped e2e tests are `live-metadata.spec.ts`, which needs `LIVE_METADATA_MODE` and a
  live backend. Run them with
  `BOOK_TRACKER_E2E_BACKEND=http://127.0.0.1:8100 LIVE_METADATA_MODE=add npx playwright test e2e/live-metadata.spec.ts`.
- Migration head is `0006_job_error_code`. No backend change this sprint.
- `.env` exists locally with the owner's `GOOGLE_BOOKS_API_KEY` and is gitignored. `make dev-backend`
  does not load it; export it yourself for a walkthrough.
- **`node_modules` was found materially incomplete at the start of this session** and `npm ci` was
  required before anything typechecked. If imports fail to resolve for no apparent reason, check
  that first.
- Commit messages in this repository carry no `Co-Authored-By` trailer.
