# Sprint 043 — Row-only Triage decisions

**Status:** in_progress
**Depends on:** 042
**Roadmap revision:** 23

## Objective

Finish the owner-approved Triage interaction: one quiet icon action per row, no second commit
surface, and no lost target when the owner temporarily leaves the screen.

## Required context

- `docs/specs/product-spec.md` section 7 and `docs/specs/technical-spec.md` section 8.
- DEC-095 and the owner's accepted follow-up in DEC-096.
- `frontend/src/pages/TriagePage.tsx`, `frontend/e2e/triage.spec.ts` and
  `frontend/e2e/accessibility.spec.ts`.

## Acceptance criteria

1. The row commit action is an icon-only yellow check on a dark circular surface at every width,
   while its accessible name still includes the target and title.
2. Changing a row target creates no request and no global Apply/Discard toolbar. The row check is
   the only commit action for that decision; explicit checkbox bulk actions remain unchanged.
3. A target draft survives navigation to Detail or Library and a refresh in the same browser tab.
4. Successful row commits remove their draft; failed commits leave it visible and retryable.
5. Focused Triage and accessibility browser coverage plus frontend type checking pass.

## Verification

```bash
cd frontend && npm run test:e2e -- --project=chromium --workers=1 e2e/triage.spec.ts
cd frontend && npm run test:e2e -- --project=chromium --workers=1 e2e/accessibility.spec.ts --grep triage
cd frontend && npm run typecheck
```

This is user-visible and requires a realistic browser walkthrough before closure.

## Explicit non-scope

- The explicit checkbox bulk-action toolbar.
- Score persistence, which remains immediate.
- The two filtered-state copy rough edges recorded by Sprint 042.

## Outcome

_In progress._
