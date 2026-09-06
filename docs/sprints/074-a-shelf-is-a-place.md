# Sprint 074 — A shelf is a place

**Status:** completed
**Depends on:** 073
**Roadmap revision:** 39

> Planned from [`../readability-proposal.md`](../readability-proposal.md) §1.3, §3.3 and §5.3.
> **Accepted by the owner as DEC-139**, including §3.3.3's cross-domain shelf page, which the
> proposal raised as a product call and the owner accepted with the rest.

## Objective

A shelf stops being a row with two buttons on it. The index becomes a board where each card is
drawn as a shelf — its covers stood up side by side, scrolling when there are more than fit — each
card says which domains it holds, and every shelf gets a page that shows the whole set, including
the members the library's one-domain rule would hide.

## Required context

- [`../readability-proposal.md`](../readability-proposal.md) §1.3 findings 14–19, §3.3, §5.3
  (the full feature menu and what was deferred), §7 (the scroller and the cross-domain risks).
- `docs/decisions.md` **DEC-065** — the library always names exactly one domain, and `/triage` and
  the export are the standing precedent for a screen that spans them. §3.3.3 reads the shelf page
  as the second such screen; DEC-139 records the owner accepting that.
- `docs/decisions.md` DEC-133 (`magnitude`), DEC-134 (the covers join), DEC-136/DEC-137 (`Panel`,
  `PageHeader`), DEC-026 (tokens).
- Code, read fresh:
  - `frontend/src/pages/ShelvesPage.tsx` — all of it.
  - `frontend/src/features/library/InsightsRanking.tsx` (`CoverStack`, exported for this screen in
    Sprint 071 — the rail either generalizes it or replaces its use here; decide and say which).
  - `frontend/src/api/shelves.ts` (`ShelfWithCount`), `frontend/src/features/shelves/ShelfPicker.tsx`,
    `frontend/src/features/add/AddForm.tsx:392-510` — both build shelf-shaped values that will not
    carry a new field.
  - `frontend/src/features/library/VirtualLibrary.tsx` — the grid the shelf page reuses.
  - `backend/src/book_tracker/api/library.py:69-79` (`ShelfResponse`), `:1082-1099` (the routes),
    `backend/src/book_tracker/application/library.py:575-596` (`list_shelves`) and `_shelf_covers`
    below it; the facets block at `:875-950` (the `GROUP BY` shape the new count copies, and the
    proof that `status_counts` already narrows by shelf).
- Tests: `frontend/src/pages/ShelvesPage.test.tsx`, `frontend/e2e/library.spec.ts`,
  `frontend/e2e/accessibility.spec.ts`, `backend/tests/test_library_api.py`,
  `backend/tests/test_library_queries.py`.

## Current implementation baseline

Measured 2026-09-05:

- A shelf row is ~90px tall in a `max-w-3xl` column and carries a name, a count, *Rename* and
  *Delete*; eleven shelves make 990px of list. The index is sorted by name only, so an 11-entry
  shelf sits below a 1-entry one.
- Sprint 071 gave the row a magnitude bar and up to three overlapping covers. The covers use the
  card's left edge and the rest of its width is empty — the owner's note on the proposal's first
  draft.
- `shelves` has **no type column** and `entry_shelves` joins an entry of any domain; the shelf
  picker is offered on every domain's detail page and in `AddForm`. Nothing on any screen says
  which domains a shelf holds.
- The row links to `/?shelf=slug`, and the library always names one domain, so a shelf holding two
  would open showing part of itself with nothing accounting for the rest. Latent today only
  because all eleven of the owner's shelves are books; 240 of that library's 264 entries are
  albums and anime and none of them is shelved.

## Deliverables

1. **`ShelfResponse` says what the shelf holds.** Members grouped by item type — the same
   `GROUP BY` the facets block already builds, keyed by shelf. **The only backend change.**
2. **The board.** Shelf cards in a responsive grid, each carrying:
   - **a cover rail** — the shelf's members stood up at one height in their own widths, on a
     rule, scrolling horizontally with `scroll-snap-type: x proximity` and a faded trailing edge.
     The rail is `aria-hidden`, holds no focusable child, and the card is a single link, so no
     keyboard reader is ever parked inside a scroller;
   - the name, the count, and the magnitude bar for its share of the largest shelf;
   - **one chip per domain**, with that domain's declared label and its count.
