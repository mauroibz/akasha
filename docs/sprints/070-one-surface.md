# Sprint 070 — One surface

**Status:** ready
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

_Not started._
