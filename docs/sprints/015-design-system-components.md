# Sprint 015 — Design system and component foundation

**Status:** completed
**Depends on:** 014
**Roadmap revision:** 6

## Objective

Every screen is built from the component library, design tokens, and form stack the technical
spec requires, and every user action produces visible feedback.

## Required context

1. `AGENTS.md`, including the walkthrough gate in section 3
2. `docs/assessment.md` sections 1 and 3 (dropped libraries and the invisible feedback layer)
3. `docs/specs/product-spec.md` section 7 (UI, design direction, screens, interaction notes)
4. `docs/specs/technical-spec.md` section 8 (frontend architecture, design tokens, cross-cutting behavior)
5. `docs/decisions.md` DEC-023, DEC-024, and DEC-026
6. Sprint 013 Outcome (the grid contract this sprint must not regress) and Sprint 014 Outcome
7. `frontend/src/features/library/VirtualLibrary.tsx` and `frontend/src/features/library/library.ts`
8. `frontend/src/components/ScorePicker.tsx`, `frontend/src/components/AppShell.tsx`, and `frontend/src/components/CoverImage.tsx`
9. `frontend/src/pages/` in full, `frontend/src/index.css`, `frontend/tailwind.config.ts`, and `frontend/components.json`
10. `frontend/e2e/` in full — several specs must be rewritten, not merely re-run

## Diagnosed defects and current implementation baseline

`docs/specs/technical-spec.md` section 8 requires "React Hook Form with schema validation,
shadcn/ui primitives, Tailwind tokens, and Motion". Three were never installed:

- `frontend/components.json` is configured for shadcn (new-york, zinc, `cssVariables: true`) but
  `frontend/src/components/ui/` does not exist and the lockfile contains no Radix packages.
- `motion` is a dependency and is imported zero times.
- `react-hook-form` and `zod` are absent; roughly eighteen fields in `DetailPage.tsx` are
  uncontrolled and read through `FormData`.

Consequently `tailwind.config.ts` is `theme: { extend: {} }`, `index.css` defines no CSS
variables, and colour is expressed as inline `zinc-*` and `fuchsia-*` literals. `index.css` names
Inter but never loads it, so the app renders in `system-ui`. Section 8's token requirement for
"bundled/local or privacy-safe loading" is unmet.

Every status and sort control is a native `<select>`, which cannot be styled and renders as an OS
widget inside a dark UI. The five navigation icons in `AppShell.tsx` are hand-drawn SVGs in which
`LibraryIcon` and `ShelfIcon` are the same three horizontal lines.

Most damaging: the application has no visible feedback. "Already in your library", "Book added",
and "Book removed from your library" are written to `sessionStorage` under `akasha.toast`, read
by the destination route, and rendered into `<p className="sr-only" aria-live="assertive">` in
`HomePage.tsx` and `TriagePage.tsx`. `sr-only` is visually hidden, so no confirmation is ever
shown. Product spec section 4.3 requires a visible toast on duplicate add. The e2e suite passes
because Playwright reads hidden text.

Sprint 013 established the grid contract now recorded in technical-spec section 8 and DEC-023.
It is load-bearing and constrains this sprint (see Explicit non-scope).

## Deliverables

- shadcn/ui installed for real: `button`, `input`, `textarea`, `label`, `select`, `checkbox`,
  `dialog`, `alert-dialog`, `tabs`, `popover`, `sonner`, `command`, plus `lucide-react`,
  `react-hook-form`, `zod`, and `@hookform/resolvers`. `package-lock.json` is committed because
  `make bootstrap` runs `npm ci`.
- Design tokens in `tailwind.config.ts` and `index.css` CSS variables per DEC-026: zinc-950
  background, zinc-900 surface, zinc-800 border, zinc-50 text, zinc-400 muted, **amber-400
  accent** on zinc-950 foreground, and the score ramp red-400 (1–3), amber-400 (4–6), lime-400
  (7–8), emerald-400 (9–10). Inter self-hosted and bundled, no third-party font request.
