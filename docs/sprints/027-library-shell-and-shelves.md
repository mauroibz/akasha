# Sprint 027 — Library shell and shelves

**Status:** completed
**Depends on:** 026
**Roadmap revision:** 11

## Objective

**The screen the owner spends their time in stops fighting them.** The library selects a domain
rather than mixing them, the grid uses the whole page instead of scrolling inside a box, and a book
gets onto a shelf without opening a dialog named after something else. The sprint succeeds when the
owner can sit on `/` and do those three things without noticing the machinery.

This is the last feature work before the two contract sprints (DEC-058), and all three items are the
owner's own words from 2026-08-14 — items 1, 4 and 5 of the roadmap's "Owner feedback" section, with
their causes already traced.

## Required context

1. `AGENTS.md`, `docs/agent/WORKFLOW.md`
2. `docs/sprints/ROADMAP.md` — "Owner feedback", items **1, 4 and 5**, which carry the causes
3. `docs/decisions.md`: **DEC-059** (shelves are the higher tier — formats are not shelves and must
   not be rendered as one), **DEC-060** (what a domain declares, and the `status_counts_by_type`
   facet this sprint's tabs build on), DEC-023 (the pinned card box), DEC-058 (why this is scheduled)
4. Sprint 013's file — the grid layout repair, whose scale and feed-semantics checks this re-runs
5. Sprint 026's Outcome, especially the chip rows the tabs will scope
6. `docs/specs/product-spec.md` section 7; `docs/specs/technical-spec.md` sections 7.2 and 8
7. `docs/agent/HANDOFF.md` and the last worklog entry

## Current implementation baseline

Observed 2026-08-15 at Sprint 026's close. **Re-derive at activation.**

- `GET /api/entries` has **no `type` filter**. Sprint 025 left it out deliberately (its AC4 only
  required that a mixed library paginate correctly, which it does).
- `facets.status_counts_by_type` already groups by item type, so the count a tab needs exists;
  what does not exist is a way to *filter* by one.
- The chip rows in `frontend/src/pages/HomePage.tsx` are one group per domain, fed by
  `GET /api/item-types`. With a domain selected, the other domains' rows should not be rendered
  at all.
- `frontend/src/features/library/VirtualLibrary.tsx` gives the virtualizer's scroll container
  `h-[min(70vh,760px)]`, so the grid is a fixed box inside a `max-w-7xl` page. The virtualizer
  measures that element, which is why it was written that way — it is not decorative.
- Shelf membership is edited inside `OpinionDialog`; creating a shelf is the whole `/shelves` route.
  `POST /api/shelves` and the entry's `shelf_ids` already do what is needed, and triage already has
  bulk shelf assignment. **[Corrected at activation: it does not.** `add_shelves` exists on the bulk
  endpoint and is tested, but no control in `TriagePage.tsx` ever sent it, and product spec §7 said
  so at line 671. AC6 was untestable as written; the control was built instead.]

## Deliverables

1. **A `type` filter on the list API**, repeated like `status`, validated against the registry, and
   included in the cursor's `filter_key` — Sprint 026's own note about `_filter_key` applies exactly
   as much here, and forgetting it is a silent paging bug rather than a test failure.
2. **A domain tab strip** fed by `GET /api/item-types`, with the choice in the URL the way every
   other filter is. **The default is the open question** — all, or the last domain used. Settle it
   with the owner rather than silently. With a domain selected, only that domain's status chips
   render.
3. **The page scrolls, not the grid.** `@tanstack/react-virtual` measures the window directly; the
   fixed height comes off the scroll container. Re-run Sprint 013's scale checks (10,000 entries) and
   the accessibility feed semantics against it rather than assuming they survive.
4. **Inline shelf editing** on the detail page and on a card, with create-on-type in the same
   control. Shelf membership leaves `OpinionDialog`. **A format is not a shelf** (DEC-059) and the
   two controls must not converge.
5. **If Sprint 026 had deferred its tracklist slice it would land here.** It did not, so this is
   noted only to close the question.

## Deliverables — second pass, folded in 2026-08-15 after the first close

The owner tried the closed sprint and raised the add flow, which is the same complaint one screen
over: *"the search page, after you clicked on an item, feels empty. If we have the data, we could
show the metadata there before confirming. Also on that same screen we should allow users to search
and create shelves on the spot. A dropdown menu that allows for new shelf creation instead of
checkboxes makes more sense. Same for everything that can be changed in the 'edit opinion' panel,
notes, format for music, etc."*

**Measured before designing.** A search candidate already carries `title`, `subtitle`, `creators`,
`credit`, `year`, `original_year`, `language`, `identifiers` and `cover_url`; the confirm screen
renders three of them and discards the rest. It does **not** carry publisher, page count,
description or subjects for a book, or label, catalogue number, format or tracklist for a record —
those come from the per-item fetch that runs at add time, and there is no provider response cache,
so previewing them costs one quota-counted request per candidate clicked.

6. **The confirm screen shows what is already known**, for free and instantly, rendered from the
   domain's field spec rather than from a book-shaped list.
7. **A full record on demand.** `GET /api/search/preview` fetches one candidate's complete payload
   without writing anything, behind the same quota guard as any other provider request. One request,
   and only when the reader asks for it.
8. **Shelves are chosen the same way everywhere** — the create-on-type control from deliverable 4,
   moved somewhere shared and used on the add screen in place of its checkboxes.
9. **The opinion is set while adding** — notes, formats and the domain's own passage fields, so a
   book you just finished does not need adding and then immediately editing. `POST /api/entries`
   accepts them and validates each against the item's own domain, exactly as `PATCH` does.
10. **A format is picked the same way everywhere too** — one closed multi-select control, shared by
    the add screen and the opinion dialog, replacing the checkbox row. **It stays visibly distinct
    from the shelf control** and offers no create option: DEC-059's rule is that a format is never
    rendered as a shelf, and a closed vocabulary you pick from is not a tier you invent.

## Acceptance criteria

1. Choosing a domain shows only that domain's entries, and the choice survives a reload and a back
   button.
2. A cursor cut under one domain filter is refused under another rather than paging wrongly.
3. The library scrolls with the page, with no inner scrollbar, at every breakpoint the design system
   supports.
4. 10,000 entries still scroll smoothly and the feed's accessibility semantics still hold, proven by
   the checks Sprint 013 introduced rather than by inspection.
5. A book can be put on a new shelf from the detail page without opening the opinion dialog and
   without leaving for `/shelves`, in at most one control.
6. Nothing renders a format as a shelf, and shelf assignment works in triage in bulk. *(Restated:
   "still works" assumed a control that had never been built.)*
7. Every behaviour the suite covers is unchanged: imports, triage, undo, bulk edit, backup, formats
   and statuses.
8. Clicking a search result shows every field the search already returned, with no provider request
   made and nothing to wait for.
9. A full record can be fetched before confirming, costs exactly one provider request, is refused
   when the daily quota is spent, and writes nothing to the library.
10. A shelf can be created and applied from the add screen, in the same control as on the detail
    page, without leaving for `/shelves`.
11. Notes, formats and the domain's passage fields can be set while adding, and a field the item's
    domain does not have is refused with a 422 naming the domain rather than silently stored.
12. Nothing renders a format as a shelf, on any screen: the format control offers a closed
    vocabulary and no way to invent a value.

## Required tests (TDD)

- A `type` filter returns only that domain, and an unknown type is a 422.
- A cursor from a `type`-filtered query is rejected against an unfiltered one.
- The tab strip renders from the registry and not from a hardcoded list.
- The virtualizer measures the window: a test that would fail against a fixed-height container.
- The 10,000-entry scale test and the feed-semantics accessibility test, re-run against the new
  scroll model.
- Creating a shelf from the detail page adds it and assigns it in one flow.

## Verification

```bash
python scripts/validate_project.py
make format && make check && make test
cd frontend && npm run test:e2e
cd .. && make build && make smoke-container
git diff --check
```

Plus the walkthrough gate against a library holding books and albums: switch domains, scroll the
whole library with the page, put a book on a brand-new shelf from its detail page, and report what
you saw.

## Explicit non-scope

- **The domain contract and the conformance suite.** That is Sprint 028, and this sprint must not
  start extracting one from what it touches.
- Per-domain imports (Sprint 029).
- Shelf hierarchy, shelf colours, drag-and-drop between shelves. The friction the owner named is
  *distance*, not expressiveness.
- Re-opening DEC-059. Formats are settled and shipped.

## Commit checkpoints

1. `feat: filter the library by domain`
2. `feat: choose a domain from the library`
3. `fix: let the library scroll with the page`
4. `feat: shelve a book without leaving the page`
5. final `docs(sprint-027): close sprint and hand off`

## Risks and decisions to surface

- **The default tab is a product decision.** "All" keeps today's behaviour and makes the tabs
  optional; "last used" is what a person with 400 books and 30 records probably wants. Put it to the
  owner with a recommendation.
- **Deliverable 3 touches the one thing Sprint 013 was called in to repair.** It wants its own slice
  and its own verification pass, not to be folded into a feature commit.
- **Inline shelf editing on a card is where scope grows.** A card is 260px wide with a pinned box
  (DEC-023); if the control does not fit, the detail page alone is a complete deliverable and the
  card can wait.
- The status chip rows and the tab strip are the same information at two levels. Decide whether the
  chips stay grouped when "all" is selected or the tabs replace the grouping entirely.

## Outcome

**Completed 2026-08-15** on `sprint-025-albums` (DEC-063), four implementation commits
`80fea5f`..`531f38f` plus this one. Nothing pushed.

### Delivered

1. **`type` on `GET /api/entries`** (`80fea5f`) — repeated like `status`, validated against a
   published `ItemTypeName` union spelled out for mypy and pinned to `DOMAINS` by a test, in
   `_filter_key` so a cursor is bound to it. Unlike `shelf` and `format`, repeating it *widens*: a
   row has one type. The facet asymmetry is DEC-062: both status facets clear `type`, `format_counts`
   applies it.
2. **The domain tab strip** (`b679229`) — from `GET /api/item-types`, present only when the build
   has more than one domain. Default settled with the owner: **the last domain used**, in
   `localStorage`, written into the URL on mount so the choice is an ordinary filter thereafter. A
   chosen tab renders one chip row without the redundant heading and narrows the format selector;
   "All" keeps DEC-060's grouped rows. Switching tabs drops statuses the new domain lacks.
3. **The page scrolls, not the grid** (`699ab9b`) — `useWindowVirtualizer` with a `scrollMargin`
   read from the bounding rect plus `window.scrollY` (not `offsetTop`, which walks offset parents
   the motion wrapper interrupts), observing `document.body` as well as the list because the chips
   above it reflow without the list's own size changing.
4. **Inline shelf editing** (`531f38f`) — chips plus one create-on-type control on the detail page,
   creating and assigning in one action; shelf membership out of `OpinionDialog`, format untouched
   (DEC-059). Plus the **bulk *Add to shelf*** in triage that product spec §7 has listed since v1 and
   that was never built.

### Verified

`validate_project.py`, `make check`, `make test` (**414 backend, 120 frontend**, from 411/110),
`npm run test:e2e` (**86 passed, 2 skipped**, from 84/2), `make build`, `make smoke-container`,
`git diff --check` — all green.

Walkthrough in Chromium against the **real dev library** (7 books, 2 albums) at `127.0.0.1:8123`,
no console or page errors anywhere:

- Tabs render `All / Book / Album`. Choosing Album gives `?type=album`, two records, one chip row
  (`Inbox 0 · Wishlist 0 · On the way 0 · Owned 2`) with no domain heading, and a format selector of
  `Vinyl 2 · CD 1 · Digital 1` — no `Physical`. Under "All": both grouped rows, and the flat
  five-format union with `Digital` once.
- The choice survives a reload, and survives opening a record and pressing back. **It does not
  survive `history.back()` from the library itself, and cannot**: every filter uses
  `replace: true` so that fiddling with filters does not stuff the history stack, which predates
  this sprint and applies to sort, shelf, status and format equally.
- The feed has **0px of inner scroll** at 375, 768 and 1440 while the document scrolls, with no
  horizontal overflow and 1/2/4 columns respectively. `j` six times moves focus to entry 11 and
  scrolls the window to 341px with the focused row fully in view.
- *Cien años de soledad* onto a brand-new shelf "Latin American" from its detail page, in one
  control, with no dialog opened and no navigation; then "Work" added from the same control and
  removed again. The opinion dialog no longer mentions Shelves and still offers Format.
- Two rows selected in triage and put on "Work" in bulk: `entry_count` 1 → 3.
- API directly: `type=wine` is 422; a cursor cut under `type=book` is 400 `invalid_cursor` when
  replayed unfiltered or under `type=album`.

### Deviations and decisions

- **AC6 rested on a false premise** and was restated: bulk shelf assignment existed only on the
  endpoint. Building the control was the owner's call at planning time and is deliverable 4b.
- **No shelf control on a library card.** The sprint named this as where scope grows; the owner
  chose detail page plus triage bulk instead.
- **Two things fixed in passing**, both the same bug class as work being done: `libraryMotionKey`
  never included `formats` (Sprint 026), so changing that filter swapped the list with no crossfade;
  and cmdk points its input's `aria-labelledby` at the element its `label` prop renders, which beats
  an `aria-label` on the input, so the shelf input had no accessible name until it was given there.
- **jsdom has no `ResizeObserver`**, which cmdk constructs on mount; `src/test/setup.ts` shims one
  beside the existing pointer-capture shims.
- One flaky failure observed once: `triage animates its action bar but not under reduced motion`
  failed in a full-file run and passed alone and on every re-run, including the full suite. Motion
  sampling timing, not a regression.

### Second pass — the add flow (folded in after the first close)

The owner tried the closed sprint and reported the add screen, which is the same complaint one
screen over. Three commits `762ed70`..`d722135`, and DEC-064.

6/7. **The confirm screen shows what is already known, and asks before fetching more** (`762ed70`).
Measured first, and the answer was *partly*: a candidate already carries subtitle, year, original
year, language and every identifier, and the screen rendered three fields of it. Those now render
for free, from the domain's field spec. `GET /api/search/preview` fetches the rest — the
description, the page count, the tracklist — on a button, writing nothing, recorded against the
quota but never blocked by it (DEC-045's rule for search, for the same reason).

8/9. **Shelves and the whole opinion, while adding** (`a8709e4`). The create-on-type control moved
to `features/shelves` and is shared with the detail page. `POST /api/entries` accepts `notes`,
`formats` and the domain's passage fields, validated against the item's own domain and refused with
a 422 **before the write**, so a refusal leaves no half-added row.

10. **One format control** (`a8709e4`), shared by the add screen and the opinion dialog, replacing
both checkbox rows. Closed, no create option, visibly not the shelf control — DEC-059 turns on that
distinction and a single widget doing both would erase it.

**Two defects the unit tests could not see**, each caught by the gate built for it:

- **The axe gate caught the first pass's tab strip.** It was a Radix `Tabs` whose triggers pointed
  `aria-controls` at a `TabsContent` that was never rendered — a critical `aria-valid-attr-value`
  failure. It is a radio group now, the pattern `AddPage` already used for the same choice.
- **The walkthrough caught a fact named twice.** Both domains declare `language` and books declare
  `original_year`, while a candidate carries columns of the same names, so a real MusicBrainz record
  rendered "Language: eng" twice (`d722135`). The domain's label wins; the candidate's column is the
  fallback value.

**One e2e assertion was rebased, not weakened.** "A card status listbox is not recycled out from
under the reader" asserted the scroll container's `scrollTop` was exactly 0. With the page as the
scroll container, Radix's scroll lock leaves a measured 2px residual, so a 4000px gesture is now
bounded to under 10px, with the reason recorded in the test.

### Second-pass verification

`make check`, `make test` (**419 backend, 126 frontend**), `npm run test:e2e` (**86 passed, 2
skipped**) — all green. Walkthrough against the real dev library and **live providers**: searching
MusicBrainz showed year and artist credit instantly with **zero** preview requests; *Load full
details* spent exactly one and added label, catalogue number, country, format and track count, after
which the button is gone. A record offers notes and formats and **no** dates or reread count
(DEC-057); a book offers all of them. Added *Rayuela* with a brand-new shelf "Rayuelas", notes, the
`physical` format, a finished date and a reread count of 2 — all in one action, all persisted
(entry 17), with publisher and page count fetched. No console or page errors.

### Impact on later sprints

- **Sprint 028** — the conformance suite gains what a domain now gets for free by existing: a tab,
  its chips, its formats, its counts, its add-screen facts and its add-screen opinion fields. `ItemTypeName` is a third published union to check for drift.
  The facet asymmetry in DEC-062 is a rule the contract has to state, not a detail.
- **Sprint 029** — unaffected. Import remains book-only and triage remains domain-agnostic, which is
  why `EntryFilter` deliberately did **not** gain `type`.
