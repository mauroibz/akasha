# The library, insights and shelves, redrawn for reading

**Status: proposal.** Written 2026-09-05 at the owner's request, after Sprint 071 closed the last
planned v1 sprint. It is written to be accepted, rejected, or cut down. Nothing here is built.

The owner's words: *"I feel like there is a lot of wasted space everywhere. We could have a bit
more fun with the layout, covers and the main number should be larger, things could be better
arranged so they are easier to parse and read. Same for the insights page, the two columns read as
bland. Finally, the shelves tab is too bland — can you propose some extra functionality to it?"*

Every number below was measured on 2026-09-05 against the owner's own running instance
(`ghcr.io/mauroibz/akasha:1.5.7` on `localhost:8000`, 19 books, 11 shelves) through Playwright at
1440×900, 2560×1400 and 390×844, or read off the geometry constants. Nothing here is an impression.

---

## 1. What the screens actually spend their space on

### 1.1 The library

| # | Finding | Measured | Where |
|---|---|---|---|
| 1 | **338px of chrome before the first cover.** Navigation bar, then a brand block that repeats the mark already in the nav, then a search row, then a filter row. On a 900px viewport that is 38% of the first screen spent saying nothing about the library. At 390×844 it is **509px — 60%**, so a phone shows one and a half books. | first card `y=338` at 1440×900; `y=509` at 390×844 | `HomePage.tsx:549-581` (header), `587-643` (search), `648-752` (controls) |
| 2 | **The card gives its cover 31% of its area and its title a 105px column.** A 281×280 card holds a fixed 128×192 cover, then `281 − 32 padding − 128 cover − 16 gap = 105px` for title, creator and year. Titles clamp to three lines at 105px (*"El problema de los Tres Cuerpos…"*), while ~90px of that same column is blank between the year and the controls. Both halves are cramped and the card as a whole is not. | card 281×280, cover 128×192, text column 105px | `library.ts:98-107`, `VirtualLibrary.tsx:289-296` |
| 3 | **The score — the number the product is built around — is 14px tall in a 36px chip, beside a 150px-wide status select that says "Read" on every card.** The control a reader touches constantly is the smaller of the two; the one they touch rarely is the widest thing on the card. | `h-9 … text-sm`, select `flex-1` | `VirtualLibrary.tsx:36-73`, `ScorePicker.tsx:88` |
| 4 | **A 2560px window shows the same four columns as a 1440px one**, with 688px of empty margin on each side — 54% of the window. `maxColumns` is 4 and the page is `max-w-7xl`. | 4 columns at both widths; first card `x=688` at 2560 | `library.ts:98-104`, `HomePage.tsx:549` |
| 5 | **The library never says how big it is.** `total` is fetched, passed into the grid, and spent entirely on `aria-setsize`. There is no visible count of what you own or of what the current filter matched. | `total` used only at `aria-setsize` | `HomePage.tsx:887`, `VirtualLibrary.tsx:278` |
| 6 | **"Table" is not a denser mode.** It is the same card unrolled: 84px rows, a 40×56 cover, the same status select and score chip. A reader with ten thousand entries has no view that trades pictures for rows. | `tableRowHeight = 84` | `library.ts:107`, `VirtualLibrary.tsx:257-258` |
| 7 | **Four filter selects are always on screen at full size**, whether or not any of them is set, and the active-filter chips Sprint 071 added then say the same thing a second time on a third row. | 44px controls row + 44px chip row | `HomePage.tsx:648-825` |

### 1.2 Insights

