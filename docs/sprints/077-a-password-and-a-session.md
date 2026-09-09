# Sprint 077 — A password and a session

**Status:** in_progress
**Depends on:** 076
**Roadmap revision:** 40

> Planned from [`../auth-and-multiuser-proposal.md`](../auth-and-multiuser-proposal.md) §2.2, §2.3
> and §5.2–5.3. **Accepted by the owner as DEC-146.**

## Objective

`AKASHA_AUTH=on` becomes legal and means something. A user has a password, logging in creates a
revocable session, the cookie that carries it is correct on both plain-HTTP LAN and HTTPS behind a
proxy, and every other route refuses an anonymous request with a stated 401 contract. No screens
yet — this sprint is finished when `curl` can log in and the library cannot be read without it.

## Required context

- [`../auth-and-multiuser-proposal.md`](../auth-and-multiuser-proposal.md) §2.2 (tables,
  hashing, cookie policy, lifetime), §2.3 (first run), §5.2 (why stdlib scrypt), §5.3 (why a
  server-side session), §6 risks 1 and 5.
- `docs/decisions.md` **DEC-146**.
- `docs/specs/technical-spec.md` §9 (security and data safety — this sprint edits it), §7.1
  (the route contract), §4 (configuration).
- Sprint 075's Outcome for the `users` and `sessions` shapes as actually built, and Sprint 076's
  for `Principal` and the resolver.
- Code, read fresh:
  - `backend/src/book_tracker/api/identity.py` — the resolver, as Sprint 076 left it.
  - `backend/src/book_tracker/main.py:280` (`create_app`), `:319-397` (the health routes),
    `:399-404` (router registration), `:418` (the SPA catch-all). Route *order* matters here:
    the auth routes and the health routes must sit ahead of the catch-all, and the catch-all must
    keep serving the SPA shell to an anonymous browser or there is nothing to render a login on.
  - `backend/src/book_tracker/config.py` — `AKASHA_AUTH` as Sprint 075 declared it.
  - `backend/src/book_tracker/api/library.py:58-70` — the existing `ErrorDetail` shape, which the
    401 body must match rather than invent.
  - `backend/src/book_tracker/logging.py` — the redaction denylist. `password`, `token` and
    `cookie` must be in it before the first login attempt is logged.
- Tests: `backend/tests/test_library_api.py`, `test_settings.py`.

## Current implementation baseline

To be re-read at activation. Expected from Sprints 075–076: `users` and `sessions` exist with
nullable credentials on the seeded user; one resolver answers every request with user 1;
`AKASHA_AUTH` accepts only `off`.

## Deliverables

1. **Password hashing.** `hashlib.scrypt`, a per-user random salt, parameters stored alongside the
   hash so they can be raised later without invalidating every password, and
   `secrets.compare_digest` for the comparison. A small module,
   `backend/src/book_tracker/application/passwords.py`, with no dependency added to
   `pyproject.toml`.
2. **Sessions.** Create, look up by token hash, refresh `last_seen_at`, expire, and delete —
   one and all. The cookie carries a `secrets.token_urlsafe(32)`; the table stores only its
   SHA-256. A lookup that misses is indistinguishable in timing from one that finds an expired
   row.
3. **The auth routes**, on a new `backend/src/book_tracker/api/auth.py`:
   - `POST /api/auth/login` — username and password, sets the cookie, returns the user.
   - `DELETE /api/auth/session` — deletes this session and clears the cookie.
   - `GET /api/auth/me` — who am I, and is setup still required. The one route the SPA may call
     before it knows whether it is logged in.
   - `POST /api/auth/setup` — first run only: creates the first admin, claims the existing rows,
     logs them in. Refuses with `409` once any user has a password.
4. **The cookie policy.** `HttpOnly`, `SameSite=Lax`, `Path=/`, `Max-Age` 400 days, and `Secure`
   **derived from the request scheme** — set when the request arrived over HTTPS (honouring
   `X-Forwarded-Proto` only from a configured trusted proxy), unset otherwise, and forceable
   either way with `AKASHA_COOKIE_SECURE`. §6 risk 5: a `Secure` cookie on a plain-HTTP LAN
   install is an install nobody can log into.
5. **The 401 contract.** Every route except `/api/health/*`, the auth routes and the SPA shell
   returns `401` with the existing `ErrorDetail` body and code `unauthenticated` when
   `AKASHA_AUTH=on` and no valid session is present. `409 setup_required` when no user has a
   credential yet. Both go in the OpenAPI document.
6. **The resolver learns its second answer.** With `AKASHA_AUTH=on` it reads the cookie, loads the
   session, refreshes it, and returns that user's `Principal`. Nothing downstream changes.
7. **Login rate limiting.** Per-username and per-peer, in-process, a small fixed window. Enough to
   make a password guess uneconomic on a LAN; deliberately not a distributed limiter.
8. **The environment bootstrap.** `AKASHA_ADMIN_USERNAME` and `AKASHA_ADMIN_PASSWORD`, both
   optional: if set on a database with no credentialed user, the admin is created at startup and
   `POST /api/auth/setup` is never needed. Documented in `.env.example` beside the warning that
   it puts a password in a file.

## Acceptance criteria

1. With `AKASHA_AUTH=off`, every route behaves exactly as it did after Sprint 076, and the auth
   routes return `404`. The whole existing suite passes unchanged.
2. With `AKASHA_AUTH=on` and a credentialed user, `POST /api/auth/login` with the right password
   sets a cookie and a following `GET /api/entries` succeeds; with the wrong password it returns
   `401` and sets no cookie.