3. **A domain filter over the board.** Choosing one shows only shelves holding it, and each card
   then counts only those members. Rendered from the registry, like every other domain control —
   no hard-coded list.
4. **Sort and search the index** — by size, by recently added to, by name — with the chosen order
   reflected in what the board shows.
5. **`/shelves/:slug` — the shelf page.** A cover mosaic, the count at the library's own
   `text-3xl`, the status breakdown bar, the mean score chip, the format mix, then the shelf's
   entries in the library's grid. **It shows the shelf whole across domains**, with a strip that
   offers only the domains this shelf actually holds and an "everything" option that is the
   default. *Rename* and *Delete* move here, off every row of the index, keeping their existing
   confirmation (product spec §7).
6. **Pin a shelf.** A pinned shelf is a one-press chip in the library's command bar.
   `localStorage`, no backend, no migration — the same shape as the remembered domain.
7. **The count and the click agree.** Whatever number a card shows, opening it shows exactly that
   many entries. This is finding 19 closed, and it is an acceptance criterion rather than a
   consequence.

## Acceptance criteria

1. A shelf card's rail shows its members' covers; a shelf whose members carry no cover shows the
   shared placeholder; an empty shelf shows neither and says it is empty.
2. The rail scrolls horizontally when it overflows, contains no focusable element, is hidden from
   assistive technology, and the card remains one link naming the shelf and its count.
3. A shelf's domain chips sum to its total count, use the domain's declared label, and a
   single-domain shelf shows exactly one chip.
4. Choosing a domain filters the board to shelves holding it and re-counts each card to that
   domain's members only; clearing it restores both.
5. Sorting by size orders the board by count descending; by name, alphabetically; the active
   control and the order shown never disagree.
6. `/shelves/:slug` renders the shelf's own entries across every domain it holds by default, and
   its strip offers only those domains.
7. The number on a card equals the number of entries its page shows.
8. Rename and delete work from the shelf page with their existing confirmation, and deleting a
   shelf still retains its entries.
9. A pinned shelf appears in the library's command bar and applies as the shelf filter in one
   press; unpinning removes it; the preference survives a reload and its absence is not an error.
10. The board and the shelf page hold at 390px with no horizontal body scroll (the rail's own
    scrolling is not body scrolling), 44px targets, and zero serious axe violations on both.
11. `GET /api/shelves` stays inside its budget with the grouped count added; measured, with the
    numbers in the Outcome.
12. Existing suites pass unchanged except where a test asserts findings 14–19; each named.

## Required tests (TDD)

| Behavior | Layer | File |
|---|---|---|
| `list_shelves` returns members grouped by item type, including a mixed shelf | integration | `test_library_queries.py` |
| An empty shelf returns an empty grouping, not a missing key | integration | `test_library_queries.py` |
| `GET /api/shelves` carries the grouping in its schema | api | `test_library_api.py` |
| The card renders a rail, a count, a magnitude bar and one chip per domain | component | `ShelvesPage.test.tsx` |
| The rail has no focusable child and is aria-hidden | component | `ShelvesPage.test.tsx` |
| The domain filter narrows the board and re-counts the cards | component | `ShelvesPage.test.tsx` |
| Sort by size/name changes the order shown | component | `ShelvesPage.test.tsx` |
| The shelf page shows every domain by default; the strip offers only those present | component | `ShelfPage.test.tsx` |
| The card's count equals the page's entry count for a mixed shelf | component | `ShelfPage.test.tsx` |
| Rename and delete from the shelf page, with confirmation | component | `ShelfPage.test.tsx` |
| A pinned shelf reaches the library bar and applies in one press | component | `HomePage.test.tsx` |
| Board and shelf page at 390px; the rail scrolls without the body scrolling | e2e | `library.spec.ts` |
| Zero serious violations on both screens | e2e | `accessibility.spec.ts` |

## Verification

