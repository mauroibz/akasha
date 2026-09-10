# Handoff — Sprint 081 ready: log in once

`docs/agent/state.json` records Sprint 080 completed and Sprint 081 `ready`; completed sprints run
001–080, plan revision is 40, and `FINAL_SPRINT` remains 82. Claim 081 only after the normal context
pass with:

```console
python scripts/sync_sprint_state.py --sprint 081 in_progress
```

## What Sprint 080 leaves behind

An admin can enter another person's library from People and write to it without losing the actual
signed-in identity. Migration `0021_session_acting_user` stores the nullable target on the session
with `ON DELETE SET NULL`; `Principal.effective_user_id` is the sole ownership switch. The fixed,
announced banner names the target everywhere and returns to the admin's own library in one press.
Identity switches clear frontend library queries and mutations.

Acting mode ends on logout, expiry, target deletion, either account's password change, and actual
admin demotion; ordinary profile edits preserve it. The HTTP boundary emits exactly one
`admin_acting_request` record per handled acted request with the two numeric ids, method and
templated route only. DEC-152 and Sprint 080's Outcome are the realized contract. Keep the Sprint
079 non-admin isolation inventory unchanged: acting as A still gives `404` for C's private ids.

Frozen gates: `make check` passed; `make test` passed 1,464 backend and 322 frontend tests at 90%
backend coverage; OpenAPI producer/consumer passed; full Playwright passed 137 with two skips. The
real 390px two-profile container walkthrough changed a score, assigned a shelf and deleted a bad
row in Bruno's library, then matched 49 browser requests to 49 minimal audit events. The banner was
never ambiguous. Walkthrough containers used foreground `docker run --rm` plus host-created `/tmp`
bind directories, so no named-volume start/delete cycle or volume approval was needed.

## Sprint 081 starting point

Read Sprint 080's Outcome and DEC-152, then inspect identity, auth/session storage, config, login
and account UI fresh. Session rows now include `acting_as_user_id`; session listing and revocation
must describe and operate on the actual user's sessions, not the effective target. Reuse the exact
trusted-peer matcher already protecting `X-Forwarded-Proto`; a second trust implementation is a
defect. Read current Tailscale primary documentation at activation because its header names are an
external, changeable contract.

Sprint 081 adds trusted-header auth (off by default and startup-refused without a peer allowlist),
batched sliding expiry, session listing/revocation/sign-out-everywhere, and the phone input pass.
Password login must remain available. The final walkthrough requires Mauro's real tailnet and
phone: do the disposable/container checks first, then request only the missing real-network
evidence if needed. The standing Compose install and its credentials remain out of scope unless
the owner explicitly brings them into the walkthrough.