3. A request with no cookie, an unknown cookie, an expired session, or a session whose user was
   deleted gets `401 unauthenticated` — four distinct tests, one body.
4. `DELETE /api/auth/session` makes the same cookie stop working on the next request.
5. On a database where no user has a credential, every route returns `409 setup_required` except
   health, `GET /api/auth/me`, `POST /api/auth/setup` and the SPA shell. `POST /api/auth/setup`
   creates the admin, and the entries that existed before it are visible to that admin
   immediately.
6. `POST /api/auth/setup` on a database that already has a credentialed user returns `409` and
   creates nothing.
7. The cookie carries `Secure` for an `https` request and not for an `http` one;
   `AKASHA_COOKIE_SECURE` overrides both directions. `X-Forwarded-Proto` is honoured only from a
   configured trusted peer and ignored otherwise.
8. A password is never in a log line, a response body, an error message or the OpenAPI document.
   Asserted by a test over captured log output, not by reading the code.
9. Rate limiting refuses after the configured number of failures within the window and recovers
   after it; a correct password within the window still succeeds for a different username.
10. The SPA shell is served to an anonymous browser. Without this there is no page on which to
    render a login form in Sprint 078.

## Required tests (TDD)

| Behavior | Layer | File |
|---|---|---|
| scrypt hash verifies, rejects a wrong password, and two hashes of one password differ | unit | `test_passwords.py` (new) |
| Stored parameters allow a later cost increase without breaking old hashes | unit | `test_passwords.py` (new) |
| Session create, look up, refresh, expire, delete | integration | `test_sessions.py` (new) |
| Login sets a cookie; the wrong password does not | api | `test_auth_api.py` (new) |
| Missing / unknown / expired / orphaned cookie all give `401 unauthenticated` | api | `test_auth_api.py` (new) |
| Logout invalidates the cookie | api | `test_auth_api.py` (new) |
| `setup_required` gates every route but the four exceptions | api | `test_auth_api.py` (new) |
| Setup claims pre-existing rows for the new admin | api | `test_auth_api.py` (new) |
| Setup twice is a `409` | api | `test_auth_api.py` (new) |
| Cookie `Secure` follows the scheme, and the override wins | api | `test_auth_api.py` (new) |
| `X-Forwarded-Proto` from an untrusted peer is ignored | api | `test_auth_api.py` (new) |
| No password reaches any log record | unit | `test_logging.py` |
| Rate limiting refuses and recovers | api | `test_auth_api.py` (new) |
| `AKASHA_AUTH=off` leaves every existing behaviour intact | api | `test_library_api.py` |

## Verification

- `make check`, `make test`, `python scripts/validate_project.py`.
- `python scripts/export_openapi.py`; `npm run api:check`. The four auth routes and the `401`/`409`
  responses are contract changes and must land in `frontend/openapi.json`.
- `make smoke-container` extended with a login round-trip against the running image in `on` mode:
  refused before login, permitted after, refused after logout.
- **Walkthrough (DEC-025):** run the container with `AKASHA_AUTH=on` against a throwaway database
  and drive it with `curl` alone — setup, login, read the library, log out, be refused. Then
  restart the container and confirm the session survives the restart, because the session lives in
  the database and that is the claim.

## Explicit non-scope

- **Every screen.** No login form, no setup form, no 401 handling in the SPA. Sprint 078. A
  browser pointed at an `AKASHA_AUTH=on` install at the end of this sprint sees a shell that
  cannot fetch anything, and that is the expected state.
- **A second user.** Sprint 079 creates one; this sprint's setup route creates exactly one admin.
- **Admin privilege meaning anything.** `is_admin` is stored and not yet enforced.
- **Trusted-header authentication.** Sprint 081. The trusted-peer configuration this sprint adds
  for `X-Forwarded-Proto` is deliberately the same mechanism, so 081 extends it rather than
  inventing a second one.
- Passkeys, OIDC, email, password reset links. See the proposal's §4 and §5.4.

## Commit checkpoints

1. `[ADD] Hash a password with the standard library`
2. `[ADD] Hold a login in a revocable session`
3. `[ADD] Let a request log in, log out, and say who it is`
4. `[ADD] Refuse an anonymous request, and say how to fix it`
5. `[ADD] Create the first admin, and claim the library it already has`
6. `[MOD] Set Secure on the cookie only where it can be sent`

## Risks and decisions to surface

- **The `Secure` cookie is the most likely way to ship an install nobody can log into**, and it
  fails silently: the browser simply does not send the cookie back. Criterion 7 tests both
  directions and the container walkthrough exercises the plain-HTTP path, which is the owner's
  own LAN case.
- **`X-Forwarded-Proto` is a header a client can set.** Honouring it unconditionally would let a
  LAN client force `Secure` and lock itself out, and it is the same class of mistake as Sprint
  081's trusted-identity header. Build the trusted-peer check once, here, and reuse it there.
- **The SPA shell must stay anonymous** or Sprint 078 has nowhere to draw. It is criterion 10 for
  that reason and not as an afterthought.
- **Rate limiting is in-process and resets on restart.** Correct for a single-container LAN
  deployment and worth stating so that nobody later mistakes it for a security boundary.
- **scrypt parameters are a judgement call** — pick them by measuring on the owner's own hardware
  class (a ZimaBoard, not a workstation) and record the measurement. A login that takes two
  seconds on the target machine is a friction regression the proposal's §2.6 would not accept.

## Outcome

_Not started. On completion record delivered behavior, commands and actual results, commit IDs,
deviations/decisions, and impact on every future sprint._
