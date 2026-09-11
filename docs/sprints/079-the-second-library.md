# Sprint 079 — The second library

**Status:** completed
**Depends on:** 078
**Roadmap revision:** 40

> Planned from [`../auth-and-multiuser-proposal.md`](../auth-and-multiuser-proposal.md) §2.3, §2.4
> and §6 risk 1. **Accepted by the owner as DEC-146.**

## Objective

Two people, two libraries, one install. The admin creates the second user; each sees their own
entries, shelves, imports and insights and none of the other's; and an exhaustive isolation suite
proves it route by route rather than by inspection. This is the sprint the whole plan is for.

## Required context

- [`../auth-and-multiuser-proposal.md`](../auth-and-multiuser-proposal.md) §2.3 (why no invitation
  flow), §2.4 (the shared/private table — **this sprint is where that table becomes enforced
  behaviour**), §6 risk 1, §7 questions 1 and 2 and DEC-146's answers to them.
- `docs/decisions.md` **DEC-146**, and **DEC-065** (the library names exactly one domain — the
  user-management screen is not a library screen and does not inherit that rule).
- `docs/specs/product-spec.md` §3 (what an entry and a shelf are), §9 (the multiuser deferral this
  sprint closes).
- Sprints 075–078 Outcomes: the `users` shape, the resolver, the auth routes, the shell's account
  control.
- Code, read fresh:
  - `backend/src/book_tracker/api/identity.py` — the resolver and `Principal`.
  - `backend/src/book_tracker/api/auth.py` — the routes Sprint 077 built.
  - **Every route in the application**, because every one of them is an isolation test:
    `api/library.py` (25 routes), `api/imports.py` (8), `api/export.py` (3),
    `api/providers.py` (3). Enumerate them from the source, not from this list.
  - `backend/src/book_tracker/application/library.py` — the ten `self.user_id` filters, and
    anything that reaches an entry or a shelf by id **without** one.
  - `backend/src/book_tracker/application/undo.py` — an undo reverses a batch; after this sprint a
    batch has an owner and reversing someone else's must be impossible.
- Tests: everything under `backend/tests/` that constructs two of anything, plus
  `frontend/src/components/AppShell.test.tsx`.

## Current implementation baseline

To be re-read at activation. Expected: one admin exists, created through setup; the resolver
answers with that user; `is_admin` is stored but enforces nothing; there is no way to create a
second user.

## Deliverables

1. **Admin is enforced.** A dependency that refuses a non-admin with `403 forbidden`, applied to
   the user-management routes and nothing else. `is_admin` stops being decoration.
2. **User-management routes**, admin-only, on `api/auth.py`:
   - `GET /api/users` — the list, with entry and shelf counts so the admin can see what a user
     owns before touching them.
   - `POST /api/users` — username, display name, initial password, admin flag.
   - `PATCH /api/users/{id}` — display name, admin flag, and password reset.
   - `DELETE /api/users/{id}` — see deliverable 5.
3. **Self-service, for everyone.** `PATCH /api/auth/password` — current password, new password,
   for the signed-in user only. Changing it revokes every other session for that user and keeps
   the current one, which is the behaviour a person expects and the one that makes a shared
   password recoverable.
4. **The screens.** A *People* section inside the existing settings surface: the list, a create
   form, rename, reset password, delete. Plus *Change password* for a non-admin, which is the only
   part of it they can see. New screens obey DEC-136's seven rules and invent nothing.
5. **Deleting a user is a decision, not a cascade.** Sprint 075 set `RESTRICT` deliberately. The
   route offers exactly two outcomes, both explicit: **transfer** the user's entries, shelves and
   import ledger to another user, or **delete** them. Neither is the default and the request must
   name one. An admin cannot delete themselves, and the last admin cannot be demoted.
6. **The isolation suite.** A parametrized test that, for **every** route in the application,
   authenticates as user B and addresses user A's ids, asserting the response is `404` — not
   `403`. A `403` confirms the row exists, which leaks the one bit an id-guessing probe wants.
   The suite enumerates routes from the router at runtime, so a route added later that is not
   covered **fails the suite** rather than silently escaping it.
7. **The shared cache stays shared, provably.** The same test asserts the other half of §2.4: two
   users who add the same book get one `items` row, one cover file, and one enrichment fetch;
   user B's entry for a shared item is reachable and user A's entry for it is not.

## Acceptance criteria

1. An admin creates a second user; that user logs in and sees an empty library, no shelves, no
   imports and empty insights, on an install where the admin has a full one.
2. Each user's entries, shelves, formats, triage, insights, export and import history contain only
   their own rows. Asserted per route by the isolation suite, not by sampling.
