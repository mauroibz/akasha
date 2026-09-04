# The rest of the app, redrawn — a cohesion proposal

**Status: proposal.** Written 2026-09-04 at the owner's request, alongside
[`export-proposal.md`](export-proposal.md), as the two features that close the next minor
release. It is written to be accepted, rejected, or cut down. Nothing here is built.

The owner's words: *"the last sprints involved a redesign to the UI of the new insights
feature. I want you to look at the rest of the app and apply some of the new design
principles to it, so everything feels cohesive."*

Sprints 066 and 067 did not invent a style. They took decisions this application already
had — DEC-026's score ramp, `BRAND.md`'s single accent, DEC-080's render-the-declaration
rule — and applied them to one screen properly. The result is that `/insights` is now the
most coherent surface in the product, and the distance between it and everything else is
the subject of this document.

---

## 1. What Sprints 066 and 067 actually established

Seven rules, each with a reason rather than a taste. They are stated here because a
cohesion pass needs a target, and "make it look like insights" is not one.

1. **A colour means one thing wherever the eye lands.** The score ramp is red 1–3, amber
   4–6, lime 7–8, emerald 9–10, and it paints scores and nothing else. Anything else
   painted in it teaches the eye that the colour is decoration (DEC-026, proposal §2.1).
2. **A number that is a proportion is drawn as one.** `7` and `3` at identical weight is a
   ranking that does not rank. The row is filled to its share, and that is the only honest
   use of the accent on a list (proposal §2.2).
3. **A row carries the faces of what it counted.** The library holds jackets, sleeves and
   posters; an aggregate of them rendered as text is a database, not a shelf (§2.8).
4. **A row opens where it is, and a filter says where it came from.** Exploring is not
   back-button ping-pong, and a filtered screen that does not name its filter looks like a
   screen that lost your data (§2.6).
5. **A notice lives inside the thing it describes.** Grey paragraphs at the foot of a page
   are the right information in the least likely place to be read (§2.5, DEC-132).
6. **A control is worded, not configured.** `min_rated` stopped being a number spinner and
   became a sentence; the suppressed values became a chip you press. A reader's screen has
   no developer controls on it.
7. **Every surface holds at 390px, with 44px targets, and is proven by axe.** Not asserted:
   `e2e/insights.spec.ts` measures the body's scroll width, and the accessibility spec runs
   with a row expanded.

Under all seven sits the older rule that makes them cheap to keep: **a screen renders a
declaration; it does not branch** (technical spec §6.6, DEC-080). A shared primitive is
that rule applied to the visual layer.

---

## 2. What the rest of the application does instead

Eleven findings, each traced to a line rather than to an impression.

