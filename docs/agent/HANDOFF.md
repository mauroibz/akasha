# Handoff — Sprint 080 ready: the admin sees everything

`docs/agent/state.json` records Sprint 079 completed and Sprint 080 `ready`; completed sprints run
001–079, plan revision remains 40, and `FINAL_SPRINT` remains 82. Claim 080 only after the normal
context pass with:

```console
python scripts/sync_sprint_state.py --sprint 080 in_progress
```

## What Sprint 079 leaves behind

Two authenticated people now have isolated entries, shelves, imports, undo, insights and exports
over a shared item/cover/attachment cache. Admin-only user management and self-service password
change are shipped in the People settings surface. Private ownership misses return `404`; a
non-admin crossing the management boundary receives `403`. User deletion requires explicit
transfer or delete, and a transfer conflict refuses atomically rather than merging data. DEC-151
and Sprint 079's Outcome are the realized contract.

Migration `0020_user_scoped_import_fingerprints` makes import replay identity unique per user.
The exhaustive inventory in `backend/tests/test_isolation.py` derives application routes from the
router, requires each route to declare an isolation treatment, and probes URL ids plus ids inside
bulk bodies. Preserve those cases. Item-addressed routes require the effective user to own an
entry for the shared item when auth is on; auth-off remains unscoped.

Frozen gates: `make check` passed; `make test` passed 1,457 backend and 320 frontend tests; the
OpenAPI producer/consumer passed; Playwright passed 136 with two configuration skips. The real
two-browser container walkthrough passed, including same-file imports, private shelves,
import/undo, insights and export, with no observed leak. It used a foreground `docker run --rm`
and disposable `/tmp` bind mounts rather than named volumes; this is the low-approval pattern to
reuse for throwaway walkthroughs.

## Sprint 080 starting point

Read the Sprint 079 Outcome and DEC-151, then inspect `identity.py`, the isolation inventory,
People/API code, AppShell and logging fresh. `Principal.acting_as` still exists and is null. Sprint
080 records act-as on the admin's session, changes the resolver's effective answer, adds the
unmissable persistent banner, and emits exactly one redacted structured audit line per acted
request. The existing isolation suite must gain an admin dimension; no non-admin assertion may be
removed or relaxed. Acting as one user must still return `404` for a third user's ids.

The owner's standing Compose install remains out of scope for destructive development checks. Use
isolated temporary data and profiles; do not request or record the owner's password.
