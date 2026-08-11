# Handoff — current reality

**Last completed:** Sprint 015 (design-system-components), 2026-08-11.
**Next:** Sprint 016 (motion-interaction-polish) — status `ready`, file at
`docs/sprints/016-motion-interaction-polish.md`.

## Read this first

The frontend is now built on the stack technical-spec section 8 has always specified. Twelve
shadcn primitives live in `frontend/src/components/ui/`, colour and radius and type come from
tokens, Inter ships from the bundle, and every form validates through zod. There is no native
`<select>` left in `frontend/src`.

**Feedback is visible.** Sonner is mounted once in `AppShell`, bottom-right. The
`sessionStorage["akasha.toast"]` handoff is gone, and so are the two `sr-only` announcement
paragraphs — DEC-028 explains why keeping both would announce every confirmation twice. If you add
a confirmation, it goes through `toast()`; there is no second channel to also update.

This was verified by using the application, not only by tests: a 30-book Goodreads import against
a real backend with the owner's Google Books key, 42 screenshots at 375/768/1440, zero uncaught
page errors. Enrichment ran live during the pass and real covers appeared while the library was
open.

## Plan shape

| Sprint | Scope | Status |
|---|---|---|
| 016 | Motion and interaction polish | `ready` |
| 017 | Scale, accessibility, resilience | `planned` |
| 018 | Container, backup, release | roadmap contract |

## What Sprint 016 must know

- **`motion` is still imported zero times.** That has not changed since Sprint 004.
- **You are not starting from a blank page.** Radix already animates dialogs, selects, and toasts
  on enter and exit, and `tailwindcss-animate` is installed and wired into `tailwind.config.ts`.
  Decide what to keep before adding more.
- **Animate against tokens.** `--score-low/mid/high/top`, `--primary`, `--radius`,
  `--radius-control`. `grep -rn "fuchsia-" frontend/src` is empty and should stay that way.
- **The DEC-023 bounds have headroom but are not slack.** Measured this sprint: 7 of 20 mounted
  rows and 28 of 48 mounted cards against the 5,000-entry fixture. `e2e/library.spec.ts` prints
  the numbers on every run. Re-assert both with animation enabled; if a bound tightens, say so
  rather than relaxing it.
- **Portalling is safe inside a virtual row; the score picker still may not portal.** DEC-029
  measured that Radix makes the document inert while a listbox is open, so the virtualizer cannot
  recycle the owning row. The `ScorePicker` exception is narrower than "portals are unsafe": its
  expanded panel is required to stay geometrically inside its card, and `e2e/library.spec.ts`
  asserts that.
- **The score ramp already exists.** `src/lib/score.ts` maps 1–10 onto four bands and is used by
  the picker and by triage score text. The product spec's "colour shifts across the range" is a
  transition between bands that already exist, not a new palette.

## Gotchas that will cost you an hour each

- `eslint --max-warnings=0` plus `react-refresh/only-export-components` means a component file
  exports components only. That is why `buttonVariants` lives in `button-variants.ts`.
- jsdom has neither Pointer Capture nor `scrollIntoView`. `src/test/setup.ts` shims them; without
  it every Radix interaction test throws before asserting anything.
- Radix `AlertDialog` is `role="alertdialog"`, and its title sets `aria-labelledby`, which
  overrides `aria-label`. Address confirmation dialogs by their visible title.
- While a Radix listbox is open the rest of the document is `aria-hidden` and pointer-events-none.
  A test that needs the scroll container during that window addresses it by class, and a
  page-level error rendered behind an open modal is unreachable — report inside the dialog.
- `e2e/radix.ts` has `chooseOption` and `expectSelected`. `selectOption()` and `toHaveValue()` do
  not work on a Radix Select.
- `e2e/feedback.spec.ts` asserts rendered geometry, not `toBeVisible()`. An `sr-only` element is
  "visible" to Playwright — that is exactly how DEC-024 survived thirteen sprints. Do not weaken
  it back to a text query.

## Things noticed and deliberately left

- **The edition-year line is truncated on library cards.** `Edition year: 1994` renders as
  `Edition year: 199…` because the metadata column is narrow and the line is `truncate`d. A
  Sprint 014 correctness win clipped by Sprint 013 geometry. Recorded against Sprint 017; fixing
  it means changing the card, which DEC-023 pins.
- **The triage score cell shows a provisional score as `6·`** with no legend.
- **The bundle is 610 kB of JavaScript** and the build now emits a chunk-size warning. Sprint 017
  decides whether to code-split or raise the limit deliberately.
- **Imports land `unsorted`**, so the library looks empty until triage runs. Correct, but it reads
  briefly as "the import did nothing".
- **`100 años de Soledad` (ISBN 9781516909629) still has no cover.** This is `OQ-001` in
  `docs/sprints/ROADMAP.md`, open and unassigned. Do not implement it or fold it into a sprint
  until the owner decides.
- Entries added through the UI carry no score; the detail page shows an unset control.

## Provider recordings

`backend/tests/fixtures/providers/` holds verbatim responses captured from Open Library and Google
Books on 2026-08-09, with a README naming the exact URL behind each file. They exist because
DEC-025 forbids proving provider behavior with a mock of the method under test. **Never re-record
them silently** — a fixture is a pinned observation of an external contract, and quietly
refreshing one turns a regression test into a rubber stamp. `scripts/validate_project.py` exempts
that directory from text hygiene so the bytes stay as captured.

## State

- Planning revision 6; state points to Sprint 016, project status `ready`.
- Gates at close: validator passed, `make check` passed, `make test` backend **154** / frontend
  **51**, Playwright chromium **44 passed / 2 skipped** across three consecutive runs,
  `make build` succeeded, `git diff --check` clean.
- The two skipped e2e tests are `live-metadata.spec.ts`, which needs `LIVE_METADATA_MODE` and a
  live backend. Run them with
  `BOOK_TRACKER_E2E_BACKEND=http://127.0.0.1:8100 LIVE_METADATA_MODE=add npx playwright test e2e/live-metadata.spec.ts`.
- Migration head is `0006_job_error_code`. No backend change this sprint.
- `.env` exists locally with the owner's `GOOGLE_BOOKS_API_KEY` and is gitignored. It is never
  committed. Note that `make dev-backend` does not load it; export it yourself if you want live
  Google Books during a walkthrough.
- `data/` is gitignored and holds whatever the last walkthrough imported. Delete it for a clean
  run.
- Commit messages in this repository carry no `Co-Authored-By` trailer.
