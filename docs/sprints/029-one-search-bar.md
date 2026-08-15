# Sprint 029 — One search bar

**Status:** ready
**Depends on:** 027, 028
**Roadmap revision:** 12

## Objective

**Adding and searching stop being two screens.** One bar at the top of `/` searches your library as
you type and reaches a provider only when your library has nothing and the query has settled — or
when you press **Add**. The domain selector to its left picks the rows you see *and* the providers
you would search, so there is never a moment where the application has to ask which you meant. The
sprint succeeds when adding a book never requires leaving `/`, and when nothing the separate add
screen could do has been lost.

Accepted as `docs/unified-search-proposal.md` and **DEC-065**, with the owner's two amendments:
"All" is removed as a filter, and the confirm step is a dialog *provided no functionality is lost*.

## Required context

1. `AGENTS.md`, `docs/agent/WORKFLOW.md`
2. `docs/unified-search-proposal.md` in full — the measurement is the design input, not background
3. `docs/decisions.md`: **DEC-065** (this sprint's contract), **DEC-062** (the remembered domain and
   the facet asymmetry this amends), **DEC-064** (the add flow as it stands, including the preview
   endpoint and its quota rule), **DEC-045** (the quota, and why search records but is never
   blocked), DEC-044 (the tier breach this sprint must not repeat), DEC-052 seam 4 (a search reaches
   only its domain's providers), DEC-023 (the pinned card box), DEC-038 (feed semantics)
4. Sprint 027's file and Outcome, both passes
5. `frontend/src/pages/AddPage.tsx` and `frontend/src/pages/HomePage.tsx` in full, and
   `frontend/src/api/add.ts`
6. `docs/specs/product-spec.md` section 7; `docs/specs/technical-spec.md` sections 7.1 and 8
7. `docs/agent/HANDOFF.md` and the last worklog entry

## Current implementation baseline

Observed 2026-08-15 at Sprint 027's close. **Re-derive at activation.**

- `/` has a search input that debounces 250 ms into the URL's `q` and reaches
  `GET /api/entries?q=`. SQL over stored normalized projections; no provider is ever consulted while
  rendering a library page, and that invariant survives this sprint.
- `/add` has its own search input debounced 300 ms into `GET /api/search?q=&type=`, five seconds per
  provider, recorded against `provider_daily_limits` (default `{"googlebooks": 900}`).
- **`searchCandidates` auto-detects a URL or a bare ISBN** (`/^(https?:\/\/|[\dXx -]{10,17}$)/`) and
  routes to `GET /api/search/resolve` instead. This is easy to lose in a rewrite and must not be.
- The domain selector exists **twice**: a radio group on `/` (All + one per domain, remembered in
  `localStorage` under `akasha.library.domain`) and a second radio group on `/add` that also seeds
  the default status. This sprint makes them one control.
- The confirm step on `/add` is Sprint 027's second pass: `CandidateFacts`, *Load full details*,
  status, score, `ShelfPicker`, `FormatPicker`, the domain's passage fields, and notes.
- `VirtualLibrary` measures the window with a `scrollMargin` taken from the list's document offset,
  re-measured by a `ResizeObserver` on `document.body`.

## Deliverables

1. **The unified bar.** Domain selector, search input and **Add**, one row, at the top of `/`. The
   selector is the single control it already is on `/`, now also naming the providers a search would
   reach. The input keeps the library's current debounce and URL behaviour exactly.
2. **"All" is removed** (DEC-065). The tab strip always names exactly one domain. The remembered
   domain rule is unchanged; the fallback when nothing is remembered is the **first declared
   domain**. A stored `""` from Sprint 027 must resolve to that fallback rather than to a filter
   nobody can express. The grouped-chip-rows branch goes away, since there is now always one row.
3. **Web results on `/`, under the settled-and-empty rule.** A provider search fires when the query
   has been still for ~800 ms, is ≥3 characters, and the library returned **zero** rows — never
   twice for the same string — or immediately when **Add** is pressed. Results render in their own
   labelled region below the library, never inside the feed. The URL/ISBN resolve path survives.
4. **The add dialog.** Selecting a web result opens Sprint 027's confirm form in a dialog over `/`.
   **Nothing in the inventory below may be lost** — that is the owner's condition on this deliverable
   and it is AC5.
5. **Reconciling what is left.** `/add` keeps manual entry and stays a working deep link; the
   header's *Add to library* button and the `a` shortcut focus the bar instead of navigating; `j`/`k`
   and the digit shortcuts get a stated rule while web results are on screen.
6. **The chrome stops saying "book"** (DEC-071, added after the Sprint 028 assessment). The rendering
   layer is already domain-neutral; the copy is not, and this sprint rebuilds the screens where most
   of it lives, so doing it anywhere else would mean doing it twice.

   **Eighteen user-visible strings, across eight files**, measured 2026-08-15:

   | Where | What it says |
   |---|---|
   | `pages/AddPage.tsx` | *Book added*, *Book could not be added*, *You can still enter this book manually*, `itemType === "book"` branches for the search label and the placeholder |
   | `pages/ImportPage.tsx` | *Import books*, and `book`/`books` in three result counts |
   | `pages/ShelvesPage.tsx` | *Your books are retained*, `N books` per shelf |
   | `pages/TriagePage.tsx` | *Import books to start triaging*, *Filter by title or author* |
   | `features/library/VirtualLibrary.tsx` | *Loading more books* |
   | `features/detail/CoverDialog.tsx` | *This book has no provider reference or ISBN…*, *…no other editions with covers for this book* |
   | `features/detail/schemas.ts` | *A book needs a title* |
   | `components/ProviderHealthNotice.tsx` | *You can still add a book manually* |
   | `api/add.ts` | *Book could not be added* |

   **The rule:** copy that names one domain must come from that domain's `label`, or be neutral.
   `Book added` becomes the domain's label; `N books` on a shelf becomes `N items` — a shelf spans
   domains and always did. **The three `itemType === "book"` branches in `AddPage` are deleted, not
   moved**: the search label and the placeholder are per-domain copy the registry can carry, and if
   this sprint needs a new `Domain` field for a placeholder, that is a legitimate registry addition
   with a conformance check, not a branch.

   **Deliberately out of scope:** the route `/books/:entryId`. Renaming it touches every `navigate`
   call and seven e2e specs to fix something cosmetic (DEC-067 row 8, reaffirmed). And
   `ImportPage.tsx` beyond its copy — the import screen is book-shaped structurally, and that is
   Sprint 031's problem, not this sprint's.

### The functionality inventory (deliverable 4's contract)

Every one of these exists on `/add` today and must exist in the dialog flow:

| # | Behaviour |
|---|---|
| 1 | Provider search scoped to the chosen domain's providers only (DEC-052 seam 4) |
| 2 | A pasted URL or bare ISBN resolves via `GET /api/search/resolve` instead of a keyword search |
| 3 | `ProviderHealthNotice` — the degraded-provider warning |
| 4 | Pending, error and partial-results (`X-Provider-Warning`) states |
| 5 | The results grid, with its staggered entry and per-result cover/title/credit/year |
| 6 | *None of these — enter manually*, reaching the validated manual form |
| 7 | The confirm form entire: `CandidateFacts`, *Load full details* and its error, status, score, `ShelfPicker`, `FormatPicker`, the domain's passage fields, notes |
| 8 | Near-match confirmation: *Add separate edition* and *Open existing entry* |
| 9 | Focus management: the bar on open, the status control on selecting a result, the near-match button on a 409, the title field on choosing manual entry |
| 10 | `already_exists` returning 200 rather than 201, and not double-adding |
| 11 | On success the new entry is highlighted in the library — which on `/` is now a dialog close rather than a navigation |

## Acceptance criteria

1. Typing in the bar filters the library and reaches **no provider**, at any query length, for as
   long as the library has a match.
2. A query that returns nothing and then goes quiet reaches a provider **exactly once**; the same
   query typed again reaches none. Proven by counting requests, not by inspection.
3. Pressing **Add** searches immediately regardless of local hits, and a pasted URL or ISBN resolves.
4. The domain selector changes both the rows shown and the providers searched, in one action, and
   there is no way to be in a state where the application must ask which domain a search means.
5. **Every behaviour in the inventory above works from `/`**, each demonstrated individually.
6. `/add` still works as a deep link and still offers manual entry.
7. The library still scrolls with the page and still holds DEC-023's mounted-DOM bounds at 10,000
   entries **with a web-results block above it**, and the feed's accessibility semantics still hold
   with two result regions on one page.
8. Nothing renders a format as a shelf; imports, triage, undo, bulk edit, backup, formats and
   statuses are unchanged.
9. **No screen names a domain in copy that the registry could supply.** Grepping the frontend for
   `book` outside `book_tracker`, imports and comments returns only the `/books/:entryId` route,
   which is explicitly out of scope. Demonstrated on an album: adding one says *Album added*, the
   shelf count reads *N items*, and the cover chooser is absent as Sprint 028 left it.

## Required tests (TDD)

- A library hit reaches no provider: a request counter over a full typed query with matches.
- Settled-and-empty fires once, and a repeat of the same string fires none.
- **Add** fires with local hits present; a URL and a bare ISBN both take the resolve route.
- Removing "All": a stored `""` preference resolves to the first declared domain, and no control
  offers a way back to an unfiltered library.
- One test per inventory row, or an existing `AddPage` test moved to the new flow rather than
  deleted — **a test deleted here is functionality lost, which is the thing the owner asked to
  prevent.**
- The 10,000-entry scale test and the feed-semantics accessibility test, re-run with a web-results
  block rendered above the library.
- **A test that fails on domain-named copy**: the add flow asserted against an *album*, expecting the
  domain's label rather than "Book", so the copy cannot regress to one domain's vocabulary silently.

## Verification

```bash
python scripts/validate_project.py
make format && make check && make test
cd frontend && npm run test:e2e
cd .. && make build && make smoke-container
git diff --check
```

Plus the walkthrough gate against the real dev library **and live providers**: type a title you own
and watch the network stay local; type one you do not and watch exactly one search go out; press
**Add** on a query that had hits; paste an ISBN; add a record and a book from `/` with shelves,
notes and format set in the dialog; and confirm the near-match path by adding something already
owned.

## Explicit non-scope

- **Manual entry moving inline.** It stays on `/add`; moving it is what pushes this past one sprint.
- **Redesigning the confirm form.** It was built and walked through in Sprint 027's second pass and
  is reused as-is.
- **Searching more than one domain at once.** Removing "All" is precisely the decision not to.
- **A provider response cache.** Tempting once search is this visible, and a real question — but it
  is a storage design with its own invalidation story, not a slice of this.
- The domain contract and its conformance suite: that is Sprint 028, which runs after this.

## Commit checkpoints

1. `feat: name a domain, always` (removing "All", including the stored-preference fallback)
2. `feat: search your library and the web from one bar`
3. `feat: add what you found without leaving the library`
4. `refactor: leave /add to manual entry`
5. final `docs(sprint-029): close sprint and hand off`

## Risks and decisions to surface

- **The quota is the thing to get wrong.** DEC-044 measured a tier breach once already. The
  settled-and-empty rule must be tested by counting requests, and the count is the acceptance
  criterion, not the feel.
- **Deliverable 3 lands a variable-height block above a window-virtualized list**, which moves the
  `scrollMargin` every list measures itself against. This is the exact class of bug Sprint 013 was
  called in to repair; it wants its own verification pass rather than being folded into a feature
  commit.
- **Two result sets on one page is an accessibility hazard.** The library is a `role="feed"` with
  server-side `aria-posinset`/`aria-setsize` (DEC-038); web results must be a plainly separate
  region and must not be announced as part of it.
- **The inventory is the deliverable, not a checklist to skim.** The owner's condition was explicit.
  If a row cannot be carried over, stop and say so rather than shipping without it.
- `j`/`k` and the digit shortcuts currently address library rows only. Decide and record what they
  do while web results are on screen rather than leaving it to emerge.

## Outcome

_Not started. On completion record delivered behavior, commands and actual results, commit IDs,
deviations/decisions, and impact on every future sprint._
