# Handoff — Sprint 043 ready and not started

Plan revision 22. The owner-directed Triage correction is complete as Sprint 042; **Sprint 043 is
`ready` and deliberately unexecuted.** It is the domain-contract work originally planned as 042 and
renumbered without a scope change.

Work remains on branch **`sprint-038-anime`**, unpushed and **unmerged**. Sprint 043 depends on the
anime line and the Triage correction, neither of which is on `main`, so it continues here unless the
owner merges first (DEC-053).

## What Sprint 042 changed

Triage rows now show a destination rather than the persisted Inbox state: explicit draft, imported
suggestion, then the domain default. Inbox is absent from the row selector, the separate suggestion
chip is gone, and a check action at the right applies that row's displayed target. Multi-row staged
Apply/Discard and explicit checkbox bulk actions remain. DEC-095 and commit `c99aa23` carry the
contract and implementation.

Two pre-existing rough edges were visible in the realistic walkthrough and are not part of 043:

- a filtered search with no matches says `Inbox is clear` while unfiltered rows remain;
- `Accept all suggested` remains visible on a Calibre-only filtered result with no suggestion.

## What Sprint 043 is

Close the mechanical frictions the third domain hit so the fourth does not repeat them. Nothing
user-visible changes and there is no walkthrough gate. Read
`docs/sprints/043-sharpening-the-domain-contract.md` and DEC-094 in full; DEC-095 explains the only
intervening product change.

The two substantial deliverables are the allowlisting entry-value validator across PATCH/add/import
and the application-wiring tier in domain conformance. The remaining four are independent: guard
against vocabulary-freezing CHECKs, one `EntryRow` factory, document Alembic's load-bearing foreign
key silence, and record the rebuild/UI-driving recipes. The sprint file names the split point if the
first two run long.

Re-check its recorded baseline rather than trusting line numbers. Sprint 042 changed only
`TriagePage.tsx` and browser tests at runtime, so the backend facts recorded from `0f1b86e` should
still hold.

## State at this handoff

- `make check`: passed.
- `make test`: 698 backend / 189 frontend passed; the documented sandbox TestClient stall occurred
  once in `test_export.py`, then the prescribed outside-sandbox run passed.
- Playwright: 105 passed / 2 intentionally skipped; focused Triage/accessibility: 36 passed.
- Realistic walkthrough: 81 real anime + 18 real Calibre books in disposable data, mobile row flow
  passed with no console/page errors. Live application data was untouched.
- Worktree must be clean after the Sprint 042 closure commit. No push or merge was performed.
