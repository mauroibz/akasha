# Sprint 080 — The admin sees everything

**Status:** completed
**Depends on:** 079
**Roadmap revision:** 40

> Planned from [`../auth-and-multiuser-proposal.md`](../auth-and-multiuser-proposal.md) §2.5.
> **Accepted by the owner as DEC-146**, including its answer to §7 question 2: view-as can write.

## Objective

*"Assume admin has unrestricted access to the data."* An admin opens another user's library, sees
it whole, can fix what is wrong in it, and can never be confused about whose library is on screen.
One resolver branch and one banner — the sprint is small because Sprint 076 made it so.

## Required context

- [`../auth-and-multiuser-proposal.md`](../auth-and-multiuser-proposal.md) §2.5, §7 question 2.
- `docs/decisions.md` **DEC-146** — the owner's answer that view-as writes rather than reads,
  because a read-only mode cannot fix the mistake it was opened to investigate.
- `docs/specs/technical-spec.md` §11 (structured logging: this sprint adds a correlation field
  and must not add a way to log a note or a password).
- Sprint 076's Outcome for `Principal` and its unused `acting_as` field — **this sprint is what
  that field was reserved for**, and no other sprint may have filled it.
- Sprint 079's Outcome for the isolation suite, which this sprint deliberately punches one hole
  through and must therefore extend rather than weaken.
- Code, read fresh:
  - `backend/src/book_tracker/api/identity.py` — the resolver, and the shape of `Principal`.
  - `backend/tests/test_isolation.py` — as Sprint 079 left it. Every assertion in it stays true
    for a non-admin; the suite gains an admin dimension rather than losing a case.
  - `frontend/src/components/AppShell.tsx` — the account control Sprint 078 added, which is where
    the banner and the way out live.
  - `backend/src/book_tracker/logging.py` — the redaction chain the audit line passes through.
- Tests: `backend/tests/test_isolation.py`, `test_users_api.py`,
  `frontend/src/components/AppShell.test.tsx`, `frontend/e2e/auth.spec.ts`.

## Current implementation baseline

To be re-read at activation. Expected: two users; `Principal.acting_as` present and always null;
every route scoped to the signed-in user and proven so by the isolation suite; an admin with no
way to see another library except through the database.

## Deliverables

1. **`POST /api/auth/act-as/{user_id}` and `DELETE /api/auth/act-as`.** Admin-only. The first
   records on the *session* that this admin is acting as another user; the second clears it.
   Recorded on the session row, not in a cookie the client controls, and not as a second login —
   the admin's own identity is never lost and never impersonated.
2. **The resolver's third answer.** When the session carries an `acting_as`, `Principal` returns
   the target's `user_id` with the admin's own id kept beside it. Every downstream service already
   takes the id, so this is one branch and no route changes.
3. **A banner nobody can miss.** Persistent, above everything, on every screen, naming whose
   library is on view and carrying one control to leave. It is not a toast, it is not dismissible,
   and it does not scroll away. Present on mobile at 390px without stealing a nav row.
4. **`GET /api/auth/me` says so.** The response carries the acting-as target, so the shell knows
   to draw the banner on first paint rather than after a second request.
5. **Every acting-as request is logged.** One structured line per request carrying the admin's id,
   the target's id, the method and the route — never a body, never a note, never a query string
   that might contain one. It goes through the existing redaction chain and a test proves nothing
   personal reaches it.
6. **The isolation suite gains a dimension.** It now runs three ways: user B against A's ids
   (`404`, unchanged); a *non-admin* attempting `act-as` (`403`); and an admin acting as A, whose
   requests against A's ids succeed and whose requests against a *third* user's ids still return
   `404`. Acting as one person is not acting as everyone.
7. **Acting-as ends when it should.** It is cleared by signing out, by the admin's session
   expiring, and by the target user being deleted. It does not survive a password change on either
   account.

## Acceptance criteria

1. An admin selects a user from *People*, and the library, shelves, insights, triage, import
   history and export are that user's, whole.
