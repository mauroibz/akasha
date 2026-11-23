# Sprint 140 — One bar

**Sprint:** 140
**Status:** in_progress
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
5. **The bar's medium chooser** is drawn as `DomainStrip` draws one (moved from Sprint 139, whose Outcome says why).

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

Completed 2026-11-23 (DEC-193).

- **Navigation.** Home, Library, Shelves, Insights, Diary. *Add* and *Import* are gone from the
  desktop bar and the phone's tab bar; the routes stay.
- **The field.** On every screen but the Library the shell draws the bar as a wide field,
  "Search your library, or add something", which opens the bar with the cursor in it; ⌘K as
  before. On a phone the bar is the filled button in the middle of the tab bar.
- **The Library** keeps its own field, which is the bar there: it filters the grid as it is
  typed into and searches the web under the existing quota rule. Its placeholder now reads the
  same as the shell's. The toolbar's *Add* and *Inbox N* buttons are removed.
- **The bar's footer.** *Enter it by hand* (`/add`) and *Bring a whole list* (`/import`), always
  shown. Its medium chooser is `DomainStrip` labelled "Search the web for".
- **What waits to be sorted** is a link in the shell, "N to sort", on every screen, absent at
  zero; counted once for both headers.

Acceptance: 1 by the existing `CommandBar` tests (library first, add in place) and the new
footer and chooser tests; 2 by the Library's existing search tests, unchanged; 3 by
`AppShell.test.tsx` and `e2e/editorial.spec.ts`; 4 by `e2e/add-ebooks.spec.ts` and the
accessibility spec.

Verification: Vitest 652 passed; `make check`; Playwright chromium 229 passed before the four
navigation specs were updated, then `editorial`, `add-ebooks`, `resilience`, `command-bar` and
`accessibility` 65 passed. Looked at in the running app at 1440 and 390 px: Shelves with the
field, the Library without it, the bar open on "rayu" with a library result and the footer. No
overflow, no console errors. The web results could not be looked at live: providers are
unreachable from the agent's sandbox ("Searching…" until the request fails).

Deviations:

- **The shell's field opens the bar; it is not itself the input.** The bar is a modal with
  tested focus, paste and drop behaviour, and an input in the shell with results beneath it
  would be a second implementation of the same thing. The owner sees a field in the same place
  on every screen and types into it after one click or ⌘K.
- **The Library's field stays in its sticky toolbar** instead of being driven from the shell.
  That toolbar stays at the top while the grid scrolls and the shell does not, so moving the
  field up would take the search away from someone halfway down their library. On the Library
  the shell's field is not drawn, so a screen never shows two.
- The count reads "N to sort" in the shell on every screen, not beside the Library's count.
- Typing in the bar keeps its existing order: library results, then the web for the chosen
  medium, then actions.

Impact on later sprints: 141 moves the Library to `/`; the shell hides its field by path
(`/library` today), which 141 must change with the route. The greeting line in 141 does not
repeat the to-sort count. 146 changes the phone's tab bar to two places around the same button.