| # | Finding | Where |
|---|---|---|
| 1 | **The score ramp is used for something that is not a score.** The import preview paints *"Local cover staged"* in `text-score-top` — emerald, which on every other screen means a 9 or a 10. | `ImportPage.tsx:710` |
| 2 | **A score is rendered as prose on the screen where hundreds of them arrive.** The preview writes `· rating 8` and `· provisional score 8` into a muted sentence. This is insights finding 1, one screen over, on the surface that introduces a whole library. | `ImportPage.tsx:700-707` |
| 3 | **Raw field names and error codes reach the reader.** A failed preview row prints `{row.field}: {row.code}` — `date_finished: invalid_date` — while the domain declares a label for that field and the connector declares wording for its errors. | `ImportPage.tsx:714-721` |
| 4 | **The biggest cover in the application is the only one not drawn by `CoverImage`.** The detail page uses a bare `<img>` and a hand-rolled empty box: no decode-reveal, no shared placeholder, and a URL that 404s leaves a broken-image glyph where every other surface would say *No cover*. | `DetailPage.tsx:271-284` vs `CoverImage.tsx:20-48` |
| 5 | **The shelves screen cannot open a shelf.** A row is a name, a count, *Rename* and *Delete*. The library filters by shelf perfectly well (`/?shelf=slug`), and nothing on this page links to it — the one screen about shelves is the one place a shelf is a dead end. | `ShelvesPage.tsx:150-215` |
| 6 | **A shelf's count is a proportion drawn as text**, on a list whose whole subject is how much is on each shelf — and with no faces, on a page listing groups of covered items. Findings 2 and 3 of §1, on the most obviously ranked screen in the product after insights. | `ShelvesPage.tsx:193-197` |
| 7 | **Two card idioms, two radii, three heading styles.** Insights cards are `rounded-xl border border-border bg-surface` with a plain `text-sm font-semibold` title and a stat on the right. Detail regions are `rounded-xl border border-border p-5` with an amber `uppercase tracking-wider` heading. Import panels are `rounded-2xl bg-surface p-5` with no border and no heading rule at all. The connector guide is `rounded-xl bg-surface-raised p-4`. Shelf rows are `rounded-xl border border-border px-5 py-4`. Library cards are `rounded-2xl bg-surface/60` inside `rounded-2xl bg-surface/40`. | `InsightsCard.tsx:55`, `DetailPage.tsx:99,353,461,469`, `ImportPage.tsx:523,693,885,939`, `ConnectorGuide.tsx:29`, `ShelvesPage.tsx:153`, `VirtualLibrary.tsx:257,315` |
| 8 | **Three page headers and four ways back.** Library and Triage carry the brand lockup with a wide-tracked eyebrow; Insights has a plain title and a lede; Import has a title and no lockup. Going back is a ghost button at `px-0` on Detail, Shelves and Add; an outline pill in the header actions on Triage; a bare `<Link>` on Import; the words *← Back to library* in Import's own success panel; and nothing at all on Insights. | `HomePage.tsx:534-548`, `TriagePage.tsx:628-646,662-670`, `InsightsPage.tsx:113-124`, `ImportPage.tsx:496-499,953`, `DetailPage.tsx:267`, `ShelvesPage.tsx:88`, `AddPage.tsx:52` |
| 9 | **The domain strip is written twice, and it overflows at 390px in both places.** The library's and the insights page's radiogroups are the same markup down to the class list. DEC-134 recorded the overflow — about 39px past a 390px viewport with five domains — on `/insights` and left it out of scope; `/` has the same `shrink-0` pills and has never been measured with five domains. | `HomePage.tsx:578-608`, `InsightsPage.tsx:136-158`, DEC-134 |
| 10 | **The segmented control is written twice too.** *Grid / Table* and *Most collected / Best rated* are both `flex rounded-full bg-surface p-1` around ghost buttons with `aria-pressed`, differing only in that one sets `min-h-11` and the other does not. | `HomePage.tsx:759-796`, `InsightsPage.tsx:163-186` |
| 11 | **Only one filter says where it came from.** `InsightFilterChip` names the insights `key`/`value` filter and offers to drop it. Shelf, format, status and the search query — the filters a reader actually sets — are states inside select triggers, so a library narrowed to eleven rows explains itself only if you go looking in three controls. | `HomePage.tsx:748-757,978-1002` |

Two smaller ones, recorded so they are not rediscovered: the import preview's summary line
(`N ready · N need a choice · N have errors`) is three numbers with no weight between them;
and `AddPage` has no header treatment at all, which is defensible for a form reached
deliberately but makes it the fourth page shape.

**None of these is a defect in behaviour.** Every screen works, and its tests pass. What
they add up to is that the application looks like six screens built in sequence, which is
exactly what it is.

---

## 3. What replaces it

### 3.1 One panel

A `Panel` primitive in `components/`: `rounded-xl border border-border bg-surface`, a
heading slot, an optional right-hand stat slot, one padding scale. It is the insights card
generalized, and it replaces the hand-built boxes on Detail, Shelves, Import and Add.

The amber uppercase heading on the detail page does not survive as a second style — it
becomes the panel's heading like every other, because §1's first rule is about the accent
too. Amber marks quantity and active state; it does not mark "this is a heading".

### 3.2 One page header, one way back

A `PageHeader` primitive: eyebrow, title, optional count, lede, actions slot. Every screen
uses it, and *← Library* is one control in one place rather than four spellings.
`AddPage` gains a header it currently lacks.

### 3.3 One segmented control and one domain strip, written once

`SegmentedControl` and `DomainStrip` extracted from the two copies each. The strip scrolls
horizontally below its breakpoint instead of pushing the document sideways, which pays
DEC-134's outstanding 390px defect **once, for both screens**, and the e2e viewport test
that Sprint 066 wrote for `/insights` extends to `/`.

### 3.4 Every cover through `CoverImage`

Including the largest one. The detail page gets the decode-reveal, the shared placeholder
and the failure fallback the rest of the application has had since Sprint 055.

### 3.5 The shelves screen becomes a ranking you can open