| # | Finding | Measured | Where |
|---|---|---|---|
| 8 | **The two cards are the same fact at two grains.** *Decade* and *Year* rank the same field; the leading card's rows (2000s 6, 2010s 5, 1960s 3) are the second card's rows added up. The page's two-column grid gave its whole width to one field. | both cards from `year` | `InsightsPage.tsx:201-226`, `insights.ts` `orderKeys` |
| 9 | **The strip above them repeats the card below them.** *Holds the most: 2000s, 6 entries* sits directly above a row reading *2000s 6*. Two of the three superlatives named `2000s`. | observed at 1440 | `SuperlativeStrip.tsx`, `InsightsPage.tsx:182-188` |
| 10 | **Time is ranked instead of drawn.** Decades and years are the one thing in this library with a natural order, and the page sorts them by count — destroying the only ordering that carries meaning. A reader cannot see *when* their library is from. | — | `InsightsRanking.tsx:159-173` |
| 11 | **One idiom, repeated.** Every fact on the page is a horizontal amber bar with a count and a chip. There is no distribution, no time, no comparison — including of the score, which is the number every other screen paints in the ramp. | — | whole page |
| 12 | **The interesting keys are in the footnote.** *Creators*, *Series*, *Publisher*, *Subjects* were demoted to a grey line reading "Nothing much to rank yet" — on a library where *Brandon Sanderson 5* and *Mistborn 5* are the two most concentrated facts it holds. | 5 keys quiet, 2 carded | `InsightsPage.tsx:228-248`, `insights.ts` `orderKeys` |
| 13 | **`max-w-5xl` in a 1440px window**, so 416px of margin, and everything below y≈995 empty. | measured at 1440×1100 | `InsightsPage.tsx:116` |

### 1.3 Shelves

| # | Finding | Measured | Where |
|---|---|---|---|
| 14 | **A 90px row to carry one number.** Eleven shelves make 990px of list inside a 768px column, and each row is a name, a count, *Rename*, *Delete*. | `max-w-3xl`, rows ~90px | `ShelvesPage.tsx:89,159` |
| 15 | **The two destructive-ish buttons are the loudest thing on every row**, repeated eleven times, while the shelf itself — what is on it — is one word and one number. | — | `ShelvesPage.tsx:251-271` |
| 16 | **A shelf has no page.** The name links into `/?shelf=slug`, which is the library with a chip on it. There is nowhere that a shelf is a thing with a shape: how far through it you are, what it is made of, how you rate it. | — | `ShelvesPage.tsx:227-245` |
| 17 | **Nothing else is possible on this screen.** Create, rename, delete. No sort, no search, no pinning, no bulk shelving, no saved filters — while the library already has a filter language that would make all of them cheap. | — | whole page |

Two smaller ones, recorded so they are not rediscovered: the shelf index is sorted by name only, which
puts an 11-entry shelf below a 1-entry one; and the running 1.5.7 instance shows the "no cover"
placeholder on every shelf row because `covers` predates it — main already fixes that (Sprint 071),
so §3.3 builds on faces that are there.

**None of these is a defect in behaviour.** Every screen works and every suite passes. What they add
up to is a product that stores pictures and shows text.

---

## 2. The rules this proposal adds

The seven rules from `ui-cohesion-proposal.md` §1 stand unchanged. Four more, each with a reason:

8. **The cover is the content.** A library of jackets, sleeves and posters that renders them at
   128px, inside a card that spends 69% of itself on 105px-wide text, is a catalogue of its own
   metadata. The cover is the largest thing on the card and the card is sized to it.
9. **A screen states its size.** Every list says how many, in a number large enough to read from
   the doorway. The count exists on every response already.
10. **Chrome is proportional to use.** A control that is set is visible; a control that is unset
    collapses. Four always-open selects above nine books is the inverse of that.
11. **A shape per fact.** A ranking is a bar list. A sequence is a timeline. A distribution is a
    histogram. Using one idiom for all three is what makes a page of true statements read as bland.

Rule 1 — one accent, one meaning — is what keeps rule 11 from becoming decoration: the timeline and
the histogram are painted in the score ramp and the amber magnitude tint that already exist, and
this proposal introduces no colour.

---

## 3. What replaces it

### 3.1 The library: a wall of covers with one command bar

**Geometry.** `gridLayout` changes in one file, and it is the whole redraw:

