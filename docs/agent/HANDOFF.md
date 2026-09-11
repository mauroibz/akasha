# Handoff — the plan is complete and v2.0.0 is released

`docs/agent/state.json` reads `project_status: complete` with a null active sprint: Sprints
001–082 are all completed. **v2.0.0 shipped 2026-09-11**: PR #19 (73 commits) merged to `main`
as `c393b57`, tag `v2.0.0` pushed, the Release workflow published
`ghcr.io/mauroibz/akasha:2.0.0` (+`2.0`, `latest`), and the GitHub Release
"Akasha 2.0.0 — authentication and multiuser" is live from `release-notes-v2.0.md`. All
gates ran green on the exact merged tree. A new line of work opens only by a plan revision
(the reopened-plan mechanics are in `docs/agent/WORKFLOW.md`'s final-sprint rule and the
seeds-methodology skill's end-of-plan revision shape).

## What 2.0.0 is, in one paragraph

Authentication and multiuser, off by default. Turn `AKASHA_AUTH=on` and a first-run setup screen
creates the admin who claims the existing library; each further account gets its own private
library (entries, shelves, imports, exports, triage scoped; items and covers a shared cache);
sessions last 400 days and slide while used, are listed and revocable per device; an admin can
act inside another library behind an unmissable banner with one audit event per request;
`tailscale serve` can additionally assert identities through a peer-allowlisted header with
zero-tap login. The exposure rule everywhere: no internet-reachable proxy, DNS or port forward
unless auth is on, TLS terminates in front, and the cookie is `Secure`. The four version
surfaces say `2.0.0`; the upgrade is `docker compose pull && up -d` with no action otherwise.

## Owner actions left (all optional, nothing is blocked on them)

1. **The release**, whenever wanted: tag `v2.0.0` on the merged main, push, watch the Release
   workflow, publish the GitHub Release from `docs/operations/release-notes-v2.0.md`, then
   upgrade the ZimaBoard (`AKASHA_VERSION=2.0.0`). With auth left off the board's upgrade
   changes nothing visible. Turning auth on is `docs/operations/runbook.md`'s
   "Turning authentication on" — proven end to end by Sprint 082's upgrade rehearsal on a copy of
   the board's own database.
2. **DEC-154's residual proof**, when Tailscale lands on the board: phone on the tailnet opens
   signed-in; a non-tailnet device does not; sign-out-everywhere ends the desktop session. Record
   it in the worklog or a superseding DEC.

## Known and left, in the order they are likely to bite

1. **Contended insights at 10,000 entries** (DEC-154/DEC-155): `creators/count` 575.4 ms,
   `creators/score` 594.9 ms, `publisher/count` 1234.8 ms p95 under 200 queued jobs — a scale
   never measured before this plan's close; the spec budget binds the first library page (147.8
   ms contended, within budget). A future sprint decides whether insights gets its own budget.
2. **The board still runs image 1.8.0** (82 entries, almost all `unsorted`, no users table),
   bound to its LAN IP with ZeroTier unable to reach it; the upgrade is owner action 1.
3. The dev machine's standing `akasha-akasha-1` (127.0.0.1:8000) is the owner's local
   081-branch-era build; a `local-081` image also exists locally. Both are prunable once
   `v2.0.0` is published and the board upgraded.
4. The e2e/browser suites are the only automated guardrails on the UI contracts; nothing is
   scheduled after this close, so a regression found in use becomes a plan revision, not a
   sprint.
