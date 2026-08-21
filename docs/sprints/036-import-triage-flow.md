# Sprint 036 — Import and triage flow

**Status:** completed
**Depends on:** 035
**Roadmap revision:** 18

## Objective

Make Import read as two independent steps and let the owner triage entries one at a time without
entering bulk-selection mode, while retaining the existing high-volume workflow behind checkboxes.

## Required context

- `AGENTS.md`; `docs/agent/WORKFLOW.md`; `docs/agent/TESTING.md`.
- `docs/specs/product-spec.md` §7 (`/import`, Triage, inline editing and keyboard flow).
- `docs/specs/technical-spec.md` §8 (virtualization, optimistic writes, accessibility and keyboard
  contracts).
- `docs/decisions.md`: DEC-025, DEC-026, DEC-028, DEC-038, DEC-062, DEC-065, DEC-079, DEC-080,
  DEC-084 and DEC-085.
- `frontend/src/pages/ImportPage.tsx`, `frontend/src/pages/TriagePage.tsx`,
  `frontend/src/components/ScorePicker.tsx`, `frontend/src/components/StatusSelect.tsx`,
  `frontend/src/features/library/VirtualLibrary.tsx`, `frontend/src/api/library.ts`.
- `frontend/src/pages/ImportPage.test.tsx`, `frontend/e2e/triage.spec.ts`,
  `frontend/e2e/accessibility.spec.ts`.

## Current implementation baseline

Observed on 2026-08-21. `/import` presents every connector and Triage as peers in one tab strip,
although connector choice belongs only to the import step. In Triage, clicking anywhere on a row
selects it and exposes the bulk toolbar. Score and current status are not row controls: changing one
entry with a pointer requires selecting it, opening a bulk action menu and choosing the value.
Checkbox selection, Shift ranges, Ctrl/Cmd+A, keyboard focus/actions and virtualization already work
and must remain available.

## Deliverables

1. A prominent two-step switch on the existing `/import` route: **1. Import** and **2. Triage**.
2. Connector tabs nested under Import only, with URL, remembered connector and staged preview/undo
   state preserved across a trip through Triage.
3. Inline domain-aware status and score controls on every mounted triage row, reusing the shared
   controls and the existing optimistic entry-write behavior.
4. Row-body clicks open detail. Only the row checkbox changes pointer selection; range selection,
   select-all, the bulk toolbar and keyboard workflows remain intact.
5. Canonical specifications, decision record and user-facing import documentation reconciled to the
   implemented interaction.

## Acceptance criteria

1. `/import` exposes one main workflow tablist with `1. Import` and `2. Triage`; connector tabs are
   visibly subordinate to Import and absent from the Triage panel.
2. URLs remain `/import?tab=<connector>` and `/import?tab=triage`; `/triage` still redirects; the
   remembered connector and staged preview survive switching to Triage and back.
3. Clicking a row body opens that entry and does not select it or reveal bulk actions.
4. Clicking a checkbox is the pointer action that selects; Shift range, Ctrl/Cmd+A, clear selection
   and every existing bulk action continue to work.
5. Score is editable from each row in two clicks (open, choose), affects exactly that entry, clears
   provisional state, updates optimistically and rolls back with one error announcement on failure.
6. Status is editable from each row, offers that row's domain vocabulary, affects exactly that entry
   and does not alter selection.
7. Keyboard `j`/`k`, score/status hotkeys, Enter, Escape and virtualized bounded-DOM behavior retain
   their existing contracts; inline controls are named and keyboard reachable.
8. The realistic browser walkthrough covers both workflow steps, row-local score/status changes,
   row navigation and checkbox-only bulk selection with no serious accessibility regression.

## Required tests (TDD)

- Import page component: separate workflow and connector tablists; switching, URL, one-main-landmark
  and staged-preview preservation.
- Playwright triage: inline score/status write one entry; controls do not select; row opens detail;
  checkbox reveals bulk toolbar; existing bulk/keyboard/range/virtualization cases remain green.
- Accessibility: Import and Triage, including a selected row and open inline controls.

## Verification

- `npm test -- --run src/pages/ImportPage.test.tsx src/components/ScorePicker.test.tsx`
- Focused TDD checks in `e2e/triage.spec.ts`, then the full Playwright gate after code freeze.
- Realistic browser walkthrough recorded in `docs/agent/worklog.md`.
- After code freeze: `python scripts/validate_project.py`, `make check`, `make test`, and
  `npm run test:e2e` once, following `docs/agent/TESTING.md` for closure reruns.

