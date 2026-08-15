# One search bar — proposal

**Status:** proposed, awaiting the owner's decision
**Written:** 2026-08-15, against Sprint 027's close (028 `ready`, not started)
**Answers:** the owner's feedback of 2026-08-15 — *"the main page should have both functionalities
open to the user: adding and searching for your data… 1 large searchbar up top for both."*

---

## 1. The ask, made precise

The owner's flow, restated so each clause can be built and tested:

1. One search bar at the top of `/`, with the domain selector to its left and an **Add** button to
   its right.
2. The domain selector chooses **both** what the library shows *and* what a web search would search.
3. Typing searches **your library** first. A local hit means no provider is consulted.
4. **No local hit** — or the reader presses **Add** — performs a web search, whose results appear
   below, ready to add through the flow the separate add screen already has.

```text
┌──────────────────────────────────────────────────────────────────────┐
│ [ All │ Books │ Records ]  ( search your library…            ) [Add] │
└──────────────────────────────────────────────────────────────────────┘
   ↑ picks the library filter          ↑ local first        ↑ forces a
     and the providers to search         (SQL, free)          web search

   IN YOUR LIBRARY (3)      ← the virtualized grid, unchanged
   …

   FROM THE WEB (12)        ← only after a miss or a press of Add
   …
```

## 2. What was measured first

The two things this bar merges are not the same kind of thing, and the difference is the whole
design problem.

| | Library search | Provider search |
|---|---|---|
| Where | `GET /api/entries?q=` — SQL over stored normalized projections | `GET /api/search?q=&type=` — Open Library / Google Books / MusicBrainz |
| Cost | Free. No provider is ever consulted while rendering a library page (a standing invariant) | One request **per provider**, 5 s timeout each, recorded against the daily quota |
| Speed | Milliseconds | Up to 5 s; MusicBrainz additionally paces itself at 1.1 s |
| Budget | None | `provider_daily_limits` defaults to `{"googlebooks": 900}` against a real ceiling of 1,000 (DEC-045) |
| Debounce today | 250 ms, then written to the URL | 300 ms, on a screen you reached deliberately |

**The risk this creates is concrete.** Adding a book means typing a title that is, by definition,
*not* in the library — so every keystroke is a local miss. Under a literal reading of rule 4,
typing `Kind of Blue` fires **twelve** provider searches. At 300 ms debounce and 5 s timeout, most
of them are still in flight when the next one starts, and a day of adding a shelf's worth of books
would breach the Google free tier — the same failure DEC-044 measured and rejected for enrichment.

Rule 3's phrasing hides a second question: **what counts as "a local hit"?** Searching `dune` when
you own *Dune* returns one row — and you may well be trying to add *Dune Messiah*. A strict "zero
rows" rule is the only one that never guesses, and it is the one costed below.

## 3. The decisions, costed

### 3.1 When does a web search actually fire?

| | Shape | For | Against | Verdict |
|---|---|---|---|---|
| **A** | Literal: fire whenever the local result set is empty | Exactly what was asked; nothing to press | Fires per keystroke while typing any new title — the common case. Breaches the free tier on a session of adding | Rejected on measurement |
| **B** | The **Add** button is the only trigger | Zero surprise, zero waste, trivially testable | The reader has to press a thing after typing a thing, which is the friction the ask is about | Rejected as the sole rule |
| **C** | **Settled-and-empty**: fire once the query has been still for ~800 ms, is ≥3 characters, and returned **zero** library rows — and never twice for the same string. **Add** forces it at any time | Behaves as the owner described for a query somebody actually finished typing; a full title costs one or two searches, not twelve. The button stays as the override for "I know it's not here" | One more piece of state (the last query searched), and a deliberate pause before results appear | **Recommended** |

Under **C**, `Kind of Blue` typed at ordinary speed fires once. A query already searched is served
from cache when the reader edits and retypes it.

### 3.2 What does the web search do when the tab says "All"?

A provider search must name a domain: `?type=` is what selects the providers, and it is the reason
adding an album spends no book-provider request (DEC-052 seam 4).

