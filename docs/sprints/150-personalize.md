# Sprint 150 — Personalize

**Sprint:** 150
**Status:** in_progress
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

_Not started. On completion record delivered behavior, commands and actual results, commit IDs, deviations/decisions, and impact on every future sprint._
