# Sprint 066 — Insights you can read

**Status:** completed
**Depends on:** 065
**Roadmap revision:** 36

> Planned from [`../insights-redesign-proposal.md`](../insights-redesign-proposal.md) and
> **accepted by the owner as DEC-132.**

## Objective

Make `/insights` answer on arrival, in colour, without a round trip — against
`GET /api/insights` exactly as Sprint 065 shipped it. No change to the ranking query, the
domain contract, or the response contract is required by this sprint.

## Required context

- [`../insights-redesign-proposal.md`](../insights-redesign-proposal.md) — **read first.**
  §1 is the evidence, §2.1–2.6 are this sprint's deliverables, §5 is what it must not do.
- [`065-insights.md`](065-insights.md) — the feature as built, its non-scope, and the
  walkthrough it still owes.
- `docs/decisions.md` DEC-026 (the design tokens and the score ramp), DEC-023 (the
  virtualization contract — this sprint must not touch it), DEC-131 (the ranking query and
  its measured budget).
- `docs/brand/BRAND.md` — one accent, and no second one.
- Code, read fresh: `frontend/src/pages/InsightsPage.tsx`, `frontend/src/lib/score.ts`,
  `frontend/src/features/library/labels.ts` (`insightKeyOptions`), `useInsights.ts`,
  `InsightsKeyPicker.tsx`, `frontend/src/pages/HomePage.tsx`
  (`filtersFromParams`/`paramsFromFilters`), `frontend/src/api/library.ts`.
- Tests: `frontend/src/pages/InsightsPage.test.tsx`, `frontend/e2e/accessibility.spec.ts`.

## Current implementation baseline

- The page is a query builder: domain pills, a key popover, a count/score toggle and a
  `min_rated` number input above one table. `InsightsPage.tsx` is 270 lines and holds all of
  it.
- **`scoreChipClass` and `scoreChipShape` already exist** in `lib/score.ts` and are used by
  the library card, the triage row and the detail page. The insights table does not import
  them.
- **`score_spread` is served on every row and rendered nowhere.** It is a population standard
  deviation (`application/library.py:1187`).
- **`rated_count` and `mean_score` are served in both metrics** and rendered only in `score`.
- `<th>{key}</th>` prints the raw field name; `insightKeyOptions` already carries the domain's
  declared label beside it.
- The `key`/`value` library filter exists end to end and is read back by `filtersFromParams`,
  but the library shows no sign that it is filtered by one.

## Deliverables

1. **The score chip.** Mean score rendered through `scoreChipClass`/`scoreChipShape`,
   unchanged from every other surface. An unrated group renders the absence, not a band. A
   score ramp legend appears once on the page.
2. **Magnitude bars.** Each row filled to `count / max(count)` of its own ranking, amber,
   behind the label; row labels return to `foreground` ink so the accent encodes the quantity
   and nothing else. Bars are decorative to assistive technology — the count is text.
3. **Both metrics on one row.** The count/score toggle becomes a *sort order*, not a data
   mode: every row shows bar, count, rated count and score chip regardless. Under score
   order, rows below `min_rated` render beneath an `n not rated enough to place` divider
   instead of being dropped.
4. **A card per key.** The key popover is replaced by a responsive grid of ranking cards, one
   per groupable key plus `year`/`decade`, six rows each with *Show n more*. Each card is
   titled with the **domain's declared label** (`Artists`, not `creators`).
5. **Interestingness ordering, and a quiet-keys line.** Cards ordered by the §2.5 rule; keys
   failing it collapse to one line naming each key and its values inline.
6. **Inline expansion.** A row click expands to its members — cover placeholder, title, year,
   score chip — fetched with the existing `key`/`value` entries filter, plus a link into the
   filtered library. The row is a disclosure with correct `aria-expanded`; the link is a link.
7. **The library breadcrumb.** When `HomePage` renders with `key`/`value` set, a dismissable
   chip names where the filter came from and clears both params.
8. **Chrome demoted.** `min_rated` leaves the control row for a disclosure worded in English;
   the suppression and null-year notices become inline chips in the card that owns them.
9. **Optional, measured not assumed:** a batched `keys=` parameter on `GET /api/insights` if
   deliverable 4's request count is shown to cost anything real. If it is not measured, it is
   not added.

## Acceptance criteria

1. A ranking row with a mean score renders it in the DEC-026 band colour for that score, with
   the numeral visible; nothing on the page is distinguishable by hue alone.
2. Two rows with counts 7 and 3 render bars whose widths differ in the same proportion.
3. Every row shows both count and score information under both sort orders; no row's data
   depends on the toggle.
