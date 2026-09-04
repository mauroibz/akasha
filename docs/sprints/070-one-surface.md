# Sprint 070 — One surface

**Status:** completed
**Depends on:** 067
**Roadmap revision:** 38

> Planned from [`../ui-cohesion-proposal.md`](../ui-cohesion-proposal.md) §3.1–3.4 and
> §3.6. **Accepted by the owner as DEC-136.** Renumbered from 071 to 070: the export
> line's own Sprint 070 (ecosystem-specific exporters) was built, found to exceed the
> owner's intended scope, and withdrawn the same day — see DEC-136. This sprint takes
> the freed number.

## Objective

Make the six screens outside `/insights` look like the same application: one panel, one
page header, one way back, one segmented control, one domain strip, every cover through
`CoverImage`, and an import preview that speaks the language the rest of the product
speaks. Frontend only. No screen changes what it does.

## Required context

- [`../ui-cohesion-proposal.md`](../ui-cohesion-proposal.md) — **read first.** §1 is the
  seven rules this sprint applies, §2 is the eleven findings with their lines, §3.1–3.4
  and §3.6 are the deliverables, §5 is what it must not do, §6 is why a cosmetic sprint is
  dangerous here.
- `docs/decisions.md` DEC-026 (the tokens and the score ramp — finding 1 is a violation of
  it), DEC-023 (the virtualization contract: fixed row heights, no per-row layout
  animation — **this sprint keeps out of that box**), DEC-080 (render the declaration),
  DEC-134 (the unpaid 390px domain-strip overflow this sprint pays), DEC-132/133 (what the
  insights redesign settled and why).
- `docs/brand/BRAND.md` — one accent, and no second one.
- Code, read fresh, all eleven findings verified at their lines before anything is
  written: `frontend/src/pages/DetailPage.tsx`, `ShelvesPage.tsx`, `ImportPage.tsx`,
  `AddPage.tsx`, `TriagePage.tsx`, `HomePage.tsx`, `InsightsPage.tsx`;
  `frontend/src/features/library/InsightsCard.tsx` (the panel being generalized),
  `frontend/src/components/CoverImage.tsx:20-48`,
  `frontend/src/features/import/ConnectorGuide.tsx`,
  `frontend/src/features/library/VirtualLibrary.tsx` (the box not to touch),
  `frontend/src/lib/score.ts`, `frontend/tailwind.config.ts`.
- Tests: every `*.test.tsx` for the pages above, `frontend/e2e/accessibility.spec.ts`,
  `insights.spec.ts` (the 390px measurement), `library.spec.ts`, `import.spec.ts`,
  `triage.spec.ts`, `add-detail.spec.ts`, `editorial.spec.ts`.

## Current implementation baseline

Confirm each at activation; the proposal's §2 table carries the lines.

- Six box idioms across five files, two radii, three heading styles.
- Three page-header treatments and four spellings of "back".
- The domain radiogroup and the segmented control are each written twice, near-identically.
- The detail page's cover is a bare `<img>` with a hand-rolled empty box.
- The import preview paints *Local cover staged* in `text-score-top` — the emerald that
  means a 9 or a 10 everywhere else — writes scores as prose, and prints
  `{row.field}: {row.code}` at a reader.
- The domain strip overflows a 390px viewport by roughly 39px with five domains
  (DEC-134, measured on `/insights`; `/` has the same markup and has never been measured).

## Deliverables

1. **`Panel`** — `rounded-xl border border-border bg-surface`, heading slot, optional
   right-hand stat slot, one padding scale. The insights card generalized. Applied to
   Detail, Shelves, Import and Add.
2. **The amber uppercase heading retires.** A panel heading is a panel heading on every
   screen; amber marks quantity and active state, not "this is a heading".
3. **`PageHeader`** — eyebrow, title, optional count, lede, actions slot — on every page,
   including `AddPage`, which has no header today. **One** *← Library* control, in one
   place, replacing four spellings.
4. **`SegmentedControl`**, extracted from the two copies, with the 44px target both should
   have had.
5. **`DomainStrip`**, extracted from the two copies, scrolling horizontally below its
   breakpoint instead of pushing the document sideways. **This pays DEC-134's outstanding
   defect once, for both screens.**
