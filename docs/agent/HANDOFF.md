# Handoff — Sprint 082 active: Two point oh

`docs/agent/state.json` records Sprint 082 as the active sprint (`ready`); completed sprints run
001–081 and `FINAL_SPRINT` remains 82. Sprint 081 closed 2026-09-11 with the owner waiving its
real-tailnet walkthrough (DEC-154) — do not reopen 081; read its Outcome before touching the
trusted-header code.

## What Sprint 081 left behind

- Trusted identity-header login (off by default, peer-allowlist-gated), daily-batched sliding
  400-day sessions, self-service session listing/revocation/sign-out-everywhere, and the mobile
  pass. Commits `20d2771`..`cba775c`, contracts in DEC-153.
- The 10,000-entry benchmark completed: lookup p95 0.09 ms, zero refresh writes inside the daily
  interval, one after. First library page contended p95 147.8 ms (budget 500 ms).
- **Walkthrough NOT RUN, owner-waived (DEC-154).** The residual proof — the owner putting the
  container behind Tailscale Serve and observing zero-tap login, non-tailnet rejection, and
  sign-out-everywhere ending the desktop session — lands at the first real 2.0.0 deployment with
  the header configured. Neither the workstation nor the ZimaBoard runs tailscaled today; the
  board's overlay is ZeroTier. The smoke gate already proves Akasha's half (startup refusal,
  untrusted-peer stripping, allowlisted identity admitted with a cookie, unknown identity 403).

## Known and left, in the order they are likely to bite

1. **DEC-154 residual proof** — when the owner deploys 2.0.0 with `AKASHA_TRUSTED_PROXY_HEADER`
   set, that session doubles as the waived walkthrough; record taps observed, non-tailnet
   rejection, and sign-out-everywhere in the worklog or a superseding DEC.
2. **Contended insights at 10k entries** — `creators/count` 575.4 ms, `creators/score` 594.9 ms,
   `publisher/count` 1234.8 ms p95 under 200 queued jobs: over the 500 ms convention at a scale
   never measured before, on a path 081 did not touch (spec budget binds the first library page).
   Recorded in DEC-154; a future sprint decides whether insights get its own budget/measurement.
3. **The board (192.168.100.240) still runs image 1.8.0** bound to the LAN IP; the working
   deployment has no users, no auth, no sessions yet. Upgrading it is the owner's decision at
   2.0.0 release time (Sprint 082 territory), not something a sprint does unasked.
4. The dev machine's `akasha-akasha-1` (127.0.0.1:8000) is the owner's local instance of the
   auth branch (built 2026-09-10, pre-081 code — it predates the session routes). If a future
   session needs current-code container behavior, rebuild rather than reuse it; a `local-081`
   image from this branch already exists (built 2026-09-11).

## Sprint 082 in one paragraph

Rewrite the exposure rule across nine files (auth exists; the rule narrows rather than deletes),
make both specs' auth sections canonical, turn the runbook's reverse-proxy section into the
followed Tailscale/LAN guidance, reconfirm Sprint 077's both-mode smoke gate against the release
image, and surface `2.0.0` together (version bump, release notes, image tag). Its file:
`docs/sprints/082-two-point-oh.md`.