| | Shape | For | Against | Verdict |
|---|---|---|---|---|
| **A** | Search every domain's providers and group the results | "All" keeps meaning all | Doubles the request cost of every search, and returns exactly the mixed list the owner's first piece of feedback was about | Rejected |
| **B** | Drop "All" — the tab always names one domain | Every rule gets simpler, and one domain at a time is what the owner said they want | Loses a view shipped four hours ago, and "what did I add this week" spans domains | Rejected as too destructive |
| **C** | Under "All", the library still shows everything; the auto-search is suppressed and **Add** asks which domain — one click, exactly once | Keeps both meanings honest, spends nothing by accident | The reader meets a small question they did not ask for | **Recommended** |

### 3.3 Where does the confirm step live?

Sprint 027 grew the confirm step considerably: cover, the facts panel, *Load full details*, status,
score, shelves, format, notes and the domain's date fields. It is a form, not a button.

| | Shape | For | Against | Verdict |
|---|---|---|---|---|
| **A** | Inline, replacing the results on `/` | No new surface; matches how `/add` behaves today | Pushes the library out of sight and makes `/` a page with two personalities | Rejected |
| **B** | A dialog over `/` | The task is focused and has a clear end; Escape is already the way out of every other dialog here; the library stays behind it | One more dialog, and the near-match confirmation is a flow *inside* it | **Recommended** |
| **C** | Navigate to `/add?source=…&source_id=…` prefilled | Reuses the whole screen untouched; deep links work | The navigation is the thing the ask is trying to remove | Rejected — but see §5 |

### 3.4 What happens to `/add`?

**It stays**, and this is not a compromise. Manual entry is a full validated form for a book that no
provider has, and it is reached deliberately. The route is lazy-loaded, so keeping it costs nothing
in the bundle. What changes is that it stops being the *only* way to add, and the header's *Add to
library* button and the `a` shortcut point at the search bar instead.

## 4. What this touches, and the risks

- **The window virtualizer.** Its `scrollMargin` is the library's offset down the document. Inserting
  a variable-height results block above it moves that offset on every search. The `ResizeObserver` on
  `document.body` added in Sprint 027 should absorb it, **but this is the exact class of bug Sprint
  013 was called in to repair** and it needs its own test rather than an assumption.
- **Two result sets on one page.** The library is `role="feed"` with `aria-posinset`/`aria-setsize`
  from the server total (DEC-038). Web results must be a separate, plainly-labelled region and must
  not be mistaken for feed items by a screen reader.
- **`j`/`k` and the digit shortcuts** currently address library rows. They need a stated rule for
  what happens when web results are on screen.
- **The standing invariant** that no provider is consulted while rendering a cached library page
  still holds under proposal **C**: a provider is reached only after a settled miss or a press.
- **Product spec section 7** describes `/add` as its own screen and would be rewritten.

## 5. Scope verdict

**This is one sprint, and only just.** Five slices:

1. The unified bar: domain selector, search input and **Add**, with the library filter behaviour unchanged.
2. Web results on `/` under the settled-and-empty rule, with the quota safety and the "All" question.
3. The add dialog, reusing Sprint 027's confirm form rather than redesigning it.
4. Reconciling `/add`, the header button, and the keyboard.
5. Re-running the virtualization and accessibility gates against the new page structure.

**It stays one sprint only if two things are held out**, and both are genuinely separable:

- **Manual entry stays on `/add`.** Moving it inline as well is a second sprint's worth of form work.
- **The confirm step is reused, not redesigned.** It was just built and walked through.

**Sequencing against Sprint 028.** 028's Phase A writes down what a domain declares and what every
screen renders from it. This proposal changes what the main screen renders and makes the domain
selector drive provider choice as well as filtering. Writing the contract first means writing it
against a shell that is about to be rebuilt. **Recommendation: this sprint runs first, and 028
describes the settled reality** — which is also the order that keeps 028's conformance suite honest.

## 6. What the owner has to decide

1. The firing rule — **C** (settled-and-empty plus the button) is recommended over the literal reading.
2. What "All" does when you press Add — **C** (ask once) is recommended.
3. Confirm as a dialog over `/` — **B** is recommended.
4. Whether this runs before Sprint 028. Recommended: **yes**.