4. Under score order, a group with fewer than `min_rated` rated entries is present, below the
   divider, and is not silently absent.
5. Every card is titled with the label the domain declares for that key, for at least two
   domains whose label for `creators` differs.
6. Ordering: given a key whose values all hold one entry and a key with a clear leader, the
   second gets a card and the first appears only in the quiet-keys line.
7. Expanding a row shows exactly the entries the ranking counted, without navigating; the
   library link from the same row lands on the same set.
8. A library page reached from a ranking shows the breadcrumb naming the key and value, and
   clearing it restores the unfiltered library.
9. The whole page is usable at 390px wide: cards stack, nothing scrolls the body sideways,
   every control keeps a 44px target.
10. Zero serious axe violations on the page in both sort orders, with a row expanded.

## Required tests (TDD)

| Behavior | Layer | File |
|---|---|---|
| Mean score renders with its band class; unrated renders the absence | component | `InsightsPage.test.tsx` |
| Bar width is proportional to count within a card | component | `InsightsPage.test.tsx` |
| Both metrics render under both sort orders | component | `InsightsPage.test.tsx` |
| Below-threshold groups render under the divider, not dropped | component | `InsightsPage.test.tsx` |
| Card titles use the domain's declared label, for two domains | component | `InsightsPage.test.tsx` |
| Interestingness ordering; an all-ones key lands in the quiet line | unit | `features/library/insights.test.ts` (new) |
| Expanding a row requests the `key`/`value` filter and lists its members | component | `InsightsPage.test.tsx` |
| The library breadcrumb renders from params and clears them | component | `HomePage.test.tsx` |
| The page has no serious accessibility violations, row expanded | e2e | `frontend/e2e/accessibility.spec.ts` |
| The page at 390px does not scroll the body horizontally | e2e | `frontend/e2e/insights.spec.ts` (new) |

## Verification

- `make check`, `make test`, `python scripts/validate_project.py`
- `npx playwright test` — **owed**: a rewritten screen and a new request path.
- **Walkthrough (DEC-025):** against a library with real imported data, open the redesigned
  page for every domain, expand rows, follow a link into the library and come back through the
  breadcrumb. Report what the rankings actually looked like — this sprint does **not**
  discharge Sprint 065's outstanding walkthrough, and should be run alongside it.
- No backend gate is owed unless deliverable 9 is taken, in which case
  `test_insights_api.py` and the exhaustive backend suite are owed with it.

## Explicit non-scope

- Covers on a ranking row, library totals, and the endpoint's filter passthrough — Sprint 067.
- Anything in the proposal's §5: cross-domain rankings, entity pages, time series, new
  metrics, grouping by entry fields.
- Touching `VirtualLibrary` or the DEC-023 virtualization contract. Ranking cards are short
  lists and are not virtualized.
