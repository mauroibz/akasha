# Sprint 081 — Log in once

**Status:** in_progress
**Depends on:** 080
**Roadmap revision:** 40

> Planned from [`../auth-and-multiuser-proposal.md`](../auth-and-multiuser-proposal.md) §2.6 and
> §5.4. **Accepted by the owner as DEC-146**, including its answer to §7 question 3: the trusted
> header is wanted, off by default.

## Objective

Spend the friction budget the owner asked for twice. On the tailnet, a phone that has already been
authenticated by Tailscale does not see a login form at all; everywhere else, a session lasts long
enough that logging in is an annual event; and a lost device can be signed out from another one.

## Required context

- [`../auth-and-multiuser-proposal.md`](../auth-and-multiuser-proposal.md) §2.6 (all five friction
  items), §5.4 (the alternatives, including why passkeys are costed and not scheduled), §6 risk 4.
- `docs/decisions.md` **DEC-146**.
- `docs/specs/technical-spec.md` §9 (security), §11 (operations) — both are edited by Sprint 082,
  but the *behaviour* they will describe is built here.
- `docs/operations/runbook.md` — the existing reverse-proxy guidance, which is what an operator
  will read while configuring this and which Sprint 082 rewrites.
- Sprint 077's Outcome for **the trusted-peer check built for `X-Forwarded-Proto`**. This sprint
  extends that mechanism; building a second one is a defect.
- Tailscale's own documentation for the identity headers `tailscale serve` injects. Read it at
  activation rather than trusting a header name written here — it is the one external contract in
  this plan and it is not this repository's to pin.
- Code, read fresh:
  - `backend/src/book_tracker/api/identity.py` — the resolver and its three answers.
  - `backend/src/book_tracker/api/auth.py` — sessions, and the trusted-peer helper.
  - `backend/src/book_tracker/config.py` — where the new settings go and how they are validated.
  - `frontend/src/pages/LoginPage.tsx` and `SetupPage.tsx` as Sprint 078 built them.
- Tests: `backend/tests/test_auth_api.py`, `test_sessions.py`, `test_settings.py`,
  `frontend/e2e/auth.spec.ts`.

## Current implementation baseline

To be re-read at activation. Expected: password login, a session table, a 400-day cookie set at
creation, act-as, and a login form that a password manager fills. No header authentication, no way
to list or revoke sessions from a screen.

## Deliverables

1. **Trusted-header authentication, off by default.** Three settings, validated together in
   `config.py`:
   - `AKASHA_TRUSTED_PROXY_HEADER` — the header carrying the authenticated identity;
   - `AKASHA_TRUSTED_PROXY_PEERS` — the addresses or CIDRs permitted to assert it;
   - `AKASHA_TRUSTED_HEADER_AUTOCREATE` — whether an unknown identity becomes a new user or is
     refused. **Default false**: an unknown tailnet identity is refused, not admitted.

   Setting the header without the peers list **refuses to start**, naming the risk. This is the
   single most dangerous setting in the plan and the validator, not the documentation, is what
   makes it safe.
2. **The resolver's fourth answer.** With the header configured, a request from a permitted peer
   carrying a known identity is authenticated with no cookie and no form. A request from any other
   peer has the header **stripped before anything reads it** — not ignored, stripped, so no later
   code path can accidentally trust it. Header authentication still creates a session row, so
   act-as, revocation and the audit line all keep working unchanged.
3. **Sessions refresh.** `last_seen_at` updates on use and the expiry slides forward, bounded by
   the 400-day maximum, so an actively-used session never expires under someone. Writing on every
   request is a write per request: batch it (update only when `last_seen_at` is older than some
   interval) and record the interval and the reason in the Outcome.
4. **See and revoke your own sessions.** `GET /api/auth/sessions` and
   `DELETE /api/auth/sessions/{id}`, plus *Sign out everywhere*. Each row shows when it was
   created, when it was last used, and the user agent — enough to recognise a phone you no longer
   have. Rendered in the account section Sprint 078 added.
5. **The mobile pass.** Login, setup and the account section walked on a real phone: keyboard
   types, input modes, the viewport with the keyboard open, no zoom-on-focus (16px minimum font on
   inputs), and the tap targets. Small, and it is the difference between "works on mobile" and
   "usable on mobile".
6. **No step-up prompts anywhere.** Explicitly verified rather than assumed: nothing in the
   application asks for a password a second time. Changing a password asks for the current one,
   which is the one exception and is a form field, not a prompt.

## Acceptance criteria

1. With the header and peers configured, a request from a permitted peer carrying a known identity
   reaches the library with no cookie and no login screen, and a session row exists for it
   afterwards.
2. The same header from a peer **not** in the list is stripped: the request is anonymous and gets
   the ordinary `401`. Asserted by a test that also proves the header is absent from the request
   object downstream, not merely unused.
3. With `AKASHA_TRUSTED_PROXY_HEADER` set and `AKASHA_TRUSTED_PROXY_PEERS` unset, the application
   refuses to start with a message naming the bypass it is preventing.