3. Every route addressed with another user's entry id, shelf id, batch id or job id returns `404`.
   No route returns `403` for a row-ownership failure, and none returns `200`.
4. A non-admin gets `403` from every user-management route and cannot see the *People* section.
5. Two users adding the same book produce one `items` row, one cover on disk, and two entries.
6. An import run by user B creates a batch owned by B; A cannot see it, cannot undo it, and A's
   own undo does not touch it.
7. Changing a password revokes that user's other sessions and not the current one, and not any
   other user's.
8. Deleting a user with a library requires naming transfer-or-delete; transfer moves the rows and
   leaves them intact; delete removes entries, shelves and the ledger and **leaves `items`,
   covers and attachments alone** — they are the shared cache.
9. An admin cannot delete themselves; the last admin cannot be demoted. Both refuse with a stated
   message, not a 500.
10. A username collides case-insensitively and is refused with a 422 naming the field.
11. The *People* screens hold at 390px, 44px targets, zero serious axe violations.
12. With `AKASHA_AUTH=off`, none of this exists: the routes are absent and the settings section is
    not rendered.

## Required tests (TDD)

| Behavior | Layer | File |
|---|---|---|
| **Every route, as user B against user A's ids, returns 404** | api | `test_isolation.py` (new) |
| The suite fails when a route is added without coverage | api | `test_isolation.py` (new) |
| Two users, one shared item, one cover, two entries | integration | `test_isolation.py` (new) |
| Create, rename, reset password, list with counts | api | `test_users_api.py` (new) |
| A non-admin is refused every management route | api | `test_users_api.py` (new) |
| Password change revokes other sessions, keeps this one | api | `test_users_api.py` (new) |
| Delete with transfer moves rows; delete without removes them | api | `test_users_api.py` (new) |
| Deleting a user leaves items, covers and attachments | integration | `test_users_api.py` (new) |
| Self-deletion and last-admin demotion are refused | api | `test_users_api.py` (new) |
| Case-insensitive username collision is a 422 | api | `test_users_api.py` (new) |
| Import ownership and undo isolation | integration | `test_undo.py` |
| The People list, create form and delete confirmation | component | `PeoplePage.test.tsx` (new) |
| A non-admin sees only Change password | component | `PeoplePage.test.tsx` (new) |
| Two users, two libraries, end to end | e2e | `auth.spec.ts` |
| Zero serious violations on the People screens | e2e | `accessibility.spec.ts` |

## Verification

- `make check`, `make test`, `python scripts/validate_project.py`.
- `python scripts/export_openapi.py`; `npm run api:check`.
- `npx playwright test`.
- **Walkthrough (DEC-025):** on a throwaway container with `AKASHA_AUTH=on`, create a second user,
  sign in as them in a second browser profile, and build a small library — add a book the admin
  already owns, make a shelf, run an import, undo it, open insights and export. Then sign back in
  as the admin and confirm nothing of theirs moved and nothing of the second user's is visible.
  Report anything that felt like it leaked even if a test says it did not.

## Explicit non-scope

- **The admin viewing another user's library.** Sprint 080. Until then an admin's unrestricted
  access is through the database and the export, and that is deliberate sequencing: isolation is
  proven before the hole that deliberately crosses it is built.
- **Per-user settings, per-user provider budgets, per-user Calibre mounts.** DEC-146 question 4
  defers the last of these; the others are outside the proposal.
- **Sharing a shelf or a list between users.** Product spec §9; explicitly outside this plan.
- **Invitations, email, self-registration.** The admin creates users.
- More than two users. Nothing here caps the count, and nothing here is tuned beyond a handful.

## Commit checkpoints

1. `[ADD] Make an admin mean something`
2. `[ADD] Let an admin add the second person`
3. `[ADD] Change your own password, and lose your other sessions`
4. `[ADD] Decide what happens to a library when its owner leaves`
5. `[TEST] Prove every route keeps two libraries apart`

## Risks and decisions to surface

- **This is the sprint where a mistake is invisible.** A leak looks exactly like working software,
  which is why deliverable 6 enumerates routes from the router at runtime instead of from a
  hand-written list that will go stale the first time a route is added. If that reflection turns
  out to be impractical, the fallback is a hand-written list **plus** a test asserting its length
  equals the router's — never the list alone.
- **`404` rather than `403` is a deliberate choice** with a real cost: a genuine permission problem
  is harder to debug because it looks like a missing row. Accepted, because the alternative
  confirms the existence of rows to someone probing ids. Say so in the Outcome so nobody
  "fixes" it later.
