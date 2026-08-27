# Sprint 042 — One decision per Triage row

**Status:** completed
**Depends on:** 041
**Roadmap revision:** 22

## Objective

Make every Triage row present one target status and one commit action, whether that target came
from an importer or from the domain default. Inbox is the queue the owner is already viewing, not
a useful target to repeat inside every row.

## Required context

- `AGENTS.md`; `docs/agent/WORKFLOW.md`; `docs/agent/TESTING.md`.
- `docs/specs/product-spec.md` §5.1, §5.2 and §7 (import suggestions, absent suggestions and
  Triage).
- `docs/specs/technical-spec.md` §8 (window virtualization, status drafts and native row controls).
- `docs/decisions.md`: DEC-085, DEC-086 and DEC-087.
- `docs/sprints/036-import-triage-flow.md` and `docs/sprints/037-triage-page-flow.md`.
- `frontend/src/pages/TriagePage.tsx`, `frontend/src/features/library/labels.ts`,
  `frontend/src/api/library.ts`, `frontend/e2e/triage.spec.ts` and the nearest realistic Triage
  walkthrough under `frontend/e2e/scratchpad/`.

## Current implementation baseline

Observed on 2026-08-27 after importing the owner's real MyAnimeList export. Every row is persisted
as `unsorted`, and the status select therefore repeats **Inbox**. An importer suggestion is rendered
beside it as a separate chip. A book without a suggestion has no proposed destination at all.
Choosing a status stages it correctly, but committing that one-row decision requires leaving the
row for a sticky page-level toolbar. An untouched anime row whose imported status and score are
already right has no row-level way to approve it.

The domain registry already declares the missing fallback: `default_status` (`read` for books,
`owned` for albums, and the appropriate value for every later domain). Status specs already mark
Inbox as `choosable: false`. No backend, schema or API addition is needed.

## Deliverables

1. A row's status select displays its imported `suggested_status`, or the row domain's
   `default_status` when there is no suggestion. An explicit draft overrides either.
2. The row select offers only choosable destination statuses. It never offers or displays Inbox,
   because being in Triage already communicates the persisted queue state.
3. The separate suggested-status chip is removed. The select is the single target-status surface.
4. A row-level Apply action commits that row's displayed target through the existing staged bulk
   mutation. It works without requiring the owner to change the select first, so an imported anime
   decision can be approved in one click.
5. Existing multi-row staging, page-level Apply/Discard, partial-failure retry, immediate scores,
   checkbox bulk actions, keyboard navigation and window virtualization remain intact.

## Acceptance criteria

1. An anime row with `suggested_status="completed"` displays Completed in its select, displays no
   duplicate suggestion chip and leaves Triage after its row Apply succeeds.
2. A book with no suggestion displays the book domain default (Read), and can likewise leave
   Triage with one row Apply click.
3. Inbox is absent from every row status select; all choices still come from that row's domain.
4. Changing a target sends no request until either that row's Apply or the existing page-level
   Apply is used. Discard restores the importer suggestion/domain default rather than Inbox.
5. A failed row Apply keeps its chosen target visible and retryable, with the existing single error
   announcement; successful rows leave the Inbox query.
6. Mobile rows do not overflow with the added action, and the action has an accessible name that
   includes both target and title.
7. A realistic browser walkthrough exercises suggested and unsuggested rows, target override,
   discard, row Apply and page-level Apply against disposable application data.

## Required tests (TDD)

- Playwright Triage: suggested target, domain-default target, no Inbox option, no duplicate chip,
  one-click row Apply, manual staging/discard, failed row Apply and mobile geometry.
- Existing Triage keyboard, bulk, partial-failure, virtualization, motion and accessibility cases
  remain green.

## Verification

```bash
cd frontend && npm run test:e2e -- --project=chromium --workers=1 e2e/triage.spec.ts e2e/accessibility.spec.ts
make check
make test
cd frontend && npm run test:e2e -- --workers=1
```

Run the final interaction against realistic disposable data and record the observed flow in the
worklog. This sprint changes user-visible behavior, so the walkthrough gate applies.

## Explicit non-scope

- Backend/API/schema changes; changing import mappings or persisted `unsorted` semantics.
- Removing the batch convenience action for importer suggestions or changing explicit checkbox
  bulk actions.
- Changing immediate score persistence, adding Triage filters, or redesigning the Import step.
- Sprint 043's domain-contract work.

## Commit checkpoints

1. `fix(sprint-042): make every triage row one approvable decision`
2. `docs(sprint-042): close sprint and hand off`

## Risks and decisions to surface

- The displayed target is intentionally not the persisted current status. Triage is the one
  surface where every persisted status is already known to be Inbox; the selector represents the
  decision being made.
- A domain default is the only domain-neutral answer when an importer has no suggestion. Shared UI
  must not branch on books, anime or albums.
- The row remains fixed-height and window-virtualized. The Apply control must fit at 390 px without
  making the row taller or horizontally scrollable.

## Outcome

Completed 2026-08-27.

- Every row now displays one destination: explicit draft, imported suggestion, then the row
  domain's default. Only the domain's choosable statuses appear, so Inbox is neither repeated nor
  offered, and the separate suggestion chip is gone (`c99aa23`).
- A check action on the row commits the displayed target through the existing bulk endpoint. It
  works without touching the select first, retains a failed target for retry and leaves drafts on
  other rows untouched. The page-level grouped Apply/Discard path remains for several changes
  (`c99aa23`).
- Browser coverage proves anime suggestions, suggestion-less book defaults, one-click approval,
  staging without a write, discard-to-target, retry after failure, mobile geometry, domain
  vocabulary, explicit bulk actions, virtualization, motion and accessibility (`c99aa23`). README,
  product/technical specs and DEC-095 record the final contract.

Acceptance criteria 1–7 passed. Focused Playwright passed 36 cases. `make check` passed; `make test`
passed 698 backend and 189 frontend tests; full Playwright passed 105 with 2 intentional skips. The
first sandboxed `make test` stalled in `test_export.py` with the documented FastAPI TestClient
signature; the prescribed outside-sandbox run completed the backend suite in 57.58 seconds.

The realistic walkthrough used fresh disposable application data at 390×844, imported the owner's
real 81-row MyAnimeList export and 18-book Calibre library through the browser, then exercised a
99-row Inbox. Anime showed Completed from its suggestion; the Calibre book showed Read from the
book default; neither offered Inbox or overflowed. Row Apply removed each intended row, Discard
restored the default without a request, and page Apply committed a changed anime target. No console
or page errors appeared; live application data was never opened for writing. Two pre-existing
filtered-empty/bulk-copy rough edges are recorded in the worklog rather than pulled into scope.

No backend, API, schema, migration or dependency changed. Sprint 043 is the unchanged domain-contract
work originally planned as 042.
