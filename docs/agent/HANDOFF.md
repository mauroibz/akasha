# Handoff — Sprint 076 closed, the request has a user; Sprint 077 gives it a session

`docs/agent/state.json` reads `project_status: "ready"`, `active_sprint: "077"`,
`active_sprint_file: "docs/sprints/077-a-password-and-a-session.md"`, `active_sprint_status:
"ready"`, `last_completed_sprint: "076"`, `plan_revision: 40`. `completed_sprints` runs `001`
through `076`. `FINAL_SPRINT` in `scripts/validate_project.py` is `82`.

**Read Sprint 076's `Outcome` and DEC-149 before 077's own file.** The proposal
([`../auth-and-multiuser-proposal.md`](../auth-and-multiuser-proposal.md) §2.2–2.3, §5.2–5.3)
is the design; DEC-146 is the plan; DEC-147 fixed the schema choices; DEC-149 records how 076
executed.

## What Sprint 076 left in the code (2026-09-09, commits `2e62032`→`e404d20`)

- **`backend/src/book_tracker/api/identity.py` is the whole identity surface.**
  `current_user(request)` reads `app.state.auth`, refuses anything but `off`, and returns
  `Principal(user_id=1, username="admin", is_admin=True)`. Sprint 077's job is to turn this
  one function's body into a session lookup and set `app.state.auth = "on"` for requests with
  no valid session — the signature, every `user: CurrentUser` route parameter and every
  service constructor stay exactly as they are.
- **Every service and repository constructor requires `user_id`.** `LibraryService`,
  `DomainRepository`, `UndoService`, `ImportService` — a missing argument is a mypy error,
  which is how the guard test and the type system keep it that way. `JobRepository.enqueue`
  keeps its optional `user_id=None` on purpose (nobody's enrichment work is nobody's, per the
  nullable column migration 0019 made); chained enrichment jobs inherit their batch's owner.
- **Undo is owner-checked:** `UndoService` raises `LookupError` for a batch that is not the
  caller's, which the route publishes as `import_batch_not_found` (404) — same body as a
  missing id. Keep it that way unless 077's 401 work needs a distinct code.
- **The enrichment handler writes no match note for an owner-less job** (the one deliberate
  076 behavior change). Do not "fix" this back to the user-1 constant — DEC-149 records why.
- The migration table is unchanged by 076; the ORM now maps `user_id` on the ledger rows and
  `jobs`, so no new columns are owed for ownership — 077's columns are `password_*` (already
  present and NULL) and session-handling only.

## The standing guard

`test_no_hardcoded_user_outside_the_resolver` greps every backend source file for a hardcoded
user. `api/identity.py` is the only exemption, and its `user_id=1` literal is pinned to the
migration's seeded row by `test_resolver_names_the_migrations_own_row`. Any new code that
needs "whose rows" must take the resolver's answer, not add an exemption to this scan.

## Verified gates at Sprint 076's close

`make check` green (mypy strict, OpenAPI contract byte-identical, validator); backend suite
**1397 passed**, frontend 305 passed; Playwright 128 passed / 2 config-skipped against a
fresh backend on a disposable data dir; benchmark before/after both "every scenario is within
budget" with unchanged query plans; DEC-025 walkthrough with two seeded users —
library/facets/insights/triage/export/import round-trip each carried only the acting user's
rows (bruno's pass through `app.dependency_overrides`, no route bypassed). Full audit trail
in Sprint 076's `Outcome` and the 2026-09-09 worklog entry.

**Running environment on handoff:** the owner's standing dev stack
(`akasha-akasha-1`) still runs the pre-identity image on :8000 — do not stop it or assume it
serves this branch's code. Sprint 076's walkthrough and Playwright backends were run on
disposable data dirs and torn down; nothing is owed to the environment. Sprint 077 needs a
working session store, so boot its own throwaway backend rather than reusing the stack.
