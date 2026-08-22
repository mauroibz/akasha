# Handoff — Sprint 037 verification remains

Plan revision 19. Sprint 037 is `in_progress`; Sprints 001–036 are complete. The owner ended the
session after implementation and the realistic walkthrough but during the exhaustive gates. Nothing
was pushed, tagged, deployed or released.

## Implemented and committed

- `b556b1d`: Triage uses window/page virtualization instead of a nested 70vh vertical scroller.
  Row statuses stage locally until Apply; Discard sends nothing; Apply groups equal statuses into
  existing bulk requests and retains failed groups. Scores and explicit checkbox bulk actions remain
  immediate.
- `8de69ed`: pending-status and bulk actions share one non-overlapping sticky stack. README, product
  spec, technical spec and DEC-087 describe the corrected contract.

The worktree was clean before this handoff-only update. No backend, API, schema, dependency or build
configuration changed.

## Evidence already green

- TypeScript passed.
- Full focused Triage/axe run: 20 passed.
- Additional post-toolbar focused geometry/accessibility run: 2 passed.
- Project validator and `git diff --check` passed.
- Realistic walkthrough passed against disposable `/tmp/akasha-s37-walkthrough.RbFZRa/data` at
  390x844: 16 rows used document scroll; two statuses staged and discarded with no request; a score
  saved immediately; two repeated status choices remained until Apply, produced exactly two grouped
  bulk requests, then left Inbox at 14. No console/page errors. Live `data/` was untouched. The
  ignored runner is `frontend/e2e/scratchpad/sprint37-walkthrough.spec.ts`; screenshot is
  `/tmp/akasha-s37-walkthrough.png`. The isolated backend was stopped.

## Required next

Implementation is frozen. Run, once and in order:

1. `make check`
2. `make test` — use the documented non-sandbox execution if the known TestClient futex signature
   appears.
3. `cd frontend && npm run test:e2e -- --workers=1`

The previous attempt started the first two commands in parallel but was intentionally aborted after
11.6 seconds when the owner ended the session. It produced no usable result, no process remains, and
neither command counts. Full Playwright was not started.

If all three pass, complete the Sprint 037 Outcome and closure docs, set state back to project
`complete` with completed sprints 001–037 and null active fields, run the closure validator plus
`git diff --check`, and commit `docs(sprint-037): close sprint and hand off`. Do not rerun the
realistic walkthrough unless runtime/test code changes.
