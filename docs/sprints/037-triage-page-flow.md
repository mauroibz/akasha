# Sprint 037 — Triage page flow and staged statuses

**Status:** completed
**Depends on:** 036
**Roadmap revision:** 19

## Objective

Let a long Triage inbox use the page's vertical space, and keep one-row status decisions stable until
the owner explicitly applies them.

## Required context

- `AGENTS.md`; `docs/agent/WORKFLOW.md`; `docs/agent/TESTING.md`.
- `docs/specs/product-spec.md` §7 (Triage and inline editing).
- `docs/specs/technical-spec.md` §8 (window virtualization, writes, keyboard and accessibility).
- `docs/decisions.md`: DEC-025, DEC-028, DEC-038, DEC-073, DEC-084, DEC-085 and DEC-086.
- `frontend/src/pages/TriagePage.tsx`, `frontend/src/features/library/VirtualLibrary.tsx`,
  `frontend/src/api/library.ts`.
- `frontend/e2e/triage.spec.ts`, `frontend/e2e/accessibility.spec.ts`.

## Current implementation baseline

Observed on 2026-08-21 after owner use. Triage caps itself at `min(70vh, 760px)` and scrolls inside a
rounded box even though the containing page has vertical space. A row-local status selection patches
immediately, optimistically changes the row, then invalidates the `status=unsorted` query. In real use
that presents as a blink back to Inbox or makes the row leave before the owner has finished reviewing
nearby entries. Score edits work and should retain their immediate-save behavior.

## Deliverables

1. Window-virtualized Triage rows with no nested vertical scroll container.
2. Row-local status drafts that stay visible and make no request until explicitly applied.
3. One apply/discard surface for pending status decisions; apply batches entries by chosen status,
   removes successful drafts and retains failed drafts for retry.
4. Canonical docs and browser coverage reconciled to the corrected interaction.

## Acceptance criteria

1. A long inbox grows down the document and the browser window owns vertical scrolling; mounted rows
   remain bounded and paging still advances near the document bottom.
2. Choosing a row status immediately shows the choice but sends neither a row PATCH nor a bulk PATCH.
3. Pending status count, apply and discard actions are visible and keyboard accessible; discard
   restores Inbox without a request.
4. Apply groups equal status choices into bounded bulk requests, refreshes Triage and Library once,
   and allows successfully changed entries to leave the inbox only then.
5. If any apply group fails, its row drafts remain visible for retry, successful groups are cleared,
   and one error announcement reports the incomplete apply.
6. Immediate row score persistence, checkbox-only pointer selection, explicit bulk status actions,
   keyboard navigation and accessibility retain their contracts.
7. A realistic browser walkthrough exercises a document-long inbox, several staged status choices,
   discard, apply and an immediate score edit.

## Required tests (TDD)

- Playwright Triage: no nested vertical overflow, window scroll reaches virtual rows, bounded mounted
  DOM, row status makes no request before apply, grouping, discard, partial failure and immediate score.
- Accessibility: Triage with pending status decisions and its apply/discard surface.
- Existing Triage bulk, keyboard, mobile and motion cases remain green.

## Verification

- Focused TDD checks in `frontend/e2e/triage.spec.ts` and `frontend/e2e/accessibility.spec.ts`.
- Realistic browser walkthrough recorded in `docs/agent/worklog.md`.
- After code freeze: `python scripts/validate_project.py`, `make check`, `make test`, and
  `npm run test:e2e -- --workers=1` once.

## Explicit non-scope

- Backend/API/schema changes, changing score persistence, changing explicit bulk actions, new Triage
  filters, undoing statuses after a successful apply, or redesigning Import.

## Commit checkpoints

1. `fix(triage): stage row statuses until apply`
2. `fix(triage): move inbox scrolling to the page`
3. `docs(sprint-037): close sprint and hand off`

## Risks and decisions to surface

- Several draft statuses can require several bulk requests because the endpoint accepts one status
  per request. Partial failure must be honest and retryable rather than pretending the apply is atomic.
- Window virtualization needs a measured document offset and a bounded-DOM assertion; merely removing
  `overflow-auto` would render every row or place virtual rows at the wrong document coordinates.

## Outcome

Completed 2026-08-22.

- Triage now virtualizes against the browser window and grows down the document instead of owning a
  nested `70vh` scroller. A deterministic 200-row browser case reaches the final row through page
  scroll while keeping fewer than 30 articles mounted (`b556b1d`).
- Row status choices are visible client-side drafts and send no row or bulk request before Apply.
  Discard restores Inbox without a request; Apply groups entries by status through the existing bulk
  endpoint, clears successful groups, retains failed groups for retry, and invalidates Triage and
  Library once (`b556b1d`).
- Pending-status and explicit checkbox-bulk actions share one keyboard-accessible sticky stack and
  do not overlap at mobile width. Scores and all explicit bulk, selection, keyboard, motion and
  accessibility contracts remain immediate and intact (`8de69ed`).
- README, product spec, technical spec and DEC-087 describe the corrected interaction. No backend,
  API, schema, dependency or build-configuration change was needed.

Acceptance criteria 1–7 passed. Focused browser coverage exercised status staging, discard,
grouped apply, partial failure, immediate score persistence, page scrolling, bounded mounted DOM,
combined-toolbar geometry and accessibility; the complete focused Triage/axe run passed 20 cases,
with 2 affected geometry/accessibility cases passing again after the final toolbar correction.

Verification after implementation freeze:

- `make check`: Ruff, Prettier, ESLint, mypy, TypeScript, OpenAPI/type consistency and project
  validation passed;
- `make test`: 559 backend and 179 frontend tests passed. The first isolated attempt exhibited the
  documented FastAPI `TestClient` stall in `test_export.py`; the prescribed outside-sandbox run
  completed the backend suite in 49.95 seconds;
- full Playwright at one worker: 103 passed and 2 intentionally skipped across 105 cases;
- `python scripts/validate_project.py` and `git diff --check` passed after the documentation/state
  closure edits.

The realistic walkthrough used a disposable copy of owner data at 390x844 with 16 entries placed
in Inbox. The browser reached the final rows with no nested overflow. Two staged choices remained
visible and Discard restored them with zero status requests. Repeating two status groups plus a
score edit produced one immediate score PATCH, then exactly two grouped bulk PATCHes only after
Apply; the successful rows left Inbox and the count became 14. No console or page error appeared,
and live application data was untouched.

There were no product or architecture deviations. Grouped Apply is deliberately not transactionally
atomic because the existing endpoint accepts one status per request; DEC-087 records the honest,
retryable partial-failure behavior. This is the final numbered sprint in plan revision 19.
