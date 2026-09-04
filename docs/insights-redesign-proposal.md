# Insights, redrawn — a redesign proposal for the v1.6.0 insights screen

**Status: proposal.** Written 2026-09-03 at the owner's request, after using the screen
Sprint 065 shipped. It is written to be accepted, rejected, or cut down. Nothing here is
built; nothing here changes what the product currently does.

The owner's words: *"I really like the data this feature provides, but dislike its
implementation on the frontend. At the very least I expected there to be colored numbers at
the score/ranking, but there is a lot of room to grow, from how we select the current
insights to how they are displayed."*

An interactive mockup of everything below — the shipped screen photographed beside a live,
clickable version of the proposal — accompanies this document. The mockup uses example data
with the shape `spotify-import-and-insights-viability.md` §Part 2 measured, not the owner's
library.

---

## 1. What was measured

`/insights` was photographed from the running application (dev server, stubbed API, the
ranking shaped as a real personal library ranks: one leader, two contenders, a long tail of
ones). The screenshot is not committed — `frontend/e2e/scratchpad/` is ignored — but the
spec that takes it is reproducible from this document's own description, and the findings
below are all readable from the source in `frontend/src/pages/InsightsPage.tsx`.

Eight findings, each traced to a line rather than to an impression.

| # | Finding | Where |
|---|---|---|
| 1 | **A mean score is rendered as plain body text.** `mean_score.toFixed(1)` in a `<td>`, no colour. Every other surface that shows a score — library card, triage row, detail page — paints it with the DEC-026 four-band ramp through `scoreChipClass`. The one screen whose entire subject is scores is the only one that does not. | `InsightsPage.tsx:214` |
| 2 | **Half the response is discarded.** `rated_count`, `mean_score` and `score_spread` arrive on every row in both metrics. In `count` mode none of the three is rendered. `score_spread` — a population standard deviation the query computes from `mean_sq` — is rendered in *neither* mode. It is dead payload today. | `InsightsPage.tsx:182–219`, `application/library.py:1187` |
| 3 | **Seven and one look identical.** A bare numeral in a table column carries no proportion. Nothing on the screen says the leader holds more than twice what fourth place holds. | `InsightsPage.tsx:209` |
| 4 | **The column header is the raw field name.** `<th>{key}</th>` prints `creators`, lowercase, where the domain declares the label `Creators` — and declares `Artists` for albums. The key picker beside it gets this right (`chosen.label`); the table does not. | `InsightsPage.tsx:180` |
| 5 | **The accent marks nothing.** Every row label is `text-primary`, so a twelve-row ranking is twelve identical amber links. Amber is the brand accent (`docs/brand/BRAND.md`) and on this screen it distinguishes no one row from another. | `InsightsPage.tsx:197` |
| 6 | **One question per visit.** Four controls — domain, key, metric, minimum-rated — sit above a single table. Authors, then subjects, then decades is three selections and three refetches, and the key picker is a popover, so the alternatives are not even visible while you choose. | `InsightsPage.tsx:79–147` |
| 7 | **The only interaction leaves the page.** A row click navigates to `/?type=…&key=…&value=…`. Exploring a ranking is therefore back-button ping-pong, and the library gives no indication of where the filter came from or how to drop it. | `InsightsPage.tsx:198–204` |
| 8 | **No item is ever shown.** The library holds book jackets, album art and film posters, and its aggregate screen is text in a table. | — |

Two smaller ones, recorded so they are not rediscovered: the `min_rated` control is a number
input with a spinner, which is a developer's control on a reader's screen; and the suppressed-
values and null-year notices are grey paragraphs under the table, which is the right
information in the least likely place to be read.

**None of these is a defect in the feature.** The query, the declaration model, the
suppression list, the normalization and the `key`/`value` filter are all right, and Sprint
065's own outcome is honest about what it could not verify. The gap is entirely in the
presentation layer, which is why this proposal needs no change to the domain contract, the
data model, or the ranking query.

---

## 2. What replaces it

Eight changes. The first six need **no backend work at all** — the endpoint already returns
everything they draw.

### 2.1 The ramp, where it belongs

Mean score becomes the same coloured chip the rest of the application already uses:
`scoreChipClass` from `frontend/src/lib/score.ts`, unchanged, with `scoreChipShape` for
geometry. Red 1–3, amber 4–6, lime 7–8, emerald 9–10.