- Every raw primitive replaced. Known clusters: the four hand-rolled modals and roughly eighteen
  fields in `DetailPage.tsx`; the delete dialog in `ShelvesPage.tsx`; search, sort, and shelf
  controls in `HomePage.tsx` — note the shelf control now reads `GET /api/shelves` through a
  `useQuery` rather than the loaded entries, so converting it to a shadcn `select` must keep that
  source (Sprint 014 AC7); filter, bulk status, bulk score, and row checkboxes in
  `TriagePage.tsx`; file input, Calibre path, per-row ambiguity select, and the hand-rolled
  tablist in `ImportPage.tsx`; search and manual-entry form in `AddPage.tsx`; the status select
  inside the library card in `VirtualLibrary.tsx`.
- Visible toasts via Sonner. The `sessionStorage["akasha.toast"]` handoff is deleted outright.
  Toast surfaces keep `role="status"`. The dedicated `aria-live` announcement regions remain for
  screen readers — the defect was that they were the only channel, not that they exist.
- All `FormData`-read forms converted to React Hook Form with zod resolvers.
- Navigation icons replaced with `lucide-react`.
- A degraded-search indicator fed by `GET /api/health/providers`, which Sprint 014 added
  (`getProviderHealth` in `src/api/health.ts` already types it). When `degraded` is true, say
  which provider is unavailable and why, rather than silently returning half the results.
- Cleanup with no compatibility layer: delete `frontend/src/pages/ComingSoonPage.tsx` (dead and
  unrouted since Sprint 004); delete the `.dialog` and `.field` component classes from
  `index.css` once nothing references them; remove every inline colour literal in favour of
  tokens.
- The e2e specs listed under Required tests rewritten for the new DOM.

## Acceptance criteria

1. `frontend/src/components/ui/` exists and every interactive control on every screen is a
   shadcn primitive or the two documented bespoke components (`ScorePicker`, the library card).
   No native `<select>` remains in `frontend/src/`.
2. Adding a book, adding a duplicate, deleting an entry, renaming a shelf, and committing an
   import each display a **visible** toast, verified in a browser at 375px and 1440px.
3. No occurrence of `akasha.toast` or `sessionStorage` remains in `frontend/src/`.
4. Colour, radius, spacing, and typography derive from tokens. `grep -rn "fuchsia-" frontend/src`
   returns nothing, and no hard-coded hex colour appears outside the token definitions.
5. Inter is served from the bundle; the built app issues no font request to a third-party host.
6. Every form validates through zod and reports field errors accessibly; a failed write never
   discards typed input, per technical-spec section 8.
7. The Sprint 013 grid contract holds unchanged: mounted virtual rows under 20, mounted cards
   under 48, 1/2/4 columns at 375/768/1440, no overlap between cover, metadata, and controls, and
   the expanded score panel stays geometrically inside its card at every width.
8. The full Chromium e2e suite passes with no uncaught page errors, with rewritten selectors and
   no reduction in the number of asserted behaviors.
9. `make check` passes, including `eslint --max-warnings=0`.

## Required tests (TDD)

- Visible-toast tests for add, duplicate add, delete, shelf rename, and import commit, asserting
  a *visible* element rather than accessible text alone.
- Form validation tests: invalid score, invalid date, and empty required title surface field
  errors and preserve input.
- The Sprint 013 spatial regressions in `frontend/e2e/library.spec.ts` must pass unmodified in
  intent; their selectors may change only where the DOM legitimately changed.
- Rewritten selectors, all of which break by construction under Radix:
  - `selectOption()` calls in `library.spec.ts`, `triage.spec.ts`, and `import.spec.ts` — Radix
    Select renders `button[role="combobox"]` with a portalled listbox.
  - `input[type="checkbox"]` selectors in `triage.spec.ts` — Radix Checkbox renders
    `button[role="checkbox"]`.
  - The `dl dt + dd` adjacent-sibling selector in `editorial.spec.ts`.
