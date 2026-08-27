# Sprint 043 — Row-only Triage decisions

**Status:** completed
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

Completed 2026-08-27 in `bb474c7`.

- The row action is now an icon-only yellow check on a dark circular surface at every viewport,
  while its accessible name still identifies both target and title.
- Changing a target remains a local draft and makes no request. The redundant page-level
  Apply/Discard bar is gone; the row check is the sole commit for that decision, while explicit
  checkbox bulk actions are unchanged.
- Drafts use versioned, tab-scoped session storage, so they survive Detail/Library navigation and
  refresh without leaking across tabs. Success clears only committed drafts; failure retains them
  for retry.
- TDD captured the intended navigation/reload failure before persistence was added. Focused gates
  passed: 20 Triage browser tests, 3 Triage accessibility tests, and frontend type checking.
- Release-level verification after implementation freeze passed: `make check`; `make test` with
  698 backend and 189 frontend tests; full Playwright with 106 passed and 2 intentionally skipped;
  `make build`; and the complete container smoke flow. The first smoke exposed an obsolete manual
  book payload in the harness; updating it to the current domain-neutral API contract made the
  rerun pass, followed by fresh `make check` and `make test` gates.
- The realistic walkthrough used a disposable database with the owner's 81-row MyAnimeList export
  and 18-book Calibre library at 390×844. A book draft survived Library navigation and refresh,
  then committed; an anime suggestion committed directly; and an anime override committed from
  its row. No console or page errors occurred, and live data was untouched.

No API, schema, or product-scope deviation. The two pre-existing filtered-state copy rough edges
recorded by Sprint 042 remain outside this sprint.