2. The banner names the user, is visible on every screen including dialogs and the detail page,
   and one press returns the admin to their own library.
3. An admin acting as another user can create, edit and delete entries and shelves in that
   library, and the changes belong to the target user, not to the admin.
4. An admin acting as user A addressing user C's ids gets `404`.
5. A non-admin gets `403` from both act-as routes.
6. Signing out clears acting-as; signing back in starts in the admin's own library.
7. Deleting the user being acted as ends the mode without a 500 on the next request.
8. Every request made while acting as someone produces exactly one audit line carrying both ids
   and no personal content. Asserted against captured log output.
9. The whole of Sprint 079's isolation suite still passes for non-admin users, unchanged.
10. With `AKASHA_AUTH=off`, the routes are absent and the banner cannot appear.
11. The banner holds at 390px, has a 44px target, zero serious axe violations, and is announced to
    a screen reader when it appears rather than only being visible.

## Required tests (TDD)

| Behavior | Layer | File |
|---|---|---|
| Act-as sets and clears on the session row | integration | `test_users_api.py` |
| The resolver returns the target's id and keeps the admin's | unit | `test_identity.py` |
| A non-admin is refused both routes | api | `test_users_api.py` |
| Admin acting as A can read and write A's library | api | `test_isolation.py` |
| A write while acting belongs to A, not the admin | integration | `test_isolation.py` |
| Admin acting as A still gets 404 for C's ids | api | `test_isolation.py` |
| Sign-out, session expiry and target deletion all clear it | api | `test_users_api.py` |
| One audit line per acting request, with no personal content | unit | `test_logging.py` |
| `GET /api/auth/me` carries the target on first call | api | `test_auth_api.py` |
| The banner renders, names the user, and leaves | component | `AppShell.test.tsx` |
| The banner is announced, not just shown | component | `AppShell.test.tsx` |
| Enter, act, edit, leave, end to end | e2e | `auth.spec.ts` |
| Zero serious violations with the banner up | e2e | `accessibility.spec.ts` |

## Verification

- `make check`, `make test`, `python scripts/validate_project.py`.
- `python scripts/export_openapi.py`; `npm run api:check`.
- `npx playwright test`.
- **Walkthrough (DEC-025):** as the admin on a container with two real libraries, enter the second
  user's library, fix something in it (change a score, move an entry to a shelf, delete a
  mis-imported row), leave, and confirm from the second user's own session that the change is
  there and belongs to them. Then check the log: exactly the requests you made, no note text, no
  cookie. Report whether the banner was ever ambiguous, because that is the whole safety property.

## Explicit non-scope

- **Acting as an admin.** An admin may act as any user including another admin; nothing here grants
  more privilege than the admin already has, and no escalation path is introduced.
- **A per-user audit log the users themselves can read.** The structured log is the record.
- **Undo of an admin's changes as a separate concept.** An edit made while acting is an ordinary
  edit and the import undo ledger already covers imports.
- **Sharing, public links, or any read path that is not an authenticated admin.** Product spec §9.
- **A "recently acted as" list or shortcuts.** Two users.

## Commit checkpoints

1. `[ADD] Let an admin open someone else's library`
2. `[MOD] Teach the resolver its third answer`
3. `[ADD] Say whose library is on screen, and never stop saying it`
4. `[ADD] Record every request made on someone else's behalf`
5. `[TEST] Prove acting as one person is not acting as everyone`

## Risks and decisions to surface

- **This sprint deliberately punches a hole through Sprint 079's isolation.** The mitigation is
  that the hole is one branch in one resolver, admin-gated, session-recorded, logged, and covered
  by the same suite that proves the wall. If the isolation suite has to *lose* a case to make this
  work, the design is wrong — it gains a dimension instead (deliverable 6).
- **The banner is the safety property, not a decoration.** An admin who forgets whose library they
  are in will eventually delete the wrong thing. Not dismissible, not scrolled away, present in
  dialogs. If the walkthrough finds any screen where it is ambiguous, that is a blocking defect.
