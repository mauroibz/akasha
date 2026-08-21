# Sprint 036 — Import and triage flow

**Status:** in_progress
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

- `npm test -- --run src/pages/ImportPage.test.tsx src/components/ScorePicker.test.tsx src/components/StatusSelect.test.tsx`
- `npm run test:e2e -- --project=chromium e2e/triage.spec.ts e2e/import.spec.ts e2e/accessibility.spec.ts`
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

_In progress._
