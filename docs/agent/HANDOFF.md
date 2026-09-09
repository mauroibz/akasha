# Handoff — Sprint 078 in progress at the authentication-router RED

`docs/agent/state.json` reads `project_status: "in_progress"`, `active_sprint: "078"`,
`active_sprint_file: "docs/sprints/078-the-way-in.md"`, `active_sprint_status: "in_progress"`,
`last_completed_sprint: "077"`, and `plan_revision: 40`. Completed sprints run 001–077;
`FINAL_SPRINT` remains 82.

Read Sprint 077's `Outcome` and DEC-150 before implementing 078. DEC-146 is the accepted plan;
DEC-136/137, DEC-026, DEC-028 and DEC-037 govern the new screen work.

## Completed Sprint 078 slices

- `12d5f82 [ADD] Handle a refused request in one place`: `frontend/src/api/request.ts` recognizes
  only 401 and `409 setup_required`, emits one typed browser event, and throws typed errors. All
  calls in `add.ts`, `exports.ts`, `health.ts`, `imports.ts`, `library.ts` and `shelves.ts` use it;
  ordinary/domain-specific responses and abort signals remain untouched. Focused API tests: 14
  passed; TypeScript passed.
- `230464b [ADD] A screen to sign in on`: `api/auth.ts` calls login without the global refusal
  wrapper (a bad password belongs on the form), `AuthFrame.tsx` uses the existing mark/tokens/panel,
  and `LoginPage.tsx` implements the password-manager contract, wrong-password focus recovery,
  and safe internal return-to state. Focused login tests: 3 passed.

## Exact RED resume point

The worktree has one intentional untracked file: `frontend/src/App.test.tsx`. Preserve it. Its three
tests specify:

1. an anonymous auth-on request for `/shelves/favorites` sees login without `AppShell`;
2. auth-off `/login` returns to the ordinary library with no account surface;
3. a mid-session `AUTH_REQUIRED_EVENT` unmounts the shelf, shows the interruption sentence, and
   returns to that shelf after successful login.

`npm test -- --run src/App.test.tsx` is RED because current `App.tsx` has no exported
`AppContent`; `npm run typecheck` reports that same missing export. Implement the cached
`GET /api/auth/me` state in `api/auth.ts`, then restructure `App.tsx` so `App` supplies
QueryClient/BrowserRouter and exported `AppContent` owns gating plus the single event listener.
Clear private query/mutation cache at logout/refusal so browser back cannot reveal prior library
data. Keep return destinations as validated local router state—never a query parameter.

## Sprint 077 authentication contract underneath it

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

## Remaining Sprint 078 work

- Add the setup API/page after a focused RED: username, display name, new-password autocomplete,
  claim-library sentence, and direct authenticated return to the requested address.
- Add the cached session identity and header account control/sign-out. It belongs in the mobile
  header, never as a sixth bottom-nav item.
- Keep `/login` and `/setup` outside `AppShell`. Auth-off must remain invisible, and the default
  e2e fixture must stub `/api/auth/me` as auth-off; opt the new auth spec into auth-on without
  adding login steps to the existing suite.
- Add `auth.spec.ts`, login/setup axe cases, 390px/44px/keyboard assertions and the real
  phone/password-manager walkthrough. Then run `make check`, `make test`, full Playwright,
  `npm run build`, and project validation once the implementation freezes.
- The checked-in OpenAPI contract should not need to change.
- `Principal.effective_user_id` remains the downstream identity seam. Do not push cookies,
  session ids or auth-mode branches into services or domain repositories.
- Session expiry is intentionally fixed even though lookup refreshes `last_seen_at`; Sprint 081
  owns sliding/batched refresh. `peer_is_trusted` in `api/auth.py` is also Sprint 081's required
  allowlist seam.

## Baseline and environment

Sprint 077 closed green at 1,421 backend tests, 305 frontend tests, Playwright 128 passed / two
configuration skips, and a both-mode container smoke/walkthrough. This interrupted Sprint 078
session ran only the focused evidence recorded above; exhaustive gates have not begun.

The owner's standing dev stack (`akasha-akasha-1`) still runs its pre-sprint image on port 8000;
do not stop it or treat it as this branch. No container, account, key, paid service, runtime data,
or irreversible owner decision was created in this session.
