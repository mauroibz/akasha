# Sprint 150 — Personalize

**Sprint:** 150
**Status:** completed
**Roadmap revision:** 57
**Depends on:** 149
**Owner:** Mauro

## Objective

Arranging the Library's front is renamed Personalize and redrawn as a standard widget editor: only placed things on the page, one plus square to add, a dialog with a list and a real preview, and the page's own settings in one bar. *On now* and *Lately* can be moved and removed.

## Required context

- DEC-195 points 3 and 4; DEC-185, DEC-192.
- Backend: `application/home_layout.py`, `application/home.py`, `api/home.py`. Frontend: `features/home/` (`LibraryFront`, `useArrange`, `Arrange`), `features/media/YourMedia.tsx`, `features/theme/ThemePicker.tsx`.

## Current implementation baseline

Arrange puts a strip on each showcase and, below them in the page, a tray of every addable thing by kind, then *Your media*, then *Theme*. *On now* and *Lately* are fixed.

## Deliverables

1. **Bands in the layout.** `now` and `lately` are layout keys again, first by default, shown, always full width; hidden ones are not drawn (`now` is still read for the greeting).
2. **A preview endpoint.** `GET /api/home/preview?module=<key>` answers the front's payload for that one module as if it were shown, refusing an unknown key.
3. **Personalize.** The button reads *Personalize*. In the mode: a bar at the top of the front with *Your media*, *Theme*, *Reset*, *Done*; each placed thing keeps its handle, size and remove; after the last, one dashed square with a plus.
4. **The add dialog.** The plus opens a dialog: the addable things by kind on one side, the chosen one's preview on the other drawn by the same component from the preview endpoint, its size choice, and *Add*. *Your media* and *Theme* open as dialogs from the bar.

## Acceptance criteria

1. *Lately* removed in Personalize is gone after a reload and offered in the add dialog; moved, it keeps its place.
2. Choosing an item in the add dialog shows its preview before anything is added; *Add* places it and closes.
3. In the mode the page holds no tray, media list or theme swatches; they are reached from the bar.
4. Operable by keyboard; no serious axe violation in the mode and with the dialog open, at 390 and 1440 px.

## Required tests (TDD)

`test_home_layout.py`, `test_home_api.py` (bands, preview); `LibraryFront.test.tsx`, the add dialog (Vitest); `e2e/home.spec.ts`.

## Verification

Per DEC-167: the tests covering the changed code, `make check`, the Playwright specs for the changed screens, and a look at them in the running app at 1440 and 390 px.

## Explicit non-scope

New kinds of showcase. Per-device layouts.

## Commit checkpoints

One per deliverable, then `[DOCS]` close.

## Risks and decisions to surface

- Listed in the Outcome as they are met.

## Outcome

Completed 2026-11-23 (DEC-195). Commits: `b4d627c` (the bands in the layout, the preview
endpoint), `aa79aee` (Personalize).

- **Bands in the layout.** `now` and `lately` are layout keys, first and shown by default,
  always the full width, with a handle and remove and no size.
- **`GET /api/home/preview?module=`**: one module's payload as if shown; stores nothing.
- **Personalize.** The greeting's button reads *Personalize*, then *Done*. In the mode a bar
  holds *Your media* and *Theme* (dialogs), *Reset* and *Done*; the page holds what is placed
  and one dashed square with a plus. A placed thing with nothing to show is one line.
- **The add dialog.** What is not placed, by kind, on the left; on the right the chosen one
  drawn by the component that would stand on the page, inert, from the preview endpoint; its
  size (not for a band); *Add*. `features/home/Showcase.tsx` is the one renderer for the page
  and the preview. The tray is deleted.

Acceptance: 1 by `test_home_layout.py`, `LibraryFront.test.tsx` and `e2e/home.spec.ts`
(remove, add back, reload); 2 by `Personalize.test.tsx` and the e2e test; 3 by
`LibraryFront.test.tsx`; 4 by the keyboard e2e test and axe in the mode and on the open
dialog at 390 and 1440 px.

Verification: backend, the nine files around the change, 196 passed; Vitest 766 passed; every
Playwright project 249 passed, 2 skipped by design; `make check`. In the running app on a copy
of the development library at 1440 and 390 px: the bar, handles on what is placed, the plus,
the dialog listing 21 things with *How you rate books* drawn in its preview. No overflow, no
console errors.

Deviations:

- The preview is drawn at the dialog's width whatever size is chosen; the size changes how
  much the thing shows, as on a phone.
- A year is still offered for every medium that records a finish, held or not, so on a small
  library the dialog and the default page list years with nothing in them. Left: it is how a
  goal's slots can be shown before the first finish.
- With many shelves and media the dialog's list is long; it scrolls inside the dialog.

Impact: none planned. This closes DEC-195.