| | Now | Proposed |
|---|---|---|
| card | 260 min × 280 fixed | 190 min × 372 fixed |
| cover | 128 × 192 fixed (31% of the card) | card-width × 300 fixed, `object-cover` (81%) |
| columns | max 4 | max 6, and the page grows to `max-w-[1600px]` |
| at 1440 | 4 covers of 128px | 6 covers of ~205px — **2.5× the cover area** |
| at 2560 | 4 columns, 54% margin | 7 columns |

The card becomes vertical: cover on top at full card width, then title on two lines *at the full
card width* (a 205px measure instead of 105px, which is the whole of finding 2), creator under it,
year and formats as one quiet line. Fixed height is preserved exactly as DEC-023 requires — the
cover's height is pinned and its width flexes with the column, so the poster crops rather than the
row resizing.

**The score gets the corner.** A 44px chip in the ramp, `text-xl tabular-nums`, sitting on a scrim
at the foot of the cover — the picker trigger, unchanged in behaviour, at 2.4× its current area and
readable across a room. The status select moves onto the same scrim as a compact pill showing the
status word; both stay visible at all times and both keep their 44px target, so nothing moves behind
a hover.

**One command bar.** The brand block, the search row and the filter row become a single sticky
56px bar: mark and wordmark, domain strip, search, view toggle. Sort/shelf/format/status collapse
into one *Filters* button carrying a count when any is set; the chips Sprint 071 built are then the
only place a set filter is stated, instead of the second place. Measured effect: **338px of chrome
becomes ~176px**, and a 900px viewport shows a full row of 300px covers on load instead of half a
row of 192px ones.

**The big number.** Beside the domain strip, the match count at `text-3xl tabular-nums`: *342
books*, or *18 of 342* when a filter is on. It is `firstPage.total`, which is already fetched and
currently reaches only screen readers (finding 5).

**Two honest densities.** *Shelf* is the wall above. *List* becomes an actual dense mode — 56px
rows, 32×48 cover, title · creator · year · formats · status · score — roughly 16 rows per screen
against today's 9. (A third *Wall* mode, covers only at 8 columns, is in the alternatives table
rather than here.)

### 3.2 Insights: one hero, then shapes

1. **The leading key becomes a hero panel**, full width, with its top row promoted: a 96px poster,
   the label, the count, the mean chip — and the three superlatives folded *inside* it as its own
   summary, which is what stops finding 9's repetition without reopening DEC-132's rule that
   superlatives come from the leading key alone.
2. **Decade and Year become one card with a grain toggle**, since they are one fact (finding 8),
   and the freed column goes to the keys the footnote was hiding.
3. **A chronology strip**: decades in chronological order, bar height by count, tinted by mean
   score. Derived client-side from the `year` ranking already on the page — **no backend**.
4. **A score distribution band**: counts of 1…10 painted in the ramp, with the unrated tail stated.
   This is the one new number in the proposal and the one backend addition (§4).
5. **An asymmetric grid** at `xl`: 12 columns, hero at 12, then 8/4 and 4/4/4 by `orderKeys` rank,
   so a ranking with fifteen values is not the same size as one with three. This is the "fun"
   without a second accent or a new idiom.
6. **The long tail becomes a card, not a footnote**: *16 subjects appear once* as a clickable tag
   row into the filtered library (finding 12).
7. Page width matches the library's, so the two screens stop being different documents.

### 3.3 Shelves: a shelf becomes a place, and the tab gains a job

Section 5 costs the full menu of candidate features. What this proposal recommends:

1. **`/shelves/:slug` — the shelf page.** A hero of up to twelve covers, the count at the same
   `text-3xl` the library uses, a status breakdown bar (*4 read · 1 reading · 6 unsorted*), the
   mean score chip, the format mix — then the shelf's own entries in the library's grid. Rename and
   delete live here, which takes them off every row of the index (finding 15). **No backend change:**
   `GET /api/entries?shelf=slug` already returns `total` and returns `facets.status_counts`
   narrowed by shelf (`library.py:892`).
2. **The index becomes a board, not a list.** Shelf tiles at three columns: cover stack, name, count
   with its magnitude bar, and a status sliver. Eleven shelves fit one screen instead of 990px of
   rows.