This is the owner's stated minimum and it costs an import. It is also the correct call
rather than merely the requested one: the ramp exists precisely so that "the colour means
the same thing wherever the eye lands", and an insights screen that opts out of it teaches
the eye that the colour is decoration.

The chip always prints its number, so nothing on the screen is encoded by hue alone.

### 2.2 The row is the bar

Each ranking row is filled to its share of the leader's count — an amber wash behind the
label, brightening toward the value end, 4px rounded data-end. Proportion becomes something
seen instead of something computed, and the accent finally encodes a quantity.

This is the first honest use of amber on the screen. It replaces, rather than adds to, the
twelve amber links of finding 5: labels return to `foreground` ink.

### 2.3 Both metrics at once

Count and score stop being modes. **The bar carries how many; the chip carries how good.**
The toggle only chooses the sort order.

This doubles the information per screen for zero new data, and it produces the reading the
current table cannot: a short bar with an emerald chip says *brilliant, and you own two of
them* at a glance. When sorted by score, rows below `min_rated` are not dropped silently —
they fall below a thin `n not rated enough to place` divider, which is what the
`min_rated` control actually means, drawn instead of configured.

### 2.4 Every question on one screen

The key picker becomes a responsive grid of cards, one per key, each pre-ranked to six rows
with a *Show n more* under it. The page answers on arrival rather than asking for a query
first.

This is the biggest structural change and the one worth arguing about. The argument for it:
a personal library's rankings are short — the viability measurement found 14 artists with
three or more albums out of 88 — so one ranking is half a screen of content and four fit
comfortably where one sits today. The argument against: `n` requests instead of one. The
answer is a batched `keys=` parameter, costed in §4.

### 2.5 Cards ordered by what they have to say

This is the owner's *"how we select the current insights"*, and today the answer is
declaration order with the first key auto-selected — which means every domain opens on
whatever its `__init__.py` happens to list first.

Proposed rule, in one sentence:

> **A key earns a card when at least three of its values hold two or more entries. Cards are
> ordered by how far the leader stands above the middle of its own ranking.**

Both halves are computable from the payload already loaded, in about a dozen lines, and both
are explainable to the reader in a sentence. A key whose every value appears once has a lead
of 1 and says nothing; a key with two values is a fact, not a ranking.

Keys that fail the test do not vanish — they collapse into one honest line at the foot of the
page: *Nothing much to rank yet — Language: Spanish 31, English 16.* That is the whole truth
about that key, stated in less space than a card, and it is more useful than a card with two
rows in it.

### 2.6 Open a row without leaving

Clicking a row expands it in place: up to four members with cover, title, year and score
chip, then *Open all 7 in the library →* for when you actually want to act on them.

This reuses the `key`/`value` filter Sprint 065 already built for the link — the same request
the row's `href` makes today, rendered inline instead of navigated to. Exploring stops being
a one-way door, and the library link stays for the case it was built for.

Paired with it: when the library page arrives carrying `key`/`value`, it shows a breadcrumb
chip — *Insights · Authors · Julio Cortázar ✕* — so the filter says where it came from and
can be dropped. Today those params apply invisibly.

### 2.7 Three answers above the fold

A strip of three superlatives drawn from the leading key: **most collected**, **highest
rated**, and **steadiest** — the last from `score_spread`, which is computed, served and
drawn nowhere.

Drawing them from the leading key rather than from all keys at once is deliberate and was
found by building it: pooled across keys, "most collected" came out as the subject tag
`Fiction`, which is true and useless. The superlatives should name things you collect.

### 2.8 Covers

A row is an author; an author has jackets. This is the one change that needs real backend
work and the one that most changes how the screen feels — it is the difference between a
database and a shelf.

It needs `InsightRowResponse.covers: list[str]`, a lateral top-3 per row. Doing it from the
client instead is an N+1 over visible rows and is not acceptable. This is the reason for a
second sprint rather than a longer first one.

---

## 3. Where it goes

The owner asked the question directly. Three answers were available.