6. **Every cover through `CoverImage`**, including the largest one on the detail page:
   decode-reveal, shared placeholder, and *No cover* instead of a broken-image glyph.
7. **The import preview speaks the application's language** (§3.6): the score becomes the
   chip every other surface paints; *Local cover staged* becomes a neutral chip; a field
   error names the domain's declared label and the connector's declared wording instead of
   `field: code`.
8. **Justified differences kept, and justified in one sentence each.** The library's
   translucent surface under a virtualized list and the connector guide's quieter box are
   the known candidates. Unifying everything and calling that coherence is the failure mode
   (proposal §6).

## Acceptance criteria

1. No surface outside a score renders in a score-ramp colour. Asserted as a test over the
   import preview's cover-staged chip, which is finding 1.
2. A score in the import preview renders in the same band class as the same score on the
   library card and the detail page.
3. A failed preview row names the domain's declared label for the field and the
   connector's declared wording for the error; no raw field name or error code reaches the
   DOM.
4. A detail page whose cover URL 404s shows *No cover*, not a broken image.
5. Every page renders its header through one component; a `git grep` for the old header
   markup returns nothing.
6. There is exactly one way back, and it reads the same on Detail, Shelves, Add, Triage
   and Import.
7. `/` and `/insights` at 390px with five domains: no horizontal body scroll, the strip
   scrolls within itself, every control keeps a 44px target. Measured on **both**, in e2e.
8. Zero serious axe violations on Library, Detail, Shelves, Add, Import and Triage.
9. **The existing component and e2e suites pass unchanged**, except where a test asserts
   one of the eleven findings — each such test is named in the outcome with the finding it
   belonged to.
10. `VirtualLibrary`'s row height, card box and column count are unchanged; the DEC-023
    contract is untouched.

## Required tests (TDD)

| Behavior | Layer | File |
|---|---|---|
| The staged-cover chip is not a score-ramp colour | component | `ImportPage.test.tsx` |
| A preview score renders in the shared band class | component | `ImportPage.test.tsx` |
| A field error renders declared label and declared wording | component | `ImportPage.test.tsx` |
| A 404 cover on detail renders the shared fallback | component | `DetailPage.test.tsx` |
| `PageHeader` renders eyebrow/title/count/actions; every page uses it | component | `components/PageHeader.test.tsx` (new) |
| `SegmentedControl` keeps `aria-pressed` semantics and a 44px target | component | `components/SegmentedControl.test.tsx` (new) |
| `DomainStrip` renders declared domains and marks the active one | component | `components/DomainStrip.test.tsx` (new) |
| `/` at 390px with five domains does not scroll the body | e2e | `frontend/e2e/library.spec.ts` |
| `/insights` at 390px still does not scroll the body | e2e | `frontend/e2e/insights.spec.ts` |
| No serious violations on the six screens | e2e | `frontend/e2e/accessibility.spec.ts` |

## Verification

- `make check`, `make test`, `python scripts/validate_project.py`
- `npx playwright test` — **owed**: every screen's markup changes.
- **Walkthrough (DEC-025), and it is the only real evidence for this work** (proposal §6):
  every screen opened at 1280px and at 390px against real imported data, in a browser, with
  an empty console-error log — and reported, screen by screen, saying what actually looked
  different. A cosmetic sprint verified only by unit tests has verified nothing.
- No backend gate is owed: this sprint changes no Python file.

## Explicit non-scope

- **Shelves as a ranking, the active-filters row, and weighted counts** — Sprint 071. This
  sprint does not add a field to any response.
- The virtualized library's geometry (DEC-023) and triage's interaction model
  (DEC-095, DEC-096).
- A light theme, a second accent, a new typeface, a component-library swap, a new
  dependency — proposal §5.
- Copy rewriting beyond the lines named in §3.2 and §3.6.
- The export tab. If Sprint 069 has shipped, it gets the primitives like any other screen;
  if it has not, nothing here waits for it.

## Commit checkpoints