3. **Sort and search the index** — by size, by recently added to, by name — which is finding 14's
   other half.
4. **Saved views ("smart shelves").** The library's filter set, named and kept: *Unrated 2024
   additions*, *Vinyl I do not own yet*. They appear on the shelves screen in their own group, open
   the library with those filters applied, and are the one genuinely new capability here — the
   filter language exists, the URL already encodes a whole view, and nothing today can keep one.
   Costs a table and a migration (§4).
5. **Pin a shelf.** A pinned shelf becomes a one-press chip in the library's command bar.
   `localStorage`, no backend, no migration.

---

## 4. What it costs

Three sprints, plus one optional. The split is the same boundary the last two redesigns used:
everything needing no new data first, everything needing some second.

| Sprint | Delivers | Backend |
|---|---|---|
| **072 — A wall of covers** | §3.1 entire: grid geometry, the vertical card, the score corner, the collapsed command bar, the visible count, the dense list, wide-screen columns. | **None.** |
| **073 — Insights with a shape** | §3.2 entire: hero panel, the Decade/Year merge, the chronology strip, the asymmetric grid, the long-tail card, and the score distribution band. | One read-only addition: per-score counts for a domain (a `GROUP BY score` over the same `_filtered_entries` the facets block already builds). |
| **074 — A shelf is a place** | §3.3 items 1–3 and 5: the shelf page, the board index, sort/search, pinning. | **None** (facets already narrow by shelf). |
| **075 — Saved views** *(optional)* | §3.3 item 4. | A `saved_views` table (name, slug, query string, created_at), CRUD routes, one migration. |

Sprint 072 is the one that must not be trimmed into 073: it is a geometry change to a virtualized
list, and DEC-023's contract, the mounted-card bound, the `library.spec.ts` layout regressions and
the 390px viewport check all have to move together or not at all.

**The acceptance criterion that holds them honest** is the one Sprint 070 used: the existing
component and e2e suites pass unchanged, except where a test asserts one of the seventeen findings
above — `library.test.ts` asserts `gridColumnCount` against `gridLayout`, so it moves with the
constants by construction, and any test that hard-codes 4 columns or a 128px cover is named in the
sprint that changes it.

---

## 5. Alternatives, and what each would cost

Costed so the shape of the work is a choice rather than this document's opinion.

### 5.1 For the library

| Strategy | What it is | Cost | Verdict |
|---|---|---|---|
| **Wall of covers (§3.1)** | Vertical card, cover at 81%, score in the corner, one command bar. | ~1 sprint, no backend | **Recommended.** Pays findings 1–7 together, and the geometry is one constant block. |
| Keep the card, shrink the chrome | Only the command bar collapse and the visible count. | ~⅓ sprint | Cheapest real gain (338px → ~176px) and it leaves the 105px title column and the 14px score exactly as they are. A fallback if 072 must shrink. |
| Grow the card instead | Keep the horizontal split, raise the card to 360px and the cover to 192×288. | ~½ sprint | Rejected: it makes the empty text column taller. Finding 2 is the split, not the size. |
| Masonry / true poster wall | Covers at natural aspect, no fixed row height. | 2+ sprints | Rejected: it ends fixed-size virtualization, which is the technical spec's contract and the Sprint 013 defect. |
| Cover-only wall as the default | No text at all under the cover; title on hover. | ~1 sprint | Rejected as a default (a phone has no hover, and a cover is not a label), but offered as an optional third density in §3.1. |

### 5.2 For insights