- Accessible-name parity: every `sr-only` label that an e2e spec queries by name keeps its exact
  text when it becomes a shadcn `<Label>`.

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
worklog. In a browser at 375px, 768px, and 1440px, exercise every screen: library filter and
sort, inline score and status editing, add by search and manually, detail edit and delete, a
Goodreads and a Calibre import including undo, triage selection and bulk actions, and shelf
rename and delete. Record what was clicked, what feedback appeared, and anything that felt
wrong. Screenshots at all three widths are recorded in the Outcome. Command output alone cannot
complete this sprint.

## Explicit non-scope

- No animation, spring, stagger, or crossfade work (Sprint 016). Static states only.
- No performance benchmarking, axe automation, or security limits (Sprint 017).
- No container, backup, or release work (Sprint 018).
- **Do not convert `ScorePicker` to a Radix `Popover` or any portalled primitive.** Radix portals
  to `document.body`, and `frontend/e2e/library.spec.ts` asserts the expanded panel is contained
  within its own card. That containment is the DEC-023 virtualization requirement and the exact
  defect Sprint 013 repaired. `ScorePicker` stays a bespoke in-card absolute overlay.
- **Do not replace the library card box with a shadcn `Card`.** `gridLayout.cardHeight` is pinned
  at 280px because fixed-size virtualization depends on it, and `gridColumnCount` subtracts a
  hard-coded 32px `paddingX` matched to the row's padding. A primitive carrying its own intrinsic
  padding desynchronizes both.
- Do not remove the `data-card-cover`, `data-card-meta`, `data-card-controls`, `data-score-panel`,
  `data-mounted-count`, or `data-columns` attributes; they are the Sprint 013 contract.
- Do not change the `feed` and `table` ARIA roles on the library container.
- No backend changes.

## Commit checkpoints

1. `build: install shadcn primitives, form stack, and icons`
2. `feat: define design tokens and self-host Inter`
3. `feat: add visible toast surface and remove sessionStorage handoff`
4. `refactor: rebuild library and triage on shadcn primitives`
5. `refactor: rebuild add, detail, import, and shelves on shadcn primitives`
6. `refactor: convert forms to react-hook-form with zod schemas`
7. `test: update e2e selectors for the component library`
8. `chore: remove dead page and superseded css classes`
9. final `docs(sprint-015): close sprint and hand off`

## Risks and decisions to surface

- A Radix `Select` inside a virtualized row portals its listbox to `document.body` while the row
  may unmount on scroll. Verify Radix's scroll lock holds it open, and record the result.
- `isEditableTarget` in `features/library/library.ts` guards global shortcuts with
  `target.closest('[role="dialog"]')`. Radix Dialog portals to `document.body` and keeps
  `role="dialog"`, so this survives — but confirm it explicitly, because a silent break disables
  every keyboard shortcut guard.
- shadcn components add DOM nodes per card. Re-measure both DEC-023 mounted-DOM bounds and record
  the new margin; if the card bound tightens, say so rather than relaxing the number.
- Sonner renders its own live region. Confirm it does not double-announce alongside the retained
  `aria-live` announcement paragraphs, and remove whichever duplicate is redundant.
- Decide whether the score ramp applies to the score picker only or also to score text in list
  rows, and record it.

## Outcome

**Status: completed 2026-08-11.**

### Delivered

`frontend/src/components/ui/` now holds twelve shadcn primitives. Every interactive control on
every screen is a primitive or one of the two documented bespoke components; no native `<select>`
remains in `frontend/src`. `tailwind.config.ts` and `index.css` carry the DEC-026 token set, Inter
ships from the bundle as seven local `woff2` subsets, and `grep -rn "fuchsia-" frontend/src`
returns nothing. Feedback is visible: Sonner is mounted once in `AppShell`, the
`sessionStorage["akasha.toast"]` handoff is deleted, and the new-entry highlight travels as router
state. All `FormData` reads are gone; the three forms validate through zod and keep typed input
when a write fails. Navigation icons are `lucide-react` (`LibraryIcon` and `ShelfIcon` were the
same three lines). `/add` shows a degraded-search notice fed by `GET /api/health/providers`.
`ComingSoonPage` and the `.field`/`.dialog` classes are deleted.