4. An unknown identity is refused with `403` by default; with autocreate on, it becomes a
   non-admin user with an empty library and no password.
5. Password login still works with the header configured — the two are alternatives, not
   exclusives, so an operator is never locked out by a proxy misconfiguration.
6. A session used regularly does not expire; one unused past its window does; neither exceeds 400
   days from creation.
7. The sessions list shows the current session marked as current, and revoking it signs you out;
   revoking another one takes effect on that session's next request.
8. *Sign out everywhere* revokes every session for that user including the current one, and no
   session belonging to any other user.
9. A user can only see and revoke their own sessions; another user's session id returns `404`.
10. On a phone: no input zooms the viewport on focus, every target is 44px, the keyboard shows the
    right type, and the account section is reachable and usable at 390px.
11. Zero serious axe violations on the sessions list.
12. With `AKASHA_AUTH=off`, none of the settings do anything and the routes are absent.

## Required tests (TDD)

| Behavior | Layer | File |
|---|---|---|
| A permitted peer's header authenticates and creates a session | api | `test_auth_api.py` |
| An untrusted peer's header is stripped, not just ignored | api | `test_auth_api.py` |
| Header without peers refuses to start | unit | `test_settings.py` |
| Unknown identity refused; autocreate makes a non-admin | api | `test_auth_api.py` |
| Password login still works alongside the header | api | `test_auth_api.py` |
| Refresh slides expiry, bounded at 400 days | integration | `test_sessions.py` |
| Refresh writes are batched, not one per request | integration | `test_sessions.py` |
| List shows the current session; revoking it signs out | api | `test_auth_api.py` |
| Sign out everywhere clears only this user's sessions | api | `test_auth_api.py` |
| Another user's session id is a 404 | api | `test_isolation.py` |
| The sessions list renders and revokes | component | `AccountSection.test.tsx` (new) |
| Inputs are 16px or larger and do not zoom | e2e | `auth.spec.ts` |
| Zero serious violations on the sessions list | e2e | `accessibility.spec.ts` |

## Verification

- `make check`, `make test`, `python scripts/validate_project.py`.
- `python scripts/export_openapi.py`; `npm run api:check`.
- `npx playwright test`.
- `make smoke-container` with the header configured and a peer allowlist, proving the refusal
  path and the success path against a real image.
- **Walkthrough (DEC-025):** the only walkthrough in this plan that needs the owner's real
  network. Put the container behind `tailscale serve`, configure the header and the tailnet peer,
  and open the application on a phone that is on the tailnet: it should be signed in already.
  Then open it from a device that is **not** on the tailnet and confirm it is not. Then, from the
  phone, sign out everywhere and confirm the desktop session ends. Report how many taps the first
  case took, which should be zero.

## Explicit non-scope

- **Passkeys / WebAuthn.** Costed in §5.4 at 1–1.5 sprints and deliberately not scheduled. The
  `users` table is shaped so a credential can be added beside the password later.
- **OIDC, SAML, LDAP.** Two people in a house.
- **Email, magic links, password reset by mail.** An admin resets a password (Sprint 079).
- **A native application.** The owner ruled it out; the mobile work here is the browser.
- **Rate limiting the header path.** There is no secret to guess; the peer allowlist is the
  control.

## Commit checkpoints

1. `[ADD] Trust an identity a proxy asserts, from peers we name`
2. `[MOD] Refuse to start when the header is trusted from anywhere`
3. `[MOD] Slide a session forward while it is being used`
4. `[ADD] See where you are signed in, and end it`
5. `[FIX] Stop the login inputs zooming a phone`

## Risks and decisions to surface

- **This is the sprint that can be misconfigured into a full authentication bypass.** Every
  mitigation is a mechanism rather than a sentence in a document: refusing to start without a peer
  list, stripping the header from untrusted peers rather than ignoring it, autocreate defaulting
  to off, and the warning living in `.env.example` beside the setting. If any of those four is
  dropped, the sprint is not done.
- **The header name is an external contract this repository does not control.** Read Tailscale's
  current documentation at activation. Make the header name configuration, never a constant, so a
  rename upstream is an environment change and not a release.
- **Session refresh is a write on the read path**, and SQLite has one writer. Batching is
  deliverable 3 for that reason; measure it with `scripts/benchmark_library.py` and put the number
  in the Outcome. A per-request write here would be a performance regression introduced by a
  convenience feature.
- **A proxy misconfiguration must never lock the owner out**, which is why password login stays
  live alongside the header (criterion 5). Do not add a mode that disables it.
- **The tailnet walkthrough needs the owner's own network**, and it is the second walkthrough in
  this project's history that cannot be faked with a seeded container (Sprint 065's is the first
  and is still owed). Plan for it rather than substituting a mocked header and calling it proven.

## Outcome

_Not started. On completion record delivered behavior, commands and actual results, commit IDs,
deviations/decisions, and impact on every future sprint._
