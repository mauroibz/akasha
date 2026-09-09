# Sprint 078 — The way in

**Status:** in_progress
**Depends on:** 077
**Roadmap revision:** 40

> Planned from [`../auth-and-multiuser-proposal.md`](../auth-and-multiuser-proposal.md) §2.3 and
> §2.6. **Accepted by the owner as DEC-146.**

## Objective

A person can log in, on a phone, without thinking about it. The login screen, the first-run setup
screen, and the 401 handling every API module needs — after this sprint a single-user install can
sit behind a password and still be the application it was.

## Required context

- [`../auth-and-multiuser-proposal.md`](../auth-and-multiuser-proposal.md) §2.3 (one screen, two
  fields, no email), §2.6 items 2 and 4 (the password-manager attributes, no step-up prompts),
  §6 risk 6.
- `docs/decisions.md` **DEC-146**, **DEC-136**/**DEC-137** (`Panel`, `PageHeader` and the seven
  cohesion rules a new screen has to obey), **DEC-026** (tokens; a new screen invents no colour),
  **DEC-028** (live regions and the `role="status"` convention), **DEC-037** (the route-chunk
  budget — the login screen is on the cold-load path and must not drag the entry chunk).
- `docs/brand/BRAND.md` — this is the first screen a person sees, and it is the only screen with
  nothing else on it.
- Sprint 077's Outcome for the four routes, the `401`/`409` bodies and the cookie as built.
- Code, read fresh:
  - `frontend/src/App.tsx` — the router, the lazy-chunk pattern, and `AppShell` wrapping
    everything. The login screen must render **outside** `AppShell`: a nav bar to five screens
    you cannot open is worse than no nav bar.
  - `frontend/src/components/AppShell.tsx` — the five `navItems` and the mobile bottom nav.
  - All six API modules under `frontend/src/api/` — `add.ts`, `exports.ts`, `health.ts`,
    `imports.ts`, `library.ts`, `shelves.ts`. Each calls `fetch` directly; **there is no shared
    client**, which is why deliverable 2 exists.
  - `frontend/src/components/ErrorBoundary.tsx` and `pages/NotFoundPage.tsx` — the existing
    failure surfaces, so a 401 does not become a third unrelated one.
- Tests: `frontend/src/pages/HomePage.test.tsx` (the component-test conventions),
  `frontend/e2e/accessibility.spec.ts` (every reachable screen owes zero serious violations),
  `frontend/e2e/console.ts` (the global stubs every e2e spec inherits).

## Current implementation baseline

To be re-read at activation. Expected: four auth routes and a working cookie from Sprint 077; six
frontend API modules calling `fetch` with no shared error handling; `AKASHA_AUTH` defaulting to
`off`, so the dev server and the whole e2e suite are unauthenticated unless a test opts in.

## Deliverables

1. **The login screen**, at `/login`, outside `AppShell`:
   - one real `<form>` with `action` and a submit button, so a phone keyboard shows *Go*;
   - `autocomplete="username"` and `autocomplete="current-password"`, `name` attributes, and
     `type="password"` — the five attributes that decide whether a password manager offers to
     fill and to save;
   - one error line for a bad password, in the existing error style, announced politely;
   - the mark, the product name, and nothing else. No "forgot password" (there is no mail), no
     "remember me" (the session is 400 days), no sign-up.
2. **The setup screen**, at `/setup`, reached only when `GET /api/auth/me` says setup is required:
   username, display name, password, and one line saying this claims the library already on this
   install. `autocomplete="new-password"`. Redirects to `/login`'s destination on success.
3. **One place that handles 401.** The six API modules get a shared `request()` helper that raises
   a typed `Unauthenticated` on `401` and `SetupRequired` on `409 setup_required`; a single
   listener turns either into a route change. This is the sprint's one refactor and it is
   deliberately small — the helper wraps `fetch`, it does not become a client library.
4. **Return to where you were.** A 401 on `/shelves/favorites` sends you to `/login` and back to
   `/shelves/favorites` after. The destination is held in router state, never in a query
   parameter — a login URL carrying a redirect target is an open-redirect shape and there is no
   reason to build one.
5. **The session in the shell.** `GET /api/auth/me` is fetched once and cached; the AppShell gains
   a small account control showing the display name with *Sign out* behind it. On mobile it goes
   in the header, **not** as a sixth item in the bottom nav — five is already the limit that fits
   at 390px.
6. **Auth-off is invisible.** With `AKASHA_AUTH=off`, `/login` and `/setup` redirect to `/`, the
   account control is absent, and no screen mentions accounts. An install that never turns auth on
   never learns it exists.

## Acceptance criteria

1. With auth on and no session, opening any address renders the login screen; a correct password
   lands on the address that was asked for.
2. A wrong password shows one error, keeps the username, clears the password, returns focus to the
   password field, and never navigates.
3. Chrome and Firefox offer to save the password after a successful login and to fill it on the
   next visit. Verified by hand in the walkthrough, because no automated test can assert it.
4. On a database with no credentialed user, every address renders the setup screen; completing it
   logs in and the library that was already there is visible immediately.
5. *Sign out* returns to the login screen and a browser back-navigation does not restore the
   library.
6. A 401 arriving mid-session — the session expired or was revoked elsewhere — routes to login
   from any screen, including one with a dialog open, without leaving the dialog on screen.
7. With `AKASHA_AUTH=off`, `/login` and `/setup` redirect to `/` and the shell shows no account
   control. The existing e2e suite runs in this mode and passes unchanged.
8. Login and setup hold at 390px with 44px targets, zero serious axe violations, and a visible
   focus ring on every control; the form is completable by keyboard alone.
9. The login chunk does not enter the entry bundle. `npm run build` reports the entry chunk within
   its existing budget (DEC-037) and the Playwright production-bundle project passes.
10. No password value is ever placed in router state, `localStorage`, `sessionStorage`, or a query
    parameter.

## Required tests (TDD)

| Behavior | Layer | File |
|---|---|---|
| Login submits, sets nothing client-side, and navigates on success | component | `LoginPage.test.tsx` (new) |
| A bad password shows one error and keeps the username | component | `LoginPage.test.tsx` (new) |
| The form carries the five password-manager attributes | component | `LoginPage.test.tsx` (new) |
| Setup posts and redirects; the claim line is present | component | `SetupPage.test.tsx` (new) |
| The shared helper raises `Unauthenticated` on 401 and `SetupRequired` on 409 | unit | `api/request.test.ts` (new) |
| A 401 from any module routes to login and remembers the destination | component | `App.test.tsx` (new) |
| Auth off redirects `/login` to `/` and hides the account control | component | `App.test.tsx` (new) |
| Sign out clears the session and returns to login | component | `AppShell.test.tsx` |
| Login, setup and a mid-session 401, end to end with auth on | e2e | `auth.spec.ts` (new) |
| Zero serious violations on login and setup | e2e | `accessibility.spec.ts` |
| Both screens at 390px with 44px targets | e2e | `auth.spec.ts` (new) |

## Verification

- `make check`, `make test`, `python scripts/validate_project.py`.
- `npx playwright test` — including the new `auth.spec.ts`, which is the first spec needing a
  backend in `on` mode. Decide and record how it gets one: a stubbed set of auth routes in the
  spec, consistent with how every other spec stubs its API, is the expected answer.
- `npm run build`; check the entry-chunk size against DEC-037's budget.
- **Walkthrough (DEC-025):** on a real phone on the tailnet, against a container with
  `AKASHA_AUTH=on`: complete setup, sign out, sign in again, and confirm the browser's password
  manager offered to save and then to fill. Then let the session persist overnight and open the
  application again in the morning without signing in. Report how many taps the whole thing took
  — that number is the sprint's actual subject.

## Explicit non-scope

- **A second user, or any user management screen.** Sprint 079.
- **The admin's view-as banner.** Sprint 080.
- **Trusted-header login.** Sprint 081. This sprint's login screen is what that one skips.
- **Password change for the signed-in user.** Sprint 079, with the rest of account management.
- Password strength meters, breach checks, "show password" toggles beyond the platform's own.

## Commit checkpoints

1. `[ADD] Handle a refused request in one place`
2. `[ADD] A screen to sign in on`
3. `[ADD] Claim the library on first run`
4. `[ADD] Return to the page that asked for a login`
5. `[ADD] Say who is signed in, and offer the way out`

## Risks and decisions to surface

- **The password-manager behaviour is the sprint's highest-value detail and the only one no test
  can assert.** It is criterion 3 and it is verified by hand in the walkthrough. Getting it wrong
  means every mobile login is typed by hand, which is precisely the friction this plan exists to
  remove.
- **The mobile bottom nav is full at five items.** The account control goes in the header. If it
  does not fit there either, the answer is a header menu, not a sixth nav item.
- **A mid-session 401 can arrive while a dialog is open** — during an import, mid-upload, with
  unsaved notes on screen. Criterion 6 covers the navigation; whether unsaved work is preserved
  across the login is a genuine product question. Recommended answer for this sprint: do not
  preserve it, and say so plainly on the login screen when arriving that way. Raise it in the
  Outcome if the walkthrough makes it feel worse than that.
- **The e2e suite is unauthenticated by default and must stay that way**, or 130 tests each gain a
  login step and the suite's runtime with it. `AKASHA_AUTH=off` in the dev server, opt-in per
  spec (§6 risk 6).

## Outcome

_Not started. On completion record delivered behavior, commands and actual results, commit IDs,
deviations/decisions, and impact on every future sprint._
