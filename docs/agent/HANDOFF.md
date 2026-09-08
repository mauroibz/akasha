# Handoff — Sprint 075 closed, the request gets its user in Sprint 076

`docs/agent/state.json` reads `project_status: "ready"`, `active_sprint: "076"`,
`active_sprint_file: "docs/sprints/076-the-request-has-a-user.md"`, `active_sprint_status:
"ready"`, `last_completed_sprint: "075"`, `plan_revision: 40`. `completed_sprints` runs `001`
through `075`. `FINAL_SPRINT` in `scripts/validate_project.py` is `82`.

**Read [`../auth-and-multiuser-proposal.md`](../auth-and-multiuser-proposal.md) and DEC-146 before
Sprint 076's own file.** The proposal is the design; DEC-147 is what Sprint 075 actually decided
inside it.

## What Sprint 075 left in the schema (2026-09-08, commits `2cab02e`→`01b717a`,
## seed rename `bd6ae67`)

- Migration head is `0019_ownership_on_the_import_ledger`, three revisions added
  (`0017` `users` + `sessions`, `0018` `entries`/`shelves` foreign keys via rebuild,
  `0019` ownership on the import ledger and `jobs`).
- Exactly one user exists: id 1, username `admin`, admin, credentials NULL
  (seeded as `owner` on close day and renamed to `admin` the same day, taking
  the in-place re-migration DEC-147 priced; see its revision note).
- Every `user_id` column that existed keeps `NOT NULL` + `server_default "1"` —
  that default is still what the unchanged code paths write with, and it is now a real
  reference. `jobs.user_id` alone is nullable (nobody's enrichment work); Sprint 076's
  resolver is what starts writing it.
- `AKASHA_AUTH` exists on `Settings` and accepts only `off`, refusing anything else
  at startup with a message naming Sprint 077. Nothing reads it yet.

## Sprint 076's three load-bearing facts

1. **24 construction sites across 8 files take a `user_id`, almost all as literal `1` or
   a defaulted parameter.** Method: grep `user_id=1` and `user_id: int = 1` across
   `backend/src/` and replace with the resolver's answer. No route parses identity yet —
   077 does that; 076 only makes the plumbing run one way.
2. **One known defect is scheduled here, not deferred:**
   `backend/src/book_tracker/application/export.py:248` (`iter_entries`) walks every
   entry row with no `WHERE user_id`. Harmless today (exactly one user); a data leak the
   day Sprint 079 creates a second. Fix in 076, alongside the scoping.
3. **The gate is the proof that nothing user-visible moved:** the whole existing suite
   (1382 backend, 305 frontend, e2e 128 passed / 2 config-skipped, exit 0 — 075 left
   it clean) plus a guard test asserting
   no `user_id` literal survives outside the resolver, per DEC-146. Edit the listed
   files, edit the tests only where a satisfying "no literal" guard requires, keep the
   migration table out of scope — no schema line in this sprint.

Two migration tests used to be pinned to head — they enumerated every revision
after the pinned fixture as literal lists, so each migration had to update them
(0016 did, 0017–0019 did: commits `2cab02e`, `10deb80`, `408b5c6`). That
obligation was retired post-closure on 2026-09-08 (DEC-148): both tests now derive
the pending list via `revision_chain_from_files()` in `migrations.py`, and two new
tests cross-check that chain against Alembic's own graph and verify the numeric
sequencing. No per-sprint migration-list edits are needed anymore.

## Verified gates at close

`make check` green; `make test` — backend 1382, frontend 305; Playwright e2e 128 passed,
2 config-skipped, exit 0; `make smoke-container` end-to-end; an Alembic upgrade/downgrade
drill on the real `backend/tests/fixtures/backup-v1` fixture sqlite; and a DEC-025
walkthrough on a container against a seeded-0016 throwaway volume — pre-migration
backup written, all three migrations run, a Goodreads preview→commit→undo round-trip
with every owned row at `user_id = 1`, the library rendering in Chromium, and
`/openapi.json` unchanged at 1.8.0. Full audit trail in Sprint 075's `Outcome`
section and the 2026-09-08 worklog entry.

**Running environment on handoff:** the owner's standing dev stack
(`akasha-akasha-1` from `compose.yaml`/`compose.build.yaml`) has been up since
before Sprint 075 started and still runs the pre-identity image at 8000 — do not
stop it or assume it serves this branch's code; Sprint 076 is backend-only and
needs no container, and any walkthrough in 077+ should build its own throwaway
stack (the 075 walkthrough stack and volumes were torn down at close; residue
checked clean).