- **Acting-as lives on the session row, never in a cookie.** A client-controlled acting-as value
  would be a privilege-escalation primitive handed to the browser.
- **Writes while acting belong to the target.** That is DEC-146's answer and it is the useful
  behaviour, but it means the log is the only record that the admin, not the user, made a change.
  Criterion 8 is what makes that acceptable; do not treat the audit line as optional polish.

## Outcome

Completed 2026-09-10. An administrator can now enter another person's complete library from
People, read and write it through the existing effective-user seam, and return to their own
library in one action without ever replacing the signed-in identity.

- **Delivered.** Migration `0021` stores a nullable acting target on the server-side session with
  `ON DELETE SET NULL`. The admin-only start/stop routes and `/api/auth/me` target response drive a
  fixed, announced banner on every route. Changing identities clears cached library queries and
  mutations. Logout, expiry, target deletion, either account's password change, and actual admin
  demotion end the mode; an ordinary profile edit does not. Every handled acted request emits one
  minimal audit event with the two ids, method and templated route only.
- **Isolation proof.** The unchanged route inventory still proves user B receives `404` for A's
  private ids. Added cases prove non-admin act-as is `403`; an admin acting as A can read, create,
  edit and delete A's entries and shelves with ownership stamped to A; C's ids remain `404`.
- **TDD and focused verification.** Act-as API, resolver, lifecycle, migration, audit and
  isolation tests were driven red then green. Final focused runs passed 39 user/isolation tests,
  nine identity/session/logging tests and the `0021` migration round trip. UI/App focused tests
  passed 12; the affected auth/accessibility Chromium run passed 29. OpenAPI export and its
  frontend consumer check passed.
- **Exhaustive verification after implementation freeze.** `make check` passed, including project
  validation and the OpenAPI drift checks. `make test` passed 1,464 backend tests at 90% coverage
  and 322 frontend tests. `npx playwright test` passed 137 with two configuration-dependent skips.
  The release image built successfully as `akasha-s080-walkthrough-20260910`.
- **DEC-025 walkthrough.** At 390px, separate admin and Bruno browser profiles held distinct real
  libraries. While the banner stayed fixed and unambiguous over the library, detail, edit/delete
  dialogs, shelves, insights, triage and export, the admin changed Bruno's score, assigned Bruno's
  book to Bruno's shelf and deleted Bruno's mis-imported row. One press restored the admin's own
  library; Bruno's still-authenticated profile then showed all three changes. The browser recorded
  49 acted API requests and the foreground container emitted exactly 49 `1 → 2` audit events with
  one stable field set; Bruno's private note and cookie content were absent. Disposable `/tmp`
  bind mounts and `docker run --rm` replaced named volumes, and all temporary directories were
  removed afterward.
- **Commits.** `5d9e905` added the session/API/resolver/audit behavior; `b6cd40d` fixed lifecycle
  cleanup and the legacy async test-client stall; `bbfe4d6` pinned ordinary profile edits;
  `6cbba42` added the banner, cache boundary, People action, OpenAPI contract and browser coverage.
- **Deviations and decisions.** DEC-152 records migration `0021`, the fixed banner/cache boundary
  and the post-request audit shape. A prerequisite test-harness defect (a synchronous Starlette
  `TestClient` nested in an async test) was converted to `httpx.AsyncClient`; product behavior was
  unchanged. The first walkthrough assertion used an exact-text locator that missed visibly
  rendered shelf text; its trace and database both showed the assignment, so the selector was
  corrected to the shelf's accessible remove control and the entire walkthrough was rerun against
  fresh data. No acceptance criterion was reduced.
- **Future impact.** Sprint 081 remains correctly scoped: it operates on and revokes the actual
  administrator session while inheriting act-as unchanged. Sprint 082 must include migration
  `0021`, the two routes, banner and minimal audit event in its canonical auth documentation; its
  acceptance criteria and dependency remain valid.