- **Deleting a user is the one irreversible action in the whole plan.** Two explicit outcomes,
  neither defaulted, a confirmation that names the counts, and the nightly backup behind it.
  If the walkthrough makes it feel too easy to do by accident, make it harder before closing.
- **Attachments stay shared** (DEC-146 answer to question 1), so deleting a user does not remove
  files another user's items reference. That is criterion 8 and it follows from the shared-cache
  decision rather than from convenience — if the owner reverses that decision, this criterion and
  Sprint 075's schema both change.

## Outcome

**Completed 2026-09-10.**

1. Admin status is now enforced at the user-management boundary. An admin can list people with
   entry/shelf counts, create an account, rename it, change its admin flag, reset its password and
   explicitly transfer or delete its library. A non-admin receives `403` from every management
   route.
2. Every signed-in person can change their own password. The current session survives; their
   other sessions are revoked; other people's sessions are untouched. An admin reset revokes all
   sessions belonging to the reset account.
3. The People settings screen exposes the full management surface only to admins and Change
   password to everyone. Auth-off renders neither the route nor the section. The screen passed its
   390 px, 44 px target and zero-serious-axe checks.
4. Entries, shelves, formats, triage, insights, exports, imports, undo, attachments and item-backed
   operations are scoped to the effective user. The runtime route inventory makes every
   application route declare its isolation treatment and fails when a new route is omitted.
   Cross-user entry, shelf, batch, job and bulk-selection ids return `404`, deliberately hiding
   whether the row exists; management authorization alone uses `403`.
5. The shared cache stayed shared: two people adding the same provider record create one item,
   fetch and cover but separate entries. An item-addressed route is available only when the caller
   has their own entry for that shared item; auth-off retains the original unscoped behavior.
6. Import batches, records, effects and related jobs carry their owner through preview, commit and
   undo. Migration `0020` changes import identity to unique `(user_id, kind, fingerprint)`, so two
   people may import the same file without sharing a batch; its upgrade and downgrade are tested.
7. User removal requires an explicit `transfer` or `delete`. Transfer preserves entries, shelf
   joins and the complete import ledger; delete removes that private graph while leaving shared
   items, covers and attachments. Self-deletion, last-admin demotion, invalid targets and
   case-insensitive username collisions produce stated 409/422 responses rather than server
   errors.

Commits: `480f356` (admin/user API), `f3d7601` (isolation and migration), `8be1e99` (People and
password UI), `a3f0a65` (OpenAPI contract), `6807b99` (test formatting), `53c4e1c` (auth-off shared
item behavior), `12ee9aa` and `c0bfde3` (isolated browser fixtures), `e963455` (multi-user gate),
`310fb52` (cross-user bulk ids), and `ec43730` (migration round trip).

Verification after the implementation froze: `make check` passed; `make test` passed 1,457
backend and 320 frontend tests; the OpenAPI producer and `npm run api:check` passed; and
`npx playwright test` passed 136 with two configuration-dependent skips. Focused final evidence
also included 64 isolation/migration tests, 31 user/isolation API tests, six People/shell component
tests and 28 affected auth/accessibility browser tests. The first literal
`python scripts/export_openapi.py` invocation from the repository root could not import the src
layout package; the project-prescribed uv environment from `backend/` generated the contract and
the consumer check passed from `frontend/`. No product failure was hidden by that path correction.

DEC-025 walkthrough: a freshly built auth-on container used two independent browser contexts and
real persisted SQLite data. The admin added a private book and imported *Rayuela*, created Bruno,
and Bruno entered an empty library, imported the same *Rayuela*, added another private book,
created a private shelf, imported then undid *Ficciones*, and opened insights and export. Returning
to the still-live admin context showed only the admin's entries, shelf and import state; People
reported Bruno's two entries and one shelf. Live Open Library enrichment requests appeared in the
container log, and nothing in either context felt leaked. The final scratchpad flow passed in
12.0 seconds. It used one foreground `docker run --rm` with disposable `/tmp` bind mounts rather
than named volumes; the container and temporary directories were removed, avoiding repeated
volume lifecycle approvals.

Deviations and decisions are recorded in DEC-151. In particular, transfer refuses with `409`
instead of merging or overwriting when the target already owns the same item, shelf slug or import
fingerprint; without a conflict it moves every row intact. Migration `0020` was required because
the earlier install-wide fingerprint constraint contradicted two independent libraries. The
planned `test_undo.py` does not exist, so import/undo ownership lives with the exhaustive isolation
tests. Sprints 080–082 were reviewed: 080 extends the same inventory with the deliberate act-as
dimension; 081's session/trusted-header work is unaffected; 082 must carry migration `0020` and
these realized isolation/deletion contracts into the canonical release documentation. No future
acceptance criterion or dependency changed.
