# Handoff — Sprint 081 in progress: external walkthrough remains

`docs/agent/state.json` records Sprint 081 as `in_progress`; completed sprints run 001–080 and
`FINAL_SPRINT` remains 82. Do not claim or advance another sprint.

## Frozen implementation

Trusted identity-header login reuses the configured trusted-peer matcher. Auth-on startup refuses
a header without peers; untrusted headers are stripped; unknown identities default to 403;
autocreate is explicit and produces a non-admin with no password. Valid cookies take precedence
and password login remains usable. Current Tailscale Serve documentation names
`Tailscale-User-Login`, but the header remains configurable.

Sessions refresh in daily batches to a 400-day forward horizon. Users can list and revoke their own
sessions and sign out everywhere from the responsive Account section. The actual user owns these
operations even during admin act-as. DEC-153 is the realized expiry/precedence contract.

Implementation commits: `20d2771`, `3d65463`, `e2fbe0c`, `c608c87`, `cf2731e`, `c661c9d`,
`3e365c6`, `1916e9d`, `cba775c`.

## Evidence already frozen

- `make check` passed.
- `make test` passed 1,473 backend and 325 frontend tests.
- Full Playwright passed 140 tests.
- OpenAPI export and frontend consumer check passed.
- `make smoke-container` passed the real-image startup refusal, untrusted-peer rejection,
  allowlisted known-user success/cookie and unknown-user refusal. Its single Make target owns
  disposable Docker setup and cleanup, avoiding separate volume approvals.
- The 50-entry benchmark probe reported 0.18 ms session lookup p95, zero refresh writes inside one
  day and one after it.

## Exact remaining work

1. Rerun the default 10,000-entry `scripts/benchmark_library.py` command to completion and record
   its lookup p95/write counts. The prior run was interrupted before a result; nothing is running.
2. Ask Mauro to perform the sprint's real-network walkthrough: serve the configured container with
   Tailscale, open it on a tailnet phone and observe zero-tap login, verify a non-tailnet device is
   not logged in, then sign out everywhere on the phone and verify the desktop session ends.
3. If both pass, finish the Sprint 081 Outcome/roadmap reconciliation, run the documentation-only
   closure checks, atomically mark 081 completed and 082 ready, and create the prescribed closure
   commit. If either fails, resume TDD and invalidate the affected gates normally.
