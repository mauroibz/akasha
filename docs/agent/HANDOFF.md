# Handoff — Sprint 082 complete except one owner approval; then close the plan

`docs/agent/state.json` records Sprint 082 as `in_progress` — the last sprint (`FINAL_SPRINT` 82).
Completed sprints run 001–081. **Every deliverable, test and gate is done and green. The only
missing piece is one line in `AGENTS.md`**, which the agent platform refuses to write without the
owner's consent (two consent prompts timed out unanswered).

## The one remaining edit

`AGENTS.md` line 137 currently reads:

```
- v1 has no auth and must remain LAN-only.
```

It must become (the sprint's deliverable 1 — the invariant a future agent is held to, rewritten
narrower rather than deleted):

```
- The exposure rule: no internet-reachable proxy, DNS or port forward unless `AKASHA_AUTH=on`, TLS terminates in front, and the session cookie is `Secure`. With `AKASHA_AUTH=off` (the default) the application has no authentication and must remain on a trusted LAN — overlay networks included (see the compose warning).
```

Once the owner approves that line (or edits it themselves), the five-minute closure is:
the AC1 phrase re-sweep (`grep -rn 'no auth'` over current docs, expecting only dated history),
`python scripts/sync_sprint_state.py --sprint 082 completed` (no successor — the project goes
`complete` with a null active sprint per WORKFLOW.md's final-sprint rule), a short worklog entry,
this file rewritten, `python scripts/validate_project.py`, `git diff --check`, and the
`[DOCS] Close sprint 082 — the plan is complete` commit. No runtime code, tests or gates are
affected by that line; the frozen tree's evidence stands.

## What Sprint 082 delivered (all verified)

- Exposure rule rewritten everywhere current: both specs, runbook, README, `.env.example`,
  `compose.yaml` (header + label), `SECURITY.md` (threat model for both modes; auth and
  cross-user isolation in scope when on).
- Specs canonical for 075–081: product §9 "Delivered" paragraph, §10 row 7 resolved, §6 route
  block complete; technical §5.1 all fifteen tables (`provider_usage` added), sessions table
  carries DEC-153's sliding horizon, §9 owns cookie policy + trusted header + allowlist + the
  exposure rule, §12 marks auth delivered.
- Runbook: "Turning authentication on" (setup claims the existing library; password loss; proxy
  lockout; sessions; the unsorted-hidden expectation) and "Running behind `tailscale serve`"
  (three settings, loopback bind, header name is Tailscale's contract).
- `scripts/validate_project.py` now gates the four version surfaces on every `make check`
  (DEC-145's ask), TDD'd in `backend/tests/test_validate_project.py`; `.env.example`↔`Settings`
  coverage pinned both directions (found and documented the missing
  `AKASHA_PROVIDER_DAILY_LIMITS`); documented-route-set test added.
- Version surfaces at `2.0.0`, contract regenerated; smoke gate extended with the session
  list/revoke surface and green end to end; `release-notes-v2.0.md` (deviations included);
  `publishing-images.md` gained the missing GitHub Release step.
- Gates: `make check`; backend 1,483 passed / 90%; frontend 325; Playwright 138 + 2 skips;
  OpenAPI export + consumer check; `make smoke-container`. Walkthrough = upgrade rehearsal on a
  copy of the real production DB (82 entries, 0016→0021 behind the pre-migration backup, library
  byte-for-byte, admin claims it, second user isolated; source untouched).

## Owner actions after closure

1. The AGENTS.md line above (approval or self-edit).
2. The release itself, whenever wanted: tag `v2.0.0`, push, watch the Release workflow, publish
   the GitHub Release from `docs/operations/release-notes-v2.0.md`, then upgrade the ZimaBoard
   (`AKASHA_VERSION=2.0.0`, `docker compose pull && up -d`) — no action needed for auth to stay
   off; turning it on is the runbook section.
3. Optional, whenever Tailscale lands on the board: the DEC-154 residual proof (phone on the
   tailnet opens signed-in; non-tailnet device does not; sign-out-everywhere ends the desktop
   session).

## Known and left, in the order they are likely to bite

1. The AGENTS.md line (above) — the only blocker to `project_status: complete`.
2. Contended insights at 10,000 entries (DEC-154/DEC-155: worst `publisher/count` 1234.8 ms p95
   under 200 queued jobs) — a fresh-scale finding, unowned by a sprint until the owner schedules
   one.
3. The board still runs image 1.8.0 with no auth (its ZeroTier overlay cannot reach the bound
   port); upgrading is the owner's release action.
4. The dev machine's standing `akasha-akasha-1` container is the owner's local 081-branch build;
   a `local-081` image (pre-2.0.0-bump) exists locally and can be pruned once 2.0.0 is tagged.
