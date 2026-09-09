# Handoff — Sprint 077 closed; Sprint 078 gives authentication a user interface

`docs/agent/state.json` reads `project_status: "ready"`, `active_sprint: "078"`,
`active_sprint_file: "docs/sprints/078-the-way-in.md"`, `active_sprint_status: "ready"`,
`last_completed_sprint: "077"`, and `plan_revision: 40`. Completed sprints run 001–077;
`FINAL_SPRINT` remains 82.

Read Sprint 077's `Outcome` and DEC-150 before implementing 078. DEC-146 is the accepted plan;
DEC-136/137, DEC-026, DEC-028 and DEC-037 govern the new screen work.

## Authentication contract now in the code

- `AKASHA_AUTH=off` remains the default. Existing routes behave as before; `/api/auth/login`,
  `/session`, `/me` and `/setup` return 404 at runtime, although all four stay in OpenAPI.
- With auth on and no credentialed user, all application/API routes return the shared
  `409 setup_required` body except health, `GET /api/auth/me`, `POST /api/auth/setup` and the SPA
  shell. Setup updates seeded user id 1 in place, preserves its library, sets the cookie and
  returns `{id, username, display_name, is_admin}`.
- With credentials present, a non-auth API request without a valid `akasha_session` cookie returns
  `401 unauthenticated`. `POST /api/auth/login` returns the same public user object and sets the
  cookie; `DELETE /api/auth/session` returns 204 and clears it.
- `GET /api/auth/me` is always safe before login in auth-on mode and returns
  `{auth: "on", authenticated, setup_required, user}`. An anonymous response has `user: null`.
- Error bodies keep the existing shape:
  `{ "error": { "code": "...", "message": "...", "details": {} } }`.
  Bad login is `unauthenticated`; repeated failures can be `login_rate_limited`; repeat setup is
  `setup_already_completed`.
- The cookie is HttpOnly, SameSite=Lax, Path=/, fixed at 400 days, and Secure only when the trusted
  request scheme or explicit setting says so. The browser stores no session token elsewhere.
- The SPA shell remains anonymous by design. FastAPI's OpenAPI/docs routes are API surfaces and
  are gated, not mistaken for shell paths.

## Seams Sprint 078 should consume, not replace

- The checked-in contract is `frontend/openapi.json`; regenerate from the backend after any
  authorized contract change. Sprint 078 should not need one.
- All six frontend API modules still call `fetch` directly. Sprint 078 owns the small shared
  `request()` wrapper and the single navigation listener described in its file.
- Keep `/login` and `/setup` outside `AppShell`. Auth-off must remain invisible, and the default
  e2e environment must remain auth off; opt the new auth spec in without adding login steps to the
  existing suite.
- `Principal.effective_user_id` remains the downstream identity seam. Do not push cookies,
  session ids or auth-mode branches into services or domain repositories.
- Session expiry is intentionally fixed even though lookup refreshes `last_seen_at`; Sprint 081
  owns sliding/batched refresh. `peer_is_trusted` in `api/auth.py` is also Sprint 081's required
  allowlist seam.

## Verified state at close

`make check` passed. `make test` passed 1,421 backend and 305 frontend tests. Playwright passed
128 with two configuration-dependent skips. `make smoke-container` passed in auth-off and auth-on
modes, including login, restart persistence and logout. The curl walkthrough claimed a realistic
pre-existing library, exercised setup/login/logout/restart, and left no disposable container,
volume or files behind. Full commands, focused evidence and scrypt measurements are in Sprint
077's `Outcome` and the 2026-09-09 worklog entry.

The owner's standing dev stack (`akasha-akasha-1`) still runs its pre-sprint image on port 8000;
do not stop it or treat it as this branch. Sprint 077 used separate exact-name disposable
containers and removed them. No account, key, paid service or irreversible owner decision is
pending.