| Option | What it means | For | Against |
|---|---|---|---|
| **Keep `/insights`** *(recommended)* | Stays a destination in the main navigation, redrawn per §2. The library gains the breadcrumb chip of §2.6. | Discoverable; one page owns one job; fixes the dead end the current link creates. | Insights still does not know what you were just looking at in the library. |
| A library view mode | A third option beside Grid and Table. Rankings inherit the library's domain tab, search box, shelf and format filters. | `LibraryService.rank()` **already accepts** `statuses`, `shelves`, `q` and `formats` — only `GET /api/insights` withholds them. "Rank the things on my Fiction shelf" is nearly free at the service layer. | The library page already carries search, filters, sort, virtualization, web results and the add dialog. Insights would also stop being a named feature in the navigation, weeks after being added to it. |
| Panels beside the library grid | A collapsible rail of small rankings. | Zero navigation. | No room. The grid is the primary surface at every viewport and the rail dies first on mobile. |

**Recommendation: the first, and then borrow the best of the second.** The two are not
exclusive, and the order matters: forwarding `rank()`'s existing filter parameters through the
endpoint is a small change that gives the Insights page a *within your current library
filters* switch — most of option two's value at none of its cost, and without giving the
library page a fourth responsibility. That forwarding is listed in Sprint 067 below.

---

## 4. What it costs

Everything above is one sprint's worth of design and roughly two of work. The natural split
is at the backend boundary, and it is a good one: **the first sprint ships the entire felt
improvement against the endpoint exactly as it stands today.**

| Sprint | Delivers | Backend |
|---|---|---|
| **066 — Insights you can read** | §2.1–2.6, plus the domain's declared label on every card (finding 4), the responsive layout, the ramp legend, suppression and null-year notices as inline chips, `min_rated` demoted out of the control row, and the library breadcrumb. | **None required.** Optionally the batched `keys=` parameter, which turns six requests into one. |
| **067 — Insights with faces** | §2.7–2.8: covers per row, library totals for the superlative strip, and the filter passthrough of §3. | `InsightRowResponse.covers`, one new aggregate, four parameters forwarded to a method that already takes them. |

The split follows the standing rule that a sprint's scope fits a sprint: the design is not
trimmed to fit one, it is delivered across two.

Draft sprint files exist as [`sprints/066-insights-you-can-read.md`](sprints/066-insights-you-can-read.md)
and [`sprints/067-insights-with-faces.md`](sprints/067-insights-with-faces.md), both `planned`.
Neither is scheduled: `docs/agent/state.json` still reads `complete`, and moving
`FINAL_SPRINT` in `scripts/validate_project.py` is the owner's decision to make when these are
accepted.

---

## 5. What this proposal deliberately does not do

- **No new colour and no new typeface.** Everything drawn uses the DEC-026 tokens and Inter.
  `BRAND.md` says the mark "needs no second brand colour, and must not acquire one"; neither
  does this screen. The score ramp and the amber accent do all the encoding.
- **No cross-domain ranking.** Sprint 065's non-scope stands, for the same reason: it needs
  the creator identity DEC-052 and DEC-077 twice declined to create.
- **No entity pages.** A row still expands to entries and links to the filtered library. The
  moment a key gets a page of its own it is a subdomain.
- **No time series and no "your year in review."** Also Sprint 065's non-scope. Note that the
  *fun* the owner is asking for is delivered here without it — superlatives and spread are
  statements about a library, not about a year.
- **No new metric.** Count and mean score remain the only two things ranked. Everything added
  above is a different rendering of data the endpoint already returns.
- **No grouping by entry fields** — status, shelf, format, date finished. Still a separate
  sprint, still interesting, still out of scope here.

## 6. Risks

- **§2.4 changes the request count.** Four to six rankings per page load instead of one. At the
  measured ~290 ms p95 for a 5,000-entry ranking (DEC-131), six parallel requests on a personal
  library are fine, but this is an assumption and the batched `keys=` parameter is the honest
  fix. Sprint 066 should measure before deciding it does not need it.
- **§2.5 is a heuristic, and heuristics are argued with.** It is deliberately one sentence and
  entirely client-side, so changing one's mind is a small diff and a test — the same reasoning
  that made `groupable` a declaration rather than a derivation.
- **A very small library still produces very short cards.** No design fixes 16 entries. What
  this design does is stop pretending otherwise: a key with nothing to say says so in one line
  instead of rendering a table of ones.
- **The walkthrough Sprint 065 still owes is still owed.** Running these rankings against the
  owner's real library — and reporting whether score density makes the score metric worth
  having — remains the most valuable output available here, and it needs the owner's own
  instance. Neither sprint below substitutes for it.