- Changing `rank()`, the response schema (except deliverable 9's optional parameter), or any
  domain's `groupable` declaration.

## Commit checkpoints

1. `[MOD] Paint an insights score with the ramp every other screen uses`
2. `[MOD] Make a ranking row show its own proportion`
3. `[MOD] Rank by an order, not by which half of the data you get`
4. `[ADD] A card per key, titled the way the domain names it`
5. `[ADD] Order the cards by what they have to say`
6. `[ADD] Open a ranking row without leaving the page`
7. `[ADD] Say where a library filter came from`

## Risks and decisions to surface

- **Request count (deliverable 9).** Measure before adding a parameter. Six parallel requests
  against a personal library may cost nothing at all.
- **The ordering heuristic will be argued with.** That is expected and is why it is one
  sentence of client-side arithmetic rather than a server-side declaration.
- **A tiny library still produces tiny cards.** The quiet-keys line is the mitigation, and
  saying "nothing to rank here yet" plainly is the acceptance criterion, not hiding it.

## Outcome

**Delivered.** All nine deliverables and acceptance criteria 1–10 are built and tested.
The material findings — a defect this sprint had to repair, deliverable 9 answered by
measurement, and what the ordering rule does to a real album library — are **DEC-133**.

- **Deliverable 1 (the score chip).** `meanScoreChipClass` added to `lib/score.ts` and used
  for every mean on the screen; the ramp legend sits once under the header. The helper is the
  only new thing rather than a straight reuse of `scoreChipClass`: the ramp is defined on the
  ten scores a person can give and a mean is a real number between them, so it bands by the
  score it is nearest — 8.8 reads as a 9, where banding the raw value would file it with 7.0.
- **Deliverable 2 (magnitude bars).** `InsightsRanking` replaces the table. The row *is* the
  bar, filled to its share of its own ranking's leader; labels returned to `foreground` ink,
  so the accent encodes a quantity instead of colouring twelve identical links.
- **Deliverable 3 (both metrics, one row).** `orderRows` in the new
  `features/library/insights.ts`. The toggle is a sort order and both numbers are on every
  row under either one. Rows below `min_rated` render under an `n not rated enough to place`
  divider instead of being dropped by the server.
- **Deliverable 4 (a card per key).** `InsightsCard`, in a responsive grid, one per groupable
  key plus `year`/`decade`, six rows and *Show n more*. Titled with the label the **domain**
  declares — the shipped `<th>{key}</th>` printed the raw field name for every domain alike.
  `InsightsKeyPicker.tsx` deleted; nothing else imported it.
- **Deliverable 5 (ordering, and a quiet line).** `keyLead`, `orderKeys` and `quietSummary`,
  unit-tested in `insights.test.ts`. A key with fewer than three values held more than once
  states itself in one line rather than rendering a two-row table.
- **Deliverable 6 (inline expansion).** `InsightsMembers` + `useInsightMembers`, over the
  `key`/`value` filter Sprint 065 already built, four entries highest-scored first, fetched
  only when a row is opened, one row open at a time. The library link is a `Link` at the end
  of the panel rather than the whole of what a row does.
- **Deliverable 7 (the breadcrumb).** `LibraryFilters.valueLabel` carries the display
  spelling (the `value` is normalized and unreadable); `libraryQueryString` still does not
  send it. The chip names the filter and clears it.
- **Deliverable 8 (chrome demoted).** `min_rated` is a sentence below the cards, shown only
  under the score order; suppression, the null-year count and the depth bound are inline
  notes in the card that owns them.
- **Deliverable 9 (the batch parameter): measured, and deliberately not added.** Seven
  parallel rankings cost a 17 ms median on a 60-entry library, and at 5,000 entries each is
  inside its own budget (`creators/count` 277.8 ms p95, unchanged from DEC-131). A batch
  would remove none of that work and would trade card-by-card painting for one slow paint.
  Full numbers and reasoning in DEC-133.

- **Prerequisite defect repaired (recorded, per AGENTS.md §2.4):**
  `GET /api/insights?key=year` and `key=decade` returned **500** and had since Sprint 065
  shipped them — `rank()` produced integer keys against a response schema declaring strings.
  A screen that ranks every key a domain offers cannot render with two of them 500ing, so it
  was fixed here: `_insight_row` coerces, two API tests cover the ranking and the round trip
  into the library, and `test_insights.py`'s assertion — which had asserted the int — is
  corrected. Found on the walkthrough's first real request. **DEC-133 finding 1.**

- **Verification.** `make check` green. Backend **1,328** passed (1,326 + 2). Frontend
  **231** passed (218 + 13). Full Playwright suite: **113 passed, 2 skipped, 0 failed** —
  including the two new `e2e/insights.spec.ts` layout tests and the three new axe checks in
  `e2e/accessibility.spec.ts` (Insights had none before this sprint).
  `scripts/benchmark_library.py --entries 5000 --jobs 100`: every scenario inside the 500 ms
  budget. `python scripts/validate_project.py` green. `make smoke-container` **not owed** —
  the diff touches no deployment configuration, and the sprint's Verification section does
  not name it.

- **Two acceptance criteria found real defects, which is why they were browser-level.** The
  sort toggle was 36 px, short of the 44 px target every other control keeps (AC9); and
  `aria-controls` on a ranking row pointed at nothing, because the panel id was built from
  the grouping value and `julio cortázar` has a space in it (AC10). Neither would have
  survived review.

- **Walkthrough (DEC-025), done.** A throwaway backend on `:8010` and a dev frontend on
  `:5180` against a `/tmp` data directory — the owner's own instance on `:8000` was left
  alone — seeded through the real HTTP API with 60 entries shaped after the viability
  measurement. Every domain ranked, both orders, rows opened, a link followed into the
  library and the breadcrumb cleared, at 1280 px and at 390 px, with an empty console-error
  log. Normalization merged `julio cortazar`, `China Mieville`, `Bjork` and
  `Angelica Gorodischer` into their accented rows; `Various Artists` was suppressed with the
  note offering it back. What the rankings actually looked like, including the album
  ordering that puts Label above Artists, is DEC-133 finding 3.

  **Still owed to the owner, and not discharged by this:** the same walkthrough against the
  owner's *real* imported library — Sprint 064's Spotify albums and the Calibre books — and
  the report of whether score density makes the score order worth having. That data lives in
  the owner's own container.
