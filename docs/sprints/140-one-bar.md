# Sprint 140 — One bar

**Sprint:** 140
**Status:** planned
**Roadmap revision:** 56
**Depends on:** 139
**Owner:** Mauro

## Objective

The top bar's field is the one place to find and to add, on every screen. *Add* and *Import* leave the navigation and the Library's own search field goes.

## Required context

- DEC-193; [`../library-first-proposal.md`](../library-first-proposal.md) section 2.1 and 3.2 and the mockup.
- DEC-165 (the command bar), product spec 4.3–4.4 (search flow, add by URL), DEC-164 (EPUB drop).
- Frontend: `components/AppShell.tsx`, `features/command/` (`CommandBar.tsx`, `CommandBarProvider.tsx`, `GlobalDrop.tsx`), `pages/LibraryPage.tsx` (its search field, *Search*, *Add*, *Inbox*), `pages/AddPage.tsx`, `pages/ImportPage.tsx`, `features/add/`.
- `e2e/command-bar.spec.ts`, `e2e/add-detail.spec.ts`, `e2e/add-ebooks.spec.ts`, `e2e/library.spec.ts`, `e2e/import.spec.ts`.

## Current implementation baseline

Observed 2026-11-23 while writing the proposal (section 2); re-observe at activation. The command bar opens from a button drawn as a field; it lists actions and, typed into, provider candidates per medium. The Library toolbar has its own field that filters the grid and shows web results, an *Add* button to `/add` and an *Inbox N* link. The navigation has *Add* (the manual form and the EPUB drop) and *Import* with the Inbox badge.

## Deliverables

1. **A real input.** The shell's field is an `<input>` labelled "Search your library, or add something"; typing opens the results beneath it, ⌘K focuses it. On a phone it opens from the tab bar's centre button.
2. **Library first, then the web.** Results list matching entries (open), then provider candidates with **Add**, which files under the medium's default status and offers the other statuses in place. Links and ISBNs resolve as today.
3. **The Library filters as you type.** On `/library` (and `/` after 141) the same field drives the grid's query; the toolbar's field and *Search* button are removed.
4. **Two last resorts in the footer.** *Enter it by hand* opens `/add`; *Bring a whole list* opens `/import`. Both leave the navigation; the routes stay. The Inbox count shows beside the Library's count as "N to sort".

## Acceptance criteria

1. Typing a title that is in the library lists it first; choosing it opens its page. A title that is not lists web results; **Add** creates the entry with the default status without leaving the screen.
2. On the Library, typing filters the grid; clearing restores it; the URL carries the query as before.
3. The navigation has no *Add* and no *Import*; both pages are reachable from the bar's footer by keyboard.
4. A dropped EPUB anywhere still imports. No serious axe violation with the results open, at 390 and 1440 px.

## Required tests (TDD)

`CommandBar` (library results, add in place, footer), `AppShell` navigation, `LibraryPage` query wiring (Vitest); `e2e/command-bar.spec.ts`, `e2e/library.spec.ts`, `e2e/add-detail.spec.ts`.

## Verification

Per DEC-167: the tests covering the changed code, `make check`, the Playwright specs for the changed screens, and a look at them in the running app at 1440 and 390 px in *Ink* and *Paper*. Add one real title through the bar against live providers in the walkthrough.

## Explicit non-scope

The Library moving to `/` (141). Changing the Add form or the import flow.

## Commit checkpoints

`[MOD]` the field is an input; `[ADD]` library results and add in place; `[MOD]` the Library filters from the bar; `[MOD]` navigation; `[DOCS]` close.

## Risks and decisions to surface

- Every e2e spec that adds an item reaches the form or the bar; selectors move.
- The bar's action list (go to, toggle theme) stays, below the results.

## Outcome

_Not started. On completion record delivered behavior, commands and actual results, commit IDs, deviations/decisions, and impact on every future sprint._