A shelf row is an insights row: a magnitude bar for its share of the largest shelf, up to
three covers of what is on it, the count, and the name as a link into `/?shelf=slug`.
*Rename* and *Delete* stay where they are.

This needs one backend field — `covers: list[str]` on the shelves response, the same
lateral top-3 join `InsightRowResponse.covers` already does and DEC-134 already
benchmarked. It is the only backend change in this proposal.

### 3.6 The import preview speaks the application's language

The score becomes the chip every other surface paints; *Local cover staged* stops
borrowing the score ramp and becomes a neutral chip; a field error names the domain's
declared label and the connector's declared wording rather than `field: code`; and the
summary line becomes three counts with visible weight.

### 3.7 A filter says where it came from, whichever filter it is

`InsightFilterChip` generalizes into an active-filters row: one dismissable chip per set
filter — shelf, format, status, query, insights key — above the library. The selects keep
their state; the chips are what makes a narrowed library legible at a glance, and they are
the same shape the insights breadcrumb already taught.

### 3.8 Counts carry weight

Wherever a set of counts describes one whole — shelf sizes, status facets, the preview
summary — the larger number is visibly larger. The bar is the one already built
(`magnitude` in `features/library/insights.ts`), reused rather than re-derived.

---

## 4. What it costs

Two sprints. The split is at the same boundary the last redesign used: everything that
needs no new data first, everything that does second.

| Sprint | Delivers | Backend |
|---|---|---|
| **[071 — One surface](sprints/071-one-surface.md)** | §3.1–3.4 and §3.6: the `Panel`, `PageHeader`, `SegmentedControl` and `DomainStrip` primitives, applied across Detail, Shelves, Import, Add, Triage and Library; every cover through `CoverImage`; the import preview's chips, labels and misused ramp; the 390px overflow paid once. | **None.** |
| **[072 — What the numbers say](sprints/072-what-the-numbers-say.md)** | §3.5, §3.7 and §3.8: shelves as an openable ranking with covers and bars, the active-filters row, and weight on the counts that describe a whole. | `ShelfWithCount.covers`, one lateral join. |

Neither sprint changes a screen's behaviour, and that is the acceptance criterion that
holds them honest: **the existing component and e2e suites pass unchanged**, except where a
test asserts one of the eleven findings above, in which case the change is the point and is
named in the sprint.

## 5. What this proposal deliberately does not do

- **No new colour, no second accent, no new typeface.** `BRAND.md` says the mark needs no
  second brand colour and must not acquire one. Everything here uses the DEC-026 tokens.
- **No light theme.** The application is dark-first by decision (product spec §7) and runs
  next to Jellyfin at night.
- **No change to the virtualized library's geometry.** DEC-023 pins the card box, the row
  height and the column count; a padding change inside a virtualized card is a measurement
  change, not a paint change, and this proposal keeps out of that box.
- **No change to triage's interaction model.** The row-local apply, the selection model and
  the keyboard flow are settled (DEC-095, DEC-096) and are not reopened for looks.
- **No component-library swap and no new dependency.** shadcn/ui source, Tailwind tokens,
  Motion as it is configured.
- **No copy rewrite** beyond the lines named in §3.6 and §3.2.
- **No new screens and no navigation change.** The export tab is the other proposal's.

## 6. Risks

- **A "cosmetic" sprint that touches every page is the easiest place in this repository to
  break something quietly.** The mitigation is the rule in §4: suites pass unchanged, and
  no test is rewritten to fit a new class name unless the sprint names that test.
- **Extracting a primitive can flatten a deliberate difference.** Three of the boxes above
  differ for reasons — the library's translucent surface sits under a virtualized list, the
  connector guide is deliberately quieter than the form it sits beside. Sprint 071 must
  keep a difference it can justify in one sentence and unify the rest, rather than making
  everything identical and calling that coherence.
- **Screenshots are the only real evidence for this work, and this repository's gates do not
  take screenshots.** The walkthrough gate (DEC-025) is the actual verification here: every
  screen opened at 390px and at desktop width, against real imported data, and reported.
- **§3.5 adds a join to a request that currently answers from one table.** Small — the
  shelves list is tens of rows, not thousands — but it is a backend change with a benchmark
  precedent (DEC-134 measured the same join on insights), and it should be measured rather
  than assumed.
- **The 390px domain strip is a five-domain problem today and a six-domain problem later.**
  A scrolling strip fixes the class of bug, not one instance of it; anything that puts the
  strip back into a `flex-wrap` row reintroduces it.
