# Sprint 027 — Library shell and shelves

**Status:** ready
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
  bulk shelf assignment.

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
6. Nothing renders a format as a shelf, and shelf assignment still works in triage in bulk.
7. Every behaviour the suite covers is unchanged: imports, triage, undo, bulk edit, backup, formats
   and statuses.

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

_Not started. On completion record delivered behavior, commands and actual results, commit IDs,
deviations/decisions, and impact on every future sprint._