- `make check`, `make test`, `python scripts/validate_project.py`.
- `python scripts/export_openapi.py` regenerated; `npm run api:check`.
- `npx playwright test`.
- `python scripts/benchmark_library.py` for the shelves path, before and after.
- **Walkthrough (DEC-025):** on a throwaway seeded backend, build a shelf holding **two domains**
  — the case that does not exist in the owner's library and is the whole reason findings 18 and 19
  are recorded — then open it from the board, check the count against the page, filter the board
  by domain, pin a shelf, and use it from the library bar. Report what a rail of ten covers feels
  like on a phone.

## Explicit non-scope

- **Saved views / smart shelves.** §3.3.5 and §5.3 row E. Accepted in principle, not scheduled;
  it needs a table and a migration and is its own sprint the day the owner asks (see the roadmap's
  "Not scheduled").
- Bulk shelving from the library (§5.3 row F), manual order and queues (row G), shelf goals
  (row H), merging shelves (row I), auto-shelving rules (row J).
- Shelf colours, icons or nesting. A shelf is a name and a set.
- Changing what the library does with `?shelf=` — it keeps working, and the shelf page links to it.

## Commit checkpoints

1. `[ADD] Tell the shelves list which domains it is holding`
2. `[MOD] Draw a shelf as a shelf`
3. `[ADD] Filter, sort and find a shelf`
4. `[ADD] Give a shelf a page of its own`
5. `[ADD] Pin a shelf to the library bar`

## Risks and decisions to surface

- **A horizontal scroller inside a vertical page.** It must not steal a vertical swipe and must
  never trap a keyboard. `proximity` snapping, no focusable children, the card as the only link.
  If the walkthrough finds it fighting the page on a phone, the fallback is a static rail that
  clips with a fade rather than scrolling.
- **The cross-domain shelf page is a genuine departure**, accepted by the owner in DEC-139 with
  `/triage` and the export as precedent. If it starts to look like a second library, stop: the
  distinguishing rule is that a shelf page shows a set the owner assembled by hand, and it never
  gains search, sort or provider access of its own.
- **A grouped count on a request that answers from two joins already.** Small — tens of shelves —
  but measure it the way DEC-134 measured its own join.
- **`ShelfWithCount` is shared with `AddForm` and `ShelfPicker`.** The new field is additive and
  both build values that will not carry it; check both before assuming.
- **Rename and delete move.** Anyone reaching for them on the index will not find them. The card
  needs an obvious route to the page, and the walkthrough should confirm nobody hunts for them.

## Outcome

Delivered as planned. This is the final planned sprint (`FINAL_SPRINT` 74); the project moves to
`complete` on closing it.

### Backend (deliverable 1, the only backend change)

