# Handoff — Sprint 079 ready: the second library

`docs/agent/state.json` reads `project_status: "ready"`, `active_sprint: "079"`,
`active_sprint_file: "docs/sprints/079-the-second-library.md"`, `active_sprint_status: "ready"`,
`last_completed_sprint: "078"`, and `plan_revision: 40`. Completed sprints run 001–078;
`FINAL_SPRINT` remains 82. Claim 079 only after the normal context pass with:

```console
python scripts/sync_sprint_state.py --sprint 079 in_progress
```

## What Sprint 078 leaves behind

The frontend now has a cached authentication coordinator, standalone login/setup routes, shared
typed 401/setup-required handling, safe router-state return destinations, private-cache clearing,
and an account/sign-out control. Auth-off remains invisible. The implementation commits are
`12d5f82`, `230464b`, `59fed62`, `969e55f`, `c10a3e2`, `71dc706`, and `afea4fb`; the Sprint 078
Outcome and final worklog carry the acceptance evidence and deviations.

Frozen gates: `make check` passed; `make test` passed 1,421 backend and 318 frontend tests;
Playwright passed 134 with two configuration skips; and the production build passed with an
88.10 kB entry chunk. The owner confirmed the real-phone/tailnet Chrome and Firefox password
save/fill plus overnight-session walkthrough. No backend/OpenAPI contract or future-sprint plan
changed.

## Sprint 079 starting point

Read Sprints 075–078 Outcomes and every 079 Required-context document/code path fresh. The sprint
adds admin-only user management, self-service password change, explicit transfer-or-delete
semantics and the exhaustive route-enumerating isolation suite. Its highest-risk rule is that a
cross-user object lookup returns `404`, while a non-admin calling a management route returns
`403`; do not blur those cases. User deletion is irreversible and must never default to either
transfer or delete. `items`, covers and attachments remain the shared cache.

The owner's standing Compose install now runs the current branch with `AKASHA_AUTH=on` against the
owner's persistent data volumes and contains the credentialed admin created during the walkthrough.
Do not use it for Sprint 079 development or destructive user-management tests; use isolated
temporary data, backups and browser profiles. Do not record or request the owner's password.