| Strategy | What it is | Cost | Verdict |
|---|---|---|---|
| **Hero + shapes (§3.2)** | Hero panel, grain toggle, chronology, distribution, asymmetric grid. | ~1 sprint, one small endpoint | **Recommended.** |
| Layout only | Asymmetric grid and the Decade/Year merge; no new idioms. | ~⅓ sprint | Honest partial: it fixes findings 8, 9 and 13 and leaves 10 and 11 — the page would still be one shape repeated. |
| A charting library | Recharts or similar for real plots. | ~1 sprint + a dependency + bundle | Rejected: two bars and a histogram are 40 lines of divs, and DEC-037 pinned the chunk budget deliberately. |
| Cross-domain insights | Rank across books, albums, films together. | 2+ sprints, and a decision | Out of scope by DEC-052 and DEC-077, which twice declined the cross-domain creator identity this needs. |

### 5.3 For shelves — the full menu

| # | Feature | Value | Cost | In? |
|---|---|---|---|---|
| A | Shelf page (`/shelves/:slug`) with composition and its own grid | High — a shelf becomes somewhere you go | ~⅓ sprint, no backend | **Yes (074)** |
| B | Board index with cover stacks, magnitude and status slivers | High — the tab stops being a settings list | ~¼ sprint | **Yes (074)** |
| C | Sort and search the index | Medium | small | **Yes (074)** |
| D | Pin shelves into the library command bar | Medium — one press to a shelf | small, `localStorage` | **Yes (074)** |
| E | Saved views / smart shelves | High — the one new capability | ~⅔ sprint + migration | **Yes (075, optional)** |
| F | Bulk shelving from the library (select rows → add to shelf) | High for tidying an import | ~1 sprint (selection model exists in Triage, DEC-095) | Deferred — its own sprint, not a rider |
| G | Manual order inside a shelf ("up next" queues) | Medium | ~1 sprint + `position` column + DnD | Deferred |
| H | Shelf goals ("12 of 30 read") | Low–medium | ~⅓ sprint + a field | Deferred — needs a product decision about targets |
| I | Merge two shelves / duplicate cleanup | Low here, high after a messy import | ~¼ sprint | Deferred |
| J | Auto-shelving rules (a shelf that fills itself) | High, and a different product | 2+ sprints | Out of scope — E is the honest 80% of it |

---

## 6. What this proposal deliberately does not do

- **No new colour, no second accent, no new typeface.** Everything is the DEC-026 tokens and
  `BRAND.md`'s single amber.
- **No light theme**, per product spec §7.
- **No end to fixed-size virtualization.** The card box changes size once, in `gridLayout`, and
  stays pinned (DEC-023).
- **No change to what a score means, or to the keyboard model.** `j`/`k`, the digits, `/` and the
  focus ring behave exactly as they do now; the chip they drive is simply larger.
- **No cross-domain aggregation** (DEC-052, DEC-077).
- **No new dependency**, no charting library, no component-library swap.
- **No copy rewrite** beyond the lines §3 names.

## 7. Risks

- **Sprint 072 touches the one virtualized surface in the product.** The mounted-card bound, the
  scroll-margin measurement and the score-picker containment test are all sensitive to the card box.
  Mitigation: change `gridLayout` and the card in one commit, run `library.spec.ts` before anything
  cosmetic follows, and keep the axe and 390px checks in the same sprint.
- **`object-cover` crops.** A poster whose title sits at its edge can lose a few pixels at the widest
  column. Mitigation: pin the cover height and centre the crop; the alternative — a flexible cover
  height — is the thing DEC-023 forbids.
- **Controls on a scrim over artwork is the classic contrast failure.** Mitigation: an opaque
  backing behind the chip and the status pill, not a tint, which is the same repair Sprint 071 made
  on the shelf row's buttons; axe runs with both on screen.
- **A denser list mode is more rows mounted per screen.** Mitigation: the row-height constant is
  the virtualizer's estimate, so the mounted-row bound moves with it and must be re-measured, not
  assumed.
- **Screenshots are the only real evidence for this work.** The walkthrough gate (DEC-025) is the
  actual verification: every screen at 390px and at 1440 and 2560, against the owner's real library,
  reported in the worklog.
- **Saved views (075) introduce the first stored query string in the product.** A view saved today
  must still parse after a filter is added or renamed; the mitigation is that a view stores the URL
  query it was created from and unknown keys are ignored on read, never on write.