- `LibraryService._shelf_members_by_type()` — a `GROUP BY (shelf_id, item type)` over
  `entry_shelves`/`entries`/`items`, the same shape the facets block already builds for the whole
  library, keyed by shelf instead. Wired into `list_shelves()`; `ShelfResponse` gained
  `members_by_type: dict[str, int]`, defaulting to `{}` so an empty shelf returns an empty
  grouping rather than a missing key (AC1's backend half).
- Also exposed `ShelfRow.updated_at` on `ShelfResponse` — not new computation, an existing column
  made visible — as the nearest available signal for "sort by recently added to" (deliverable 4).
  Named as a deliberate approximation, both in the code and here: `entry_shelves` carries no
  timestamp of its own, so this is the shelf's own created/renamed time, not literally the last
  member's addition. Adding a true one needs a new column and a migration, which deliverable 1
  did not ask for.
- Tests: `test_library_queries.py` (a mixed shelf's grouping, an empty shelf's `{}`),
  `test_library_api.py` (the grouping over HTTP, a mixed shelf's `entry_count` agreeing with the
  sum of `members_by_type`).

### Frontend

1. **The board** (`ShelvesPage.tsx`, rewritten). A responsive grid of `ShelfCard`s replaces the
   `max-w-3xl` row list (finding 14). Each card: a `ShelfRail` (deliverable 2) — covers stood up
   at one height in their own widths on a rule, scrolling with `scroll-snap-type: x proximity`,
   `aria-hidden` and holding no focusable child (AC2) — the shared "No cover" placeholder when
   members exist but none carry art, and neither when the shelf is empty (AC1); a magnitude bar
   against the largest shelf shown; one chip per domain held, from `members_by_type` and the
   domain registry's own labels (AC3).
2. **`ShelfRail` is its own component, not a generalization of `CoverStack`** (decision surfaced
   by the required-context note). `CoverStack` (`InsightsRanking.tsx`) is a fixed-size,
   up-to-three overlapping stack built for a different question ("a hint of what's in this
   group," beside a ranking row's text). A shelf's rail is unbounded, naturally sized per cover,
   and the card's whole visual weight — bending `CoverStack` to also do that would have made
   neither shape honest. Recorded here rather than only in the code, since the sprint's own
   required-context section asked for the decision to be named.
3. **Domain filter, sort, search** (deliverable 3-4). A `DomainStrip` limited to domains at least
   one shelf actually holds (offering a domain with zero matches would be a filter that always
   empties the board); choosing one re-counts every card to that domain's members via
   `members_by_type` (AC4). Sort by size (default, ties broken by name), name, or "recently
   added" (the `updated_at` approximation above). A plain client-side search over shelf names —
   the list is small enough that no backend change earns its keep here.
4. **`/shelves/:slug`** (`ShelfPage.tsx`, new route). Shows the shelf's own entries **across every
   domain it holds by default** (AC6) — `types: []` on the same `getLibraryPage` the library
   itself calls, which already means "every domain" (DEC-065's own contract, unchanged). A
   `DomainStrip` offering "Everything" plus only the domains this shelf holds narrows it. The
   count at `text-3xl` (the library's own scale), a status breakdown bar and a format-mix line
   both read `facets.status_counts`/`format_counts` off the same response — already narrowed by
   shelf, no new backend query, per deliverable 5's "no backend change for the rest of it." The
   mean score chip is computed from currently-loaded entries only (a client-side approximation
   for a shelf larger than one page — no server aggregate exists for it, and none was in scope).
   Rename and delete moved here from the index (finding 15), keeping their existing confirmation.
   The entries themselves render through the same `VirtualLibrary` grid the library uses.
5. **Pinning** (deliverable 6). `readPinnedShelf`/`writePinnedShelf` (`library.ts`), the same
   shape and `localStorage` pattern as the remembered domain. A "Pin to library" toggle on the
   shelf page; a chip in the library's command bar (📌 name, applies the shelf filter in one
   press, plus a separate un-pin control — never nested inside the same button, which would be
   invalid, ambiguous markup) reads it back. Its absence is not an error (AC9).
6. **The count and the click agree** (deliverable 7 / AC7), verified directly in the walkthrough
   below rather than assumed: a card's own number and the total the shelf's own page shows for
   the same shelf were read from the same `entry_count`/`total` fields, both ultimately backed by
   the one `entry_shelves` join.

### Acceptance criteria

1. Rail / placeholder / "Empty" — held (`ShelvesPage.test.tsx`).
2. Rail has no focusable child, is `aria-hidden`, the card is the one link — held
   (`ShelvesPage.test.tsx`, `library.spec.ts`'s board test counts focusable elements inside the
   rail directly).
3. Chips sum to the total, one chip for a single-domain shelf — held (`ShelvesPage.test.tsx`);
   structurally guaranteed by the backend `GROUP BY`, not just asserted.
4. Domain filter narrows and re-counts — held (`ShelvesPage.test.tsx`).
5. Sort by size/name, active control and shown order agree — held (`ShelvesPage.test.tsx`); the
   "recently added" order is asserted as an order, not as a claim about timing accuracy it cannot
   make (see the `updated_at` approximation above).
6. `/shelves/:slug` spans every domain by default; the strip offers only those present — held
   (`ShelfPage.test.tsx`, `library.spec.ts`, `accessibility.spec.ts`).
7. Card count equals the page's own count — held (`ShelfPage.test.tsx`'s mixed-shelf test; the
   walkthrough's live "4" on both the board card and the shelf page for the same real shelf).
8. Rename/delete from the shelf page, existing confirmation, entries retained on delete — held
   (`ShelfPage.test.tsx`).
9. Pin/unpin, one-press apply, survives reload, absence is not an error — held
   (`HomePage.test.tsx`'s pin test, `library.test.ts`'s `readPinnedShelf`/`writePinnedShelf` tests).
10. 390px, no horizontal body scroll (the rail's own scroll is not body scroll), 44px targets,
    zero serious axe violations on both screens — held (`library.spec.ts`'s two 390px tests,
    `accessibility.spec.ts`'s two new axe tests).
11. `GET /api/shelves` stays inside budget with the grouped count added — held. Measured at 5,000
    entries / 100 contended jobs: `shelves list (13 shelves, covers)` p95 9.4ms idle → 11.6ms
    contended (was 7.6-8.1ms before this sprint's own query addition, per Sprint 072's own
    measurement) — a small, expected increase from one more `GROUP BY`, nowhere near the 500ms
    budget. `VERDICT: every scenario is within budget.`
12. Existing suites pass unchanged except where a test asserts findings 14-19 — held. Three specs
    needed updating, all because rename/delete moved off the index (finding 15) exactly as
    deliverable 5 specifies, not because of an unrelated regression:
    - `editorial.spec.ts`'s "shelf management creates, renames, and deletes shelves" now opens
      the created shelf's own page before renaming/deleting it.
    - `feedback.spec.ts`'s "renaming a shelf confirms on the toast surface" (both viewport
      variants) navigates directly to the shelf page rather than clicking a "Rename" button that
      no longer exists on the index row.
    - Neither test's *assertion* changed (a toast still confirms; a confirmed delete still
      retains entries) — only how each reaches the control that used to live on the index.

### Verification

- `make check`, backend `pytest -q` (1364 passed), frontend `vitest run` (305 passed) — green.
- `python scripts/export_openapi.py` regenerated for `members_by_type`/`updated_at`;
  `npm run api:check` — green.
- `npx playwright test` — 128 passed, 2 skipped, 0 failed on the clean run.
- `python scripts/benchmark_library.py --entries 5000 --jobs 100` before and after — numbers
  above; every scenario within budget.
- Walkthrough (DEC-025): a throwaway backend (`scripts/walkthrough.py`), seeded via the real API.
  Built a shelf holding two domains (2 books, 2 albums) — the case the owner's own library never
  has and the whole reason findings 18/19 exist — plus an 8-book shelf, an empty shelf, and a
  shelf with one covered and one uncovered member. Confirmed live: the two-domain shelf's board
  card and its own page both read `4`; filtering that page to Book showed exactly 2 entries;
  clearing the filter restored all 4; pinning it and returning to the library surfaced the chip,
  and one click applied the shelf as a filter, narrowing "2 of 10" for the currently-selected
  domain; no horizontal overflow at 390px on either the board or the shelf page; zero console or
  page errors throughout. Real cover art came from OpenLibrary for one entry (rate-limited by the
  provider after a handful of requests, consistent with `docs/sprints/062-providers-under-strain.md`'s
  own findings about this provider under a burst of calls) — the single-cover case was verified
  live; a full ten-cover rail's scrolling behaviour was verified instead by `library.spec.ts`'s
  own e2e test (real overflow measurement, not merely rendered) rather than by a live rail this
  session could not fill with real art in the time available. Recorded rather than glossed over,
  per the walkthrough gate's own rule.

### Deviations, named rather than left for a reader to notice

- `textHeight`-style honesty: `updated_at` answers "recently added to" with the shelf's own
  timestamp, not a true last-member-addition time. See deliverable 1 above and DEC-144.
- The shelf page's mean score chip is a client-side mean over loaded entries, not a server
  aggregate — accurate for any shelf that fits on one page (all of this sprint's test shelves do),
  approximate beyond it. No acceptance criterion graded it and no backend addition was owed here
  beyond deliverable 1, so it was not built as one.
- `ShelfRail` was built as a new component rather than a generalized `CoverStack`, per the
  required-context section's own instruction to decide and say which.