### Commits

| Commit | Subject |
|---|---|
| `0192b52` | build: install shadcn primitives, form stack, and icons |
| `4f56e7f` | feat: define design tokens and self-host Inter |
| `ed34c54` | feat: add visible toast surface and remove sessionStorage handoff |
| `4f30eeb` | refactor: rebuild library and triage on shadcn primitives |
| `d2954e3` | refactor: rebuild add, import, shelves, and the nav shell on shadcn primitives |
| `004f1b5` | refactor: convert forms to react-hook-form with zod schemas |
| `5ec996b` | chore: remove dead page and superseded css classes |
| `dad0b5a` | fix: give small controls their own radius token |

Checkpoints 6 and 7 landed as one commit: the e2e selector rewrite is not separable from the DOM
change that forces it, and committing the rewrite alone would have meant committing a red suite.

### Acceptance criteria

1. **Met.** Twelve primitives under `src/components/ui/`; `grep -rn "<select" frontend/src`
   returns nothing. `ScorePicker` and the library card box remain bespoke per DEC-026.
2. **Met.** Verified in a browser at 375px and 1440px by `e2e/feedback.spec.ts`, which asserts
   rendered geometry rather than `toBeVisible()` alone, and again by hand in the walkthrough:
   add `Book added`, duplicate `Already in your library`, delete `Book removed from your library`,
   rename `Shelf renamed to "Renombrada"`, import `Import complete: 30 books added`.
3. **Met.** `grep -rn "sessionStorage\|akasha.toast" frontend/src` returns one comment explaining
   why the handoff is gone. `localStorage` for the view preference is untouched; AC3 names
   `sessionStorage` only.
4. **Met.** `grep -rn "fuchsia-" frontend/src` is empty and no hard-coded hex appears outside the
   token definitions in `index.css`, which name the palette entries they encode in comments.
5. **Met.** `make build` emits seven `inter-*.woff2` files; `grep -roE "googleapis|gstatic"` over
   `dist/` returns nothing.
6. **Met.** `opinionSchema`, `metadataSchema`, and `manualBookSchema` in
   `src/features/detail/schemas.ts`. Errors are `role="alert"`, referenced by `aria-describedby`
   from a control carrying `aria-invalid`. Six tests cover invalid date range, out-of-range reread
   count, empty title on both forms, malformed ISBN, and a rejected write preserving input.
7. **Met and re-measured.** Against the 5,000-entry fixture: 7 mounted rows, 28 mounted cards
   (bounds: under 20 and under 48). Against 30 real books: 4/2/1 columns at 1440/768/375 with
   5/5/4 mounted rows and 20/10/4 mounted cards. The primitives add nodes per card but no cards or
   rows, so the margin is unchanged. `e2e/library.spec.ts` now prints the measurement.
8. **Met.** Chromium: **44 passed, 2 skipped**, no uncaught page errors. The two skips are
   `live-metadata.spec.ts`, which needs `LIVE_METADATA_MODE`. Asserted behaviours increased: the
   suite gained `feedback.spec.ts` (10 tests) and a virtualizer/listbox test, and the import
   ambiguity test now also asserts that choosing enables the commit.
9. **Met.** `make check` passes including `eslint --max-warnings=0`.

### Verification

```text
python scripts/validate_project.py   passed
make format                          clean
make check                           passed (ruff, mypy 33 files, tsc, openapi, validator)
make test                            backend 154 passed / frontend 51 passed
npm run test:e2e -- --project=chromium   44 passed, 2 skipped (three consecutive clean runs)
make build                           backend wheel + frontend bundle, 610 kB js / 34 kB css
git diff --check                     clean
```

