# Sprint 139 — One frame

**Sprint:** 139
**Status:** ready
**Roadmap revision:** 56
**Depends on:** 138
**Owner:** Mauro

## Objective

Every screen that survives DEC-193 unchanged uses one of two page widths, the one `PageHeader`, one cover component and one medium chooser. No behaviour changes.

## Required context

- DEC-193; [`../library-first-proposal.md`](../library-first-proposal.md) section 2.4 and 3.8 and the mockup.
- DEC-136 (one surface) and Sprints 070–071, which introduced `components/PageHeader.tsx` and `components/DomainStrip.tsx`.
- Frontend: `components/PageHeader.tsx`, `components/DomainStrip.tsx`, `components/CoverImage.tsx`, every `<main>` under `pages/` and `features/*/`, `pages/ShelfPage.tsx`, `pages/DiaryPage.tsx`, `features/command/CommandBar.tsx`, `pages/AddPage.tsx`.
- `e2e/accessibility.spec.ts`, `e2e/editorial.spec.ts`.

## Current implementation baseline

Seven page widths (`max-w-3xl`, `4xl`, `5xl`, `6xl`, `7xl`, 1280 px, 1600 px), each written on its page's `<main>`. `PageHeader` exists and fifteen pages use it; Home, Library, Shelves and Insights write their own titles. The medium chooser is `DomainStrip` on the Library, a hand-written `radiogroup` on Insights and Shelves, chips in the command bar and a select on Add. A cover with its caption is written out per screen (Library card, shelf page, Diary, Home, Shelves).

## Deliverables

1. **Two widths.** A `PageFrame` component (`wide`, 1440 px, for screens of covers; `reading`, 960 px, for text and forms) owns `<main>`, its width and padding. Every page uses it; no page writes a `max-w-*` on `<main>`.
2. **One chooser.** `DomainStrip` gains the underlined-tab drawing as its one look and replaces the hand-written choosers on Insights, Shelves and the command bar. Add keeps a select: it is a form field.
3. **One cover.** A `Cover` component (sizes `s`, `m`, `l`; the medium's aspect ratio; one caption: title, creator, an optional score) used by the shelf page, the Diary, the pile, the year review and Home's modules. The Library's virtualised card keeps its controls and takes the same drawing and caption.
4. **One header.** Pages that survive (Add, Import, Inbox, Settings, the pile, Lent out, the decks, tiers, people, a shelf, the year review) share `PageHeader` at one size. Home, the Library toolbar, the Shelves index, Insights and the Diary are left for the sprints that replace them.

## Acceptance criteria

1. No `<main>` outside `PageFrame` sets a width (a test reads the sources).
2. Insights, Shelves and the command bar render `DomainStrip`; choosing a medium behaves as before (existing tests pass unchanged apart from selectors).
3. A shelf page, the Diary and the pile draw covers through `Cover`; a square medium is square.
4. No serious axe violation and no horizontal overflow at 390 and 1440 px on the changed screens; the Library's DOM budget tests (DEC-023) pass unchanged.

## Required tests (TDD)

`PageFrame`, `Cover`, `DomainStrip` (Vitest); a source test for widths; the changed pages' existing Vitest files; `e2e/accessibility.spec.ts`, `e2e/shelves.spec.ts`, `e2e/insights.spec.ts`, `e2e/command-bar.spec.ts`.

## Verification

Per DEC-167: the tests covering the changed code, `make check`, the Playwright specs for the changed screens, and a look at them in the running app at 1440 and 390 px in *Ink* and *Paper*.

## Explicit non-scope

Moving or merging any screen (140–146). New copy. Theme presets (148).

## Commit checkpoints

`[ADD]` PageFrame; `[MOD]` one chooser; `[ADD]` Cover; `[MOD]` headers; `[DOCS]` close.

## Risks and decisions to surface

- The Library card is virtualised and budgeted; it shares the drawing, not necessarily the component.
- A wider or narrower page can move a Playwright assertion that reads positions.

## Outcome

_Not started. On completion record delivered behavior, commands and actual results, commit IDs, deviations/decisions, and impact on every future sprint._