1. `[ADD] One box, and one heading inside it`
2. `[MOD] Every page starts the same way, and goes back the same way`
3. `[ADD] Write the domain strip and the toggle once`
4. `[FIX] Fit the domain strip on a phone` (DEC-134's outstanding defect)
5. `[MOD] Draw the biggest cover the way we draw the small ones`
6. `[FIX] Stop painting a staged cover like a perfect score`
7. `[MOD] Say what went wrong in the domain's own words`

## Risks and decisions to surface

- **A sprint that touches every page is the easiest place here to break something
  quietly.** The mitigation is acceptance criterion 9 and nothing else: suites pass
  unchanged, and no test is rewritten to fit a class name unless the sprint names it.
- **Extracting a primitive can flatten a difference that existed for a reason.** Keep the
  ones that can be justified in a sentence; the outcome lists them.
- **The 390px strip is a five-domain problem today and a six-domain problem later.** A
  scrolling strip fixes the class; anything that puts it back in a `flex-wrap` row
  reintroduces it.
- **`AddPage` gaining a header changes a screen tested by `add-detail.spec.ts`.** Expected,
  and named here so it is not mistaken for a regression.

## Outcome

**Status: completed, 2026-09-04.** All 8 deliverables and all 10 acceptance criteria met.
Commits: `bc0323f` (primitives), `abebbe2` (domain strip/toggle extracted), `a7e383a`
(Detail's cover and panels), `5ba37ef` (Shelves/Add headers), `e82481c` (import score/
cover-staged chips), `6085448` (DEC-134 fix), `90d8600` (e2e finding-3 assertion),
`d48817d` (amber heading retired everywhere it hid).

**Delivered.**

1. **`Panel`** (`frontend/src/components/Panel.tsx`) — `rounded-xl border border-border
   bg-surface`, optional heading + right-hand stat row, `bodyClassName` for callers that
   need their own internal spacing rather than one imposed scale. `InsightsCard` now
   builds on it (the generalization); Detail's personal region, Files region, Edition
   facts and tracklist regions, and Import's form/preview-row/undo boxes all carry the
   same chrome now.
2. **The amber uppercase heading retired**, everywhere it appeared — not only the four
   box idioms finding 7 cited, but two more instances the same pass found nested inside
   already-touched content: `Attachments.tsx` (mounted inside Detail's Files panel) and
   `CandidateFacts.tsx` (the add-flow confirm card). `git grep "uppercase tracking-wider
   text-primary"` returns nothing in `frontend/src`.
3. **`PageHeader`** (`frontend/src/components/PageHeader.tsx`) — eyebrow/title/count/
   lede/actions, applied to Library, Shelves, Add, Import and Triage. `BackToLibrary`
   (`frontend/src/components/BackToLibrary.tsx`) is the one *"← Library"* control,
   replacing the ghost button (Detail/Shelves/Add), the outline pill (Triage), the bare
   `<Link>` (Import) and the words *"← Back to library"* (Import's undo panel) — four
   spellings down to one.
4. **`SegmentedControl`** (`frontend/src/components/SegmentedControl.tsx`), extracted
   from Grid/Table and Most collected/Best rated, `min-h-11` on every option now (only
   one copy had it before).
5. **`DomainStrip`** (`frontend/src/components/DomainStrip.tsx`), extracted from the two
   radiogroups, scrolling within itself (`overflow-x-auto`, `min-w-0`, `max-w-full` on
   the strip, `shrink-0` moved to its buttons) instead of refusing to shrink and pushing
   the document sideways. Paid DEC-134 once for both `/` and `/insights` — see the
   deviation below on what else that actually took.
6. **Every cover through `CoverImage`**, including Detail's — decode-reveal, the shared
   placeholder, "Cover failed to load" on a 404 instead of a broken-image glyph.
7. **The import preview speaks the application's language**: the score renders in
   `scoreChipClass`/`scoreChipShape`, the same chip Detail and the library card use;
   *Local cover staged* is a neutral `bg-surface-raised` chip, not `text-score-top`; a
   field error renders through `frontend/src/features/import/errors.ts`'s
   `describeRowError` — the domain's declared label (from `/api/item-types`, when the
   active importer names exactly one domain) or a small static/humanized fallback, plus
   a wording table covering every code the shipped readers raise — instead of
   `{field}: {code}`.
8. **Justified differences kept, one sentence each**: the library's translucent
   `bg-surface/60`/`bg-surface/40` cards sit under a virtualized list with a pinned
   geometry (DEC-023) and were not touched; the connector guide's quieter
   `bg-surface-raised` box (no border) stays deliberately quieter than the form beside
   it; Detail's title/subtitle/creator/year block stays beside the cover rather than
   becoming a `PageHeader`, because it is item detail rather than a listing page (only
   its back control unified); `/insights` itself keeps its own existing header (it is
   the screen these primitives generalize *from*, not one of the six being unified) —
   `DomainStrip` and `SegmentedControl` replace its two duplicated controls, `Panel`
   generalizes `InsightsCard`, `PageHeader` does not apply to it.

**Acceptance criteria.**

1. No surface outside a score renders in a score-ramp colour — `ImportPage.test.tsx`
   and `e2e/import.spec.ts` assert the staged-cover chip carries no `text-score-*`
   class; `git grep` confirms no remaining literal use outside `lib/score.ts`,
   `ScorePicker`, and the insights legend.
2. A preview score renders in the same band class as the library card and the detail
   page — `ImportPage.test.tsx` asserts `bg-score-top` on a score of 9, matching
   `scoreChipClass(9)`.
3. A failed preview row names the domain's declared label and a legible wording, never
   `field: code` — `ImportPage.test.tsx` and `e2e/import.spec.ts` both updated (see
   deviation below on what "declared" actually means with no backend change).
4. A 404'd Detail cover shows the shared `CoverImage` failure fallback —
   `DetailPage.test.tsx`, two new tests (the 404 case and the no-cover case).
5. Every page renders its header through one component — Library, Shelves, Add, Import,
   Triage all render through `PageHeader`; `git grep` for the old per-screen header
   markup (the brand-lockup eyebrow pattern, the bare `text-4xl` h1 outside
   `PageHeader.tsx`) returns nothing except Detail's and Insights' own, both justified
   above.
6. One way back, reading the same on Detail, Shelves, Add, Triage and Import —
   `BackToLibrary`, five places, one string. `e2e/live-metadata.spec.ts` updated (its
   Detail assertion moved from `role: "button"` to `role: "link"`, finding 8).
7. `/` and `/insights` hold at 390px with five domains, the strip scrolling within
   itself, 44px targets — new e2e tests in `e2e/library.spec.ts` and extended
   `e2e/insights.spec.ts` (both needed a real fix, not just a test — see the deviation
   below).
8. Zero serious axe violations on Library, Detail, Shelves, Add, Import, Triage —
   `e2e/accessibility.spec.ts`, full run, unchanged assertions, all green.
9. Existing suites pass unchanged except where a test asserted one of the eleven
   findings, each named here: `ImportPage.test.tsx` ("previews and commits a confined
   Calibre library...", finding 1/2; "previews once, exposes errors...", finding 3);
   `e2e/import.spec.ts` ("row errors and ambiguity require an explicit choice", finding
   3); `e2e/live-metadata.spec.ts` (its Detail back-button assertion, finding 8).
   `e2e/library.spec.ts` and `e2e/insights.spec.ts` gained new/extended tests rather
   than changed assertions — deliverable 5's own instruction that the viewport test
   "extends to `/`".
10. `VirtualLibrary.tsx` untouched — confirmed by `git diff --stat`, zero lines.

**Deviations, recorded rather than guessed past.**

- **AC3's "domain's declared label" and "connector's declared wording" do not exist as
  backend declarations for row-level field errors** — only `ImportReadError` (a whole-
  file refusal) carries `user_message`/`action` (DEC-080). A field error's `field`/`code`
  pair is either already a human phrase (`imdb.py`, `letterboxd.py`, `trakt.py` pass
  `"Your Rating"`, `"Watched Date"`) or a raw internal name (`goodreads.py`,
  `calibre.py`, `myanimelist.py` pass `isbn`, `my_rating`, `series_animedb_id`), and this
  sprint's own Verification section says no Python file changes. `describeRowError`
  resolves what it honestly can — an entry field or a metadata `FieldSpec` from
  `/api/item-types`, when the active importer names exactly one domain — and humanizes
  the rest (`date_read` → `Date read`) rather than inventing a backend contract. This is
  the ceiling of a presentation-only fix; a connector-declared field/error vocabulary
  would be new backend scope for a future sprint if the humanized fallback ever reads
  wrong for a specific code.
- **Paying DEC-134 took one more line than the strip itself.** `DomainStrip`'s own
  `overflow-x-auto`/`min-w-0`/`max-w-full` was not sufficient on `/insights`: its
  immediate parent (the `role="group" aria-label="Ranking controls"` wrapper) was itself
  an unconstrained flex item, so the strip's `max-w-full` resolved against that parent's
  own unclamped width rather than the viewport. Fixed at the parent
  (`min-w-0 max-w-full` added to `InsightsPage.tsx`'s Ranking-controls group) — the
  actual mechanism, found only by measuring computed styles once the naive fix still
  measured 47px of overflow. `/` needed no equivalent fix; its domain strip's immediate
  parent is a plain flex row directly inside `<main>`, not nested inside a second flex
  group.
- **`useItemTypes` in `ImportPage.tsx` is now enabled whenever a previewed record has an
  error**, not only when an importer declares more than one target domain. Narrowly
  scoped to avoid an unconditional new fetch on every Import visit; guarded with
  `Array.isArray` since a test's fetch mock can answer the wrong shape and must not
  crash the page.

**Verified.**

- `make check` — green (backend ruff format/check, mypy; frontend prettier, eslint,
  tsc, `npm run api:check`; `scripts/validate_project.py`).
- `make test` — backend **1,352** passed (unchanged: no Python file touched). Frontend
  **266** passed (was ~253 before this sprint's new/changed tests).
- `npx playwright test` (parallel, chromium + heavy-library + production-bundle
  projects) — **119 passed, 2 skipped** (the two `LIVE_METADATA_MODE`-gated tests),
  three consecutive runs; one run hit a single pre-existing timing flake
  (`library.spec.ts` "keyboard guards and reduced motion remain effective", a
  search-debounce race unrelated to any file this sprint touched — green in isolation
  and on both full reruns).
- **Walkthrough (DEC-025), done.** A throwaway backend (`scripts/walkthrough.py --keep`
  on an ephemeral port) seeded through the real HTTP API — 5 domains, 11 entries, real
  1x1-pixel JPEG covers uploaded to 6 of them via `POST /api/items/{id}/cover`, one
  book left `unsorted` for Triage, a "Favorites" shelf holding 5 entries — served behind
  a real Vite dev server (`AKASHA_E2E_BACKEND`) on a scratch port. A real Chromium
  instance (Playwright, no route stubbing) visited Library, Detail, Shelves, Add, Import
  and Triage at 1280px and 390px: zero console errors and zero horizontal body overflow
  on every one of the twelve combinations but one (below); every screen's header, back
  control and box chrome visually consistent (screenshots inspected); Detail's cover
  the shared `CoverImage` treatment at full size; Triage's header now identical in shape
  to Library's and Import's. `/insights` also checked (not in scope, to confirm the
  extracted primitives did not regress it): unaffected, zero overflow at both widths.
  The owner's own instance at `:8000` was untouched throughout (confirmed reachable and
  healthy before and after); the throwaway backend, frontend dev server and data
  directory were torn down at close.

  **One defect found, out of scope, not fixed here, per the walkthrough gate's own
  rule:** `/import`'s "Choose an import source" connector strip (`ImportPage.tsx`'s
  `sourceStrip`, a shadcn `TabsList` with no width constraint) overflows a 390px
  viewport by about 205px with the real backend's seven registered importers (Goodreads,
  Calibre, MyAnimeList, Letterboxd, IMDb, Trakt, Spotify). This is a different control
  from DEC-134's domain radiogroup — not named by any of the proposal's eleven findings,
  not one of this sprint's deliverables — and confirmed pre-existing by `git diff` (this
  sprint's diff touches no line of `sourceStrip` or its container). Recorded in
  `docs/decisions.md` DEC-137 and carried forward in `docs/agent/HANDOFF.md`.

**Next:** Sprint 071 — What the numbers say (shelves as an openable ranking, an
active-filters row, weighted counts). It depends on this sprint's primitives, which are
now built and available.
