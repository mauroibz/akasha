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
7. **Only if deliverable 6 adds a `Domain` field:** `docs/specs/technical-spec.md` **section 6.6**
   (the binding domain contract), `docs/guides/adding-a-domain.md`, and
   `backend/tests/test_domain_conformance.py` — whose
   `test_the_suite_covers_every_field_of_the_contract` **fails by design** when a field is added to
   `Domain` without a check. That failure is the contract working, not a defect to route around.
8. `docs/agent/HANDOFF.md` and the last worklog entry

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
   domain**. An **absent or empty** stored preference must resolve to that fallback rather than to a
   filter nobody can express — note that `readDomainPreference` in
   `frontend/src/features/library/library.ts` returns `""` both for a value stored by Sprint 027 and
   for a first-ever visit with nothing stored, so one branch must cover both. The grouped-chip-rows
   branch goes away, since there is now always one row.
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

   **Twenty-four user-visible strings, across eleven files.** First stated 2026-08-15 as eighteen
   across eight; **re-measured 2026-08-16 and corrected** — the original count was assembled
   separately from the rest of this file, missed two whole screens, and did not match its own table,
   which already listed nine files and nineteen strings. Line numbers are as of the re-measurement
   and will drift; the strings are the contract, not the numbers.

   | Where | What it says |
   |---|---|
   | `pages/AddPage.tsx` | *Book added*, *Book could not be added*, *You can still enter this book manually*, `itemType === "book"` branches for the search label and the placeholder |
   | `pages/HomePage.tsx` | **:626** *Add a book or visit the inbox to get started.* — the empty state of the very screen this sprint rebuilds |
   | `pages/NotFoundPage.tsx` | **:23** *Add a book* — the link label on the 404 |
   | `pages/ImportPage.tsx` | *Import books*, `book`/`books` in three result counts, and **:295** *Your library hides unsorted books until you sort them* |
   | `pages/ShelvesPage.tsx` | *Your books are retained*, `N books` per shelf, **:99** *Deleting a shelf removes the tag from your books but never deletes the books themselves*, **:241** *This shelf will be removed from all your books. The books themselves are retained…* |
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

   **Where the two arms differ in substance, the rule above does not decide it, and the sprint must
   record which behaviour survives rather than picking one silently.** Two of the three branches are
   like this, and neither is a noun swap:

   - `AddPage.tsx:112` — books get *"You can still enter this book manually."*, albums get *"Try
     again in a moment."* One arm offers a recovery path the other withholds. **Decide whether every
     domain is offered manual entry on a failed provider search**, and say so in the Outcome. Manual
     entry today is bound to `DEFAULT_DOMAIN` (DEC-067 row 6), so offering it for every domain is a
     promise the add path must actually keep — if it cannot, the neutral copy must not imply it.
   - `AddPage.tsx:299` — books get *"Title, author, ISBN, or URL"*, albums get *"Album or artist"*.
     The book arm advertises the **resolve** path, and resolve is domain-neutral: a MusicBrainz URL
     resolves exactly as an Open Library one does. So the placeholder for every domain names that
     path. This is the branch most likely to want the `Domain` field.

   **On that field, decide at the boundary rather than mid-flight.** A per-domain placeholder is a
   declarative addition to `Domain` and costs a conformance check
   (`test_the_suite_covers_every_field_of_the_contract` fails until it has one) plus the mirrored
   client union. It is in scope — but note that the roadmap's line about this sprint leaving the
   backend contract untouched was written before deliverable 6 existed and has been narrowed to
   match. The alternative, if the field is judged not worth it, is one neutral placeholder for every
   domain naming title, creator and URL. **Either is acceptable; a surviving `itemType === "book"`
   branch is not.**

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
| 12 | **The `AbortController`** (`AddPage.tsx:95`, `:124`): each keystroke aborts the in-flight provider search. A provider search takes about five seconds, so without it a few keystrokes leave several multi-second requests running against a rate-limited free API for results that are thrown away. This is quota protection, not tidiness — see the first risk below |
| 13 | **The stale-response guard** (`searchRequestId`): a response for a superseded query is discarded, so a slow earlier search cannot overwrite a newer result set |

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
9. **No screen names a domain in copy that the registry could supply.** Verified by running this
   exact command, not by inspection:

   ```bash
   grep -rniE 'book' frontend/src --include='*.ts' --include='*.tsx' \
     | grep -v '\.test\.' \
     | grep -vE '^[^:]+:[0-9]+: *(//|\*|/\*)' \
     | grep -vE '/books/|book_tracker|manualBookSchema|ManualBookValues|_book_id|Bookmark'
   ```

   The exclusions are deliberate and each is out of scope for a stated reason: test files assert on
   copy and follow it; the `/books/:entryId` route stays (DEC-067 row 8); `manualBookSchema`,
   `ManualBookValues`, `goodreads_book_id` / `calibre_book_id` and lucide's `Bookmark` icon are
   identifiers, and internal names are permanent by project invariant.

   **The command returns 27 lines today** (measured 2026-08-16) — that is the pre-implementation
   baseline, and it is the twenty-four strings above plus three lines that are not copy: two JSX
   comment continuations in `HomePage.tsx` that survive the comment filter because they wrap
   inside a `{/* … */}` block, and `AddPage.tsx:49`'s `useState("book")`, a domain id rather than
   a word anyone reads. **On completion, every line the command still returns must be a comment or
   a non-rendered identifier, and zero may be a string that reaches the screen.** The residue is
   small enough to read, so read it — do not assert on the count. Record the actual output in the
   Outcome.

   Demonstrated on an album besides: adding one says *Album added*, the shelf count reads *N items*,
   and the cover chooser is absent as Sprint 028 left it.

## Required tests (TDD)

- A library hit reaches no provider: a request counter over a full typed query with matches.
- Settled-and-empty fires once, and a repeat of the same string fires none.
- **Add** fires with local hits present; a URL and a bare ISBN both take the resolve route.
- Removing "All": **both** an absent preference (first-ever visit) and a stored `""` resolve to the
  first declared domain, and no control offers a way back to an unfiltered library.
- **Inventory row 12**: a superseded provider search is aborted rather than left running — asserted
  on the `AbortSignal`, since this is the quota protection and DEC-044 is what happens without it.
- **Inventory row 13**: a late response for an older query does not replace a newer result set.
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