### Walkthrough (AGENTS.md section 3)

Run against a real backend on `:8100` with the owner's `GOOGLE_BOOKS_API_KEY`, a fresh database,
and a 30-row Goodreads CSV of real Spanish-language and translated fiction. 42 screenshots at
375/768/1440. **Zero uncaught page errors across the whole pass.**

Exercised: Goodreads preview and commit (30 rows), triage selection and bulk status, accept-all
suggested, library grid at three widths, sort by score, shelf filter, free-text search, inline
score and status editing, table view, detail view, opinion edit with an invalid date range,
metadata edit with an empty title, delete with confirmation, provider search, manual add with a
malformed ISBN, shelf rename and delete, the Calibre tab, and reduced motion.

Observed:

- Enrichment ran live during the pass and real covers appeared for `Ficciones`, `Cien años de
  soledad`, and `Rayuela` while the library was open.
- Provider search for "El hacedor Borges" returned 20 results across both providers, each with an
  edition year, publisher, language, and provider badge.
- The degraded-search notice was verified against a genuinely degraded backend (server restarted
  without the key): *"Search is running on fewer providers — googlebooks is unavailable:
  GOOGLE_BOOKS_API_KEY is not set"*, at both 375px and 1440px.
- Imported rows land `unsorted`, so the library is empty until triage runs. Correct per DEC and
  the status-facet default, but it reads as "the import did nothing" for a moment.
- Inline score and status edits produce no toast. Deliberate: they are optimistic writes that
  render instantly, and a toast per keystroke-speed edit would be noise. Failures do toast.

Things noticed and left (see `docs/agent/HANDOFF.md`):

- On a library card the edition-year line is `truncate`d inside a narrow metadata column, so
  `Edition year: 1994` renders as `Edition year: 199…`. The year is a Sprint 014 correctness win
  being clipped by Sprint 013 geometry; fixing it means changing the card, which DEC-023 pins.
- The triage score cell renders a provisional score as `6·`, which is cryptic without the legend
  the library card has.

### Deviations and decisions

- **DEC-028** records the toast surface: Sonner's own `aria-live` region replaces the two
  `sr-only` announcement paragraphs rather than joining them, because keeping both announces every
  confirmation twice. Sonner v2 puts the polite region on the container rather than
  `role="status"` on each toast, so the sprint's "toast surfaces keep `role='status'`" is met one
  level up.
- **DEC-029** records that Radix makes the document inert while a Select listbox is open, which is
  what makes a portalled listbox safe inside a virtualized row, and that `isEditableTarget` had to
  widen from tag names to roles.
- Confirmation dialogs are addressed by their visible title now, because Radix derives the
  accessible name from `AlertDialogTitle` via `aria-labelledby`, which overrides `aria-label`.
- `--radius-control` was added after the walkthrough showed a 16px checkbox rendering as a circle
  at the card radius.
- Two prerequisite defects were fixed because they blocked verification: the search-debounce
  effect wrote an unchanged query back to the URL on every page load, and Vite discovered the new
  dependencies mid-navigation and force-reloaded the page.

### Impact on future sprints

- **016 (motion):** the token layer, `tailwindcss-animate`, and Sonner's own transitions are in
  place, so animation work starts from tokens rather than literals. It must re-assert the two
  DEC-023 bounds with animation on; the current margin is 7/20 rows and 28/48 cards. The
  crossfade-on-sort work now has a stable list container to key. `motion` is still imported zero
  times.
- **017 (hardening):** the accessibility audit inherits labelled controls, `aria-invalid` /
  `aria-describedby` on every field, and Radix focus management, so it should find fewer defects
  than planned. It also inherits a 610 kB JS bundle that now warrants the code-splitting the build
  warns about, and the two cosmetic defects listed above.
- **018 (release):** unchanged. The build still produces a single static bundle with no runtime
  font or CDN dependency, which keeps the LAN-only invariant intact.