## Explicit non-scope

- Backend/API/schema changes, new triage filters or batch actions, redesigning the detail screen,
  changing imported-status suggestions, or removing keyboard/bulk triage.

## Commit checkpoints

1. `feat(import): clarify the two-step import and triage flow`
2. `feat(triage): add row-local status and score editing`
3. `docs(sprint-036): close sprint and hand off`

## Risks and decisions to surface

- Fixed-height virtual rows constrain control density. Reuse compact controls and verify narrow
  viewports rather than allowing an expanding row to invalidate virtualization.
- A status edit removes an `unsorted` row from the inbox after the server accepts it; this is the
  intended meaning of triage, but optimistic rollback must restore it on failure.

## Outcome

Completed 2026-08-21.

- `/import` now presents one prominent `1. Import` / `2. Triage` workflow switch. Connector tabs
  exist only inside Import; connector URLs, last-source memory, staged previews, undo history and
  the legacy `/triage` redirect retain their contracts (`142d422`).
- A triage row now opens detail when its body is clicked. Only its checkbox enters pointer
  selection, so the existing Shift range, select-all, keyboard and bulk workflows remain available
  without making one-entry decisions feel like bulk work (`e7dfe05`).
- Every mounted row has named, domain-aware status and score selects. They patch exactly one entry,
  update optimistically, preserve any bulk selection, clear provisional score state on success and
  restore the prior cached row with one announcement on failure. Narrow rows hide redundant
  imagery, and short inboxes fit their content instead of reserving a mostly empty panel
  (`4e8f151`, `cbdf7e4`).
- The final browser gate repaired a suggestion badge's accessibility text, isolated ignored reusable
  walkthroughs from ordinary Playwright discovery, and made the production-bundle test declare its
  item-type boundary (`87d73cc`). Canonical product, technical, owner and domain-extension docs now
  describe the delivered hierarchy and editing behavior.

Acceptance criteria 1–8 passed. Component tests cover the two tab levels, URL transitions, single
main landmark and staged-preview survival. Sixteen Triage Playwright cases cover row-local success
and rollback, row navigation, checkbox-only selection, bulk actions, keyboard shortcuts,
virtualization, motion and mobile geometry; axe covers both unselected and selected Triage states.

Verification after implementation freeze:

- focused Vitest: 31 passed (`ImportPage` and `ScorePicker`);
- `make check`: Ruff, Prettier, ESLint, mypy, TypeScript, OpenAPI and project validation passed;
- `make test`: 559 backend and 179 frontend tests passed; after the final JSX-only accessibility
  correction, the affected frontend gate passed again with 179 tests;
- focused browser checks: 16 Triage cases, 2 Triage accessibility cases and 2 production-bundle
  cases passed;
- full Playwright at one worker: 101 passed, 2 intentionally skipped; scratchpad walkthroughs were
  not collected;
- `python scripts/validate_project.py` and `git diff --check` passed before closure.

The realistic walkthrough used a disposable copy of the owner's real application data at 390 px,
with four entries temporarily placed in the unsorted inbox. It switched between both workflow steps
and connector tabs, changed one score from 8 to 7, changed another row's status to `read` and saw
only that row leave Triage, opened a third row's detail page, and selected a fourth only through its
checkbox to reveal the bulk toolbar. The first visual pass exposed excess blank space under the
short inbox; the corrected pass showed four fitted rows with no horizontal overflow, console error
or page error. The parameterized runner remains locally under ignored `frontend/e2e/scratchpad/`
and is now explicitly opt-in, so future sprints can adapt it without making the normal gate depend
on owner data.

One planned implementation detail changed: the shared expanding score picker cannot fit at a fixed
virtual-row edge, and a portalled Radix select failed `aria-hidden-focus`. DEC-086 records the use of
native selects for this geometry. No API, schema or backend behavior changed. The shared import
route's Calibre-specific missing-`metadata.db` refusal remains observed and out of scope. Existing
Playwright proxy-error chatter from intentionally unstubbed optional requests and Vitest/JSDOM
warnings remain recorded in DEC-084's optimization backlog; they did not hide a failed assertion.
