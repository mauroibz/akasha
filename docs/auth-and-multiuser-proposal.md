# Two people, one install: authentication and multiuser

**Status: proposal.** Written 2026-09-07 at the owner's request, after v1.8.0 shipped and the
numbered plan closed at Sprint 074. It is written to be accepted, rejected, or cut down. Nothing
here is built.

The owner's words: *"the last major feature we could try to ship is proper auth and multiuser
support. The goal with multiuser is to allow a single install serve at least two independent
libraries to two users. Organization is the priority, as everything is self hosted, assume admin
has unrestricted access to the data, privacy is not a concern. A basic user/password should be
supported, any help in reducing user interaction and friction is welcome. Local use, with tailscale
as a proxy to his local network is still the primary expected use. A single user setup without auth
could still be available for easy deployments. Easy mobile access is a priority, web browser in the
local network is the expected use for now, not app planned. This may be a heavy change, so plan it
as as many sprints necessary to reach its own major release (maybe 2.0?)."*

Every count below was read off the code at `11db2c5`, not estimated.

---

## 1. What is already built, and what genuinely is not

This is the part that changes the cost. The v1 spec promised that multiuser would "reduce
data-model churn" by putting `user_id` on `entries` and `shelves` (product spec §9), and then
warned: *"multiuser still requires a real users table, ownership backfill, authentication
identities, authorization checks, and uniqueness validation. Do not claim it is migration-free."*

Both halves of that are true, and the first half was actually done.

### 1.1 Already there

| Thing | Where | State |
|---|---|---|
| `entries.user_id` | `0002_domain_schema.py:70` | `NOT NULL`, `server_default "1"` |
| `shelves.user_id` | `0002_domain_schema.py:104` | `NOT NULL`, `server_default "1"` |
| `uq_entries_user_item` | `0002_domain_schema.py:84` | The uniqueness multiuser needs, already user-scoped |
| `uq_shelves_user_slug` | `0002_domain_schema.py:108` | Same, for slugs |
| Six user-leading indexes | `0002`, `0003`, rebuilt in `0013` and `0015` | Every list, status, score and date query plan is already `(user_id, …)` |
| `LibraryService(engine, user_id=1)` | `application/library.py:135` | The service takes a user and filters on it in ten places |
| `DomainRepository(…, user_id=1)` | `infrastructure/repositories.py` | Five signatures already carry it |

The measured consequence: the query plans multiuser needs already exist and have already been
benchmarked. Nothing in §5's keyset pagination, facet counting, or list sorting has to be
redesigned, re-indexed, or re-measured. `LibraryService` is already the seam.

### 1.2 Not there

| Missing | Consequence |
|---|---|
| A `users` table | `user_id` is an integer pointing at nothing. No FK, no name, no credential |
| A `sessions` table | No way to hold a login, and no way to revoke one |
| Any authentication at all | `AKASHA_*` has no auth setting; no login route, no cookie, no 401 |
| `user_id` on `import_batches`, `import_records`, `import_effects` | An import and its undo ledger belong to nobody. Two users importing concurrently would share one undo history |
| `user_id` on `jobs` | Import jobs are per-user; enrichment jobs are per-item. The table cannot currently tell them apart |
| A user on the request | `LibraryService(request.app.state.engine)` is constructed **24 times across 8 files** with no user argument, so the default `1` wins every time |
| `enrichment.py:443` | Hardcodes `EntryRow.user_id == 1` outright, writing a provider note onto user 1's entry |
| Any admin concept | No roles, no user management, no "view another library" |

### 1.3 The three counts that size the work

- **24 service construction sites** across 8 backend files (11 of them in `api/library.py` alone)
  must stop defaulting the user and start receiving one.
- **213 `create_app(` calls** across the backend test suite. If authentication defaults to *on*,
  every one of them breaks. This single fact dictates the design in §2.1.
- **6 frontend API modules** under `src/api/` call `fetch` directly. There is no shared client, so
  there is no single place a 401 is currently handled.

---

## 2. What is proposed

### 2.1 Auth is a mode, and the default mode is today

`AKASHA_AUTH` takes `off` (default) or `on`.

**`off` is bit-for-bit today's behaviour.** No login screen, no cookie, no users table consulted.
Every request resolves to a single implicit user whose id is `1` — the rows that already exist.
An existing install upgrades to 2.0 and notices nothing. The 213 existing API tests keep passing
without one edit. `docker compose up` on a fresh machine still gives a working library with no
password to invent.

**`on` turns the same code path into a real identity.** The resolver that returns "user 1" in `off`
mode returns "whoever this session cookie belongs to" instead. Everything downstream is identical,
because everything downstream already takes a `user_id`.

This is the whole architectural bet, and §1.1 is why it is affordable: the application was already
written as `render(entries WHERE user = X, filter, sort)`, exactly as product spec §9 said to
write it. What is missing is the sentence that decides X.

### 2.2 Identity, credentials and sessions

**`users`**: `id`, `username` (unique, normalized), `display_name`, `password_hash`,
`password_salt`, `is_admin`, `created_at`, `updated_at`. No email — there is no mail to send, and
asking for one is friction with no payoff.

**Password hashing uses `hashlib.scrypt` from the standard library.** It is memory-hard, it is in
every Python the project already runs, and it adds nothing to a runtime dependency list currently
ten entries long. §5.2 costs `argon2-cffi` as the alternative and explains why it is not worth a
new C extension for a two-user install.

**`sessions`**: `id`, `user_id`, `token_hash`, `created_at`, `last_seen_at`, `expires_at`,
`user_agent`. The cookie carries an opaque random token; the table stores only its hash. A
server-side row rather than a self-contained signed cookie, for one reason that matters here:
sessions must be long-lived for a phone to be usable, and a long-lived credential you cannot
revoke is a bad trade. "Sign out everywhere" is a `DELETE`.

**Cookie**: `HttpOnly`, `SameSite=Lax`, `Path=/`, and `Secure` **only when the request arrived over
HTTPS**. This is not a nicety. A LAN install reached at `http://192.168.1.40:4441` would never
receive a `Secure` cookie and could never log in; the same install behind Tailscale Serve is
HTTPS and should get one. The flag follows the request, and `AKASHA_COOKIE_SECURE` can force it.

**Lifetime**: 400 days, refreshed on use. On a tailnet-only deployment the session *is* the
convenience, and re-authenticating a phone every fortnight is exactly the friction the owner asked
to remove. §5.3 costs the shorter-session alternatives.

### 2.3 First run, and the second user

**First run with `AKASHA_AUTH=on` and no users**: every API route returns `409 setup_required`, and
the SPA shows one screen asking for a username and a password. Submitting it creates the admin,
**claims every existing row** (all the `user_id = 1` data becomes theirs, because it always was),
and logs them in. One screen, two fields, no email, no confirmation step.

An operator who prefers automation can instead set `AKASHA_ADMIN_USERNAME` and
`AKASHA_ADMIN_PASSWORD`; the admin is created at startup and the setup screen never appears. Both
paths are documented; neither is required.

**The second user** is created by the admin from a settings screen: username, display name, initial
password. No invitations, no tokens, no email round-trip. Two people who live in the same house do
not need an invite flow, and every piece of one is a thing that can break at 1am. The new user can
change their own password from the same screen, scoped to themselves.

### 2.4 What is shared, and what is not

This is the decision that defines "two independent libraries", and it follows directly from
*"organization is the priority… privacy is not a concern"*.

| Shared across users | Private to one user |
|---|---|
| `items` and their titles, years, covers | `entries` — status, score, notes, dates, progress |
| `item_identifiers`, `item_sources` | `shelves`, `entry_shelves`, `entry_formats` |
| Cover files on disk | `import_batches`, `import_records`, `import_effects` |
| Provider budgets and provider health | Insights, triage, export |
| Enrichment jobs (they enrich an item) | Import jobs (they act on one person's library) |

The metadata cache stays one cache. Two people who both own *Rayuela* should share one row, one
cover, one enrichment fetch and one provider request — that is the organization the owner is
asking for, and duplicating the cache per user would be strictly worse in every dimension.

**Attachments are the one genuinely open question.** They hang off `items`, so an epub uploaded by
one person is visible to the other. Given the stated position that privacy is not a concern and one
copy of a file is better organization than two, the recommendation is to **leave them shared** and
say so out loud in the product spec. It is flagged in §7 because it is the one place where "shared
cache" stops being obviously right, and it is cheap to decide now and expensive to change later.

### 2.5 The admin sees everything

*"Assume admin has unrestricted access to the data."* Built as an explicit, visible mode rather
than an implicit privilege: an admin picks another user from the settings screen and the whole
application renders that user's library, with a persistent banner naming whose library is on screen
and one control to leave. Every route honours it, because every route already takes its user from
one resolver.

This costs almost nothing once §2.1 exists — it is one more way for the resolver to answer — and it
pays for itself three times over: it is the support tool, the migration tool, and the answer to
"where did that entry go".

### 2.6 Friction, specifically

The owner asked twice for less of it. Concretely:

1. **A 400-day session.** Log in on the phone once.
2. **A login form a password manager understands**: a real `<form>`, `autocomplete="username"` and
   `autocomplete="current-password"`, one submit button, no multi-step reveal. This is the single
   highest-value mobile detail and it is five attributes.
3. **Optional trusted-header authentication for Tailscale.** Tailscale Serve can inject the
   authenticated tailnet identity as a request header. With `AKASHA_TRUSTED_PROXY_HEADER` set,
   a request carrying a known identity is logged in with no form at all — the tailnet already
   authenticated it. This is the largest friction reduction available for the owner's stated
   primary deployment, and it is also the most dangerous setting in the proposal: a misconfigured
   proxy that lets a client set the header itself is a full bypass. It is therefore **off by
   default, refuses to work unless the peer address is in an explicitly configured allowlist, and
   is documented with the warning attached.** §5.4 costs it against passkeys.
4. **No re-authentication prompts anywhere.** There is nothing in this application worth a
   step-up challenge.
5. **`off` stays the default**, so nobody who does not want any of this pays for it.

---

## 3. What it costs

Eight sprints, 075 through 082, ending in **2.0.0**. The order is not negotiable in its first
half: the schema must exist before the resolver, and the resolver must exist before anything can
authenticate.

| Sprint | Delivers | Backend | User-visible |
|---|---|---|---|
| **075 — Identity in the schema** | `users`, `sessions`, `user_id` on `import_batches`/`import_records`/`import_effects`/`jobs`, FKs on `entries.user_id` and `shelves.user_id`, everything backfilled to a single seeded user. `AKASHA_AUTH` exists and only accepts `off`. | One migration, with a downgrade and a migration test from the current head | **None.** A migration that runs on the owner's real database and changes nothing observable |
| **076 — The request has a user** | The resolver. All 24 construction sites take a user; the `user_id=1` defaults and the `enrichment.py` literal are deleted; imports, undo, export, insights and jobs carry it. A guard test asserts no `user_id` literal survives outside the resolver. | Refactor only, no schema | **None.** Still one user, still no login |
| **077 — Password and session** | `users` gets real credentials (scrypt), `sessions` gets used, `POST /api/auth/login`, `DELETE /api/auth/session`, `GET /api/auth/me`, the 401 contract, the cookie policy, login rate limiting. `AKASHA_AUTH=on` becomes legal. | Auth router, session store, one dependency | API-level only; no screens yet |
| **078 — The way in** | The login screen, the first-run setup screen, the 401 handling every one of the 6 API modules needs, the redirect-back-to-where-you-were, the mobile pass at 390px, the password-manager attributes. | None | **The whole visible half.** A single-user install can now be behind a password |
| **079 — The second user** | Admin role enforced, the settings screen (create user, rename, reset password, delete), self-service password change, and the cross-user isolation suite: every route probed as user B against user A's ids. | User management routes | Two people, two libraries |
| **080 — The admin sees everything** | View-as, the banner, the way out, admin-only enforcement, and an audit line in the log for every impersonated request. | One resolver branch | Support, migration and recovery |
| **081 — Friction** | Trusted-header authentication with its allowlist, the 400-day refreshing session, session listing and "sign out everywhere", and the mobile login walkthrough on a real phone. | Header resolver, session refresh | Log in once, on the tailnet, never again |
| **082 — 2.0** | The exposure boundary rewritten (product spec §9, technical spec §9, the `AGENTS.md` invariant, the runbook's proxy guidance, `.env.example`, `README.md`, `compose.yaml`'s warning), the container smoke test extended to cover **both** modes, release notes, and the version bump to `2.0.0`. | None | The release |

**Sprint 076 is the one that must not be trimmed or merged.** It ships zero user-visible change and
touches 8 files and 24 call sites, which is exactly the kind of sprint that gets folded into its
neighbour and then goes wrong. It is also the sprint that makes 077 through 081 small. Keeping it
alone, with its own gate, is the whole reason this plan is eight sprints rather than five.

**The acceptance criterion that holds the plan honest**: at the end of every sprint, `AKASHA_AUTH`
unset must behave exactly as v1.8.0 did, and the existing 1364 backend, 305 frontend and 130 e2e
tests must pass **unchanged** except where a test asserts something this plan deliberately moved.
A sprint that has to edit the existing suite broadly has got the boundary wrong.

---

## 4. What this proposal deliberately does not do

- **No public exposure.** Authentication is the *precondition* for it, not the same thing. The
  invariant becomes "no internet-reachable proxy, DNS or port forward unless `AKASHA_AUTH=on`,
  HTTPS terminates in front, and the session cookie is `Secure`" — a narrower rule, not a deleted
  one. Nothing in these eight sprints puts Akasha on the internet.
- **No public share links.** Product spec §9 pairs sharing with auth. It becomes cheap after 077
  and it is still a separate feature with its own product questions (does a shared list update
  live, can it be revoked, does it leak the shelf name). Not scheduled.
- **No per-user provider budgets or quotas.** Budgets are a property of the deployment.
- **No SSO, OIDC, LDAP or OAuth.** Two people in a house.
- **No email.** No verification, no reset link, no SMTP configuration. An admin resets a password.
- **No per-user configuration.** Settings stay deployment-wide.
- **No mobile application.** The owner ruled it out for now; the mobile work here is the browser at
  390px, which is where every screen is already tested.

---

## 5. Alternatives, and what each would cost

Costed so the shape of the work is a choice rather than this document's opinion.

### 5.1 For the mode switch

| Strategy | What it is | Cost | Verdict |
|---|---|---|---|
| **`off` by default, `on` opt-in (§2.1)** | One resolver, two answers. | Included above | **Recommended.** The only option that leaves 213 existing tests and every existing install untouched |
| Auth always on | Delete the single-user path; everyone gets a login. | ~1 sprint *less* to build, but the whole existing test suite has to be re-fixtured, and every existing install needs a password before it starts | Rejected. It breaks the owner's own "easy deployments" requirement and turns a refactor into a rewrite of the gate |
| A third `proxy` mode | Auth entirely delegated upstream, no local users. | ~½ sprint on top | Folded into §2.6's trusted header instead, which is the same capability without a third code path |

### 5.2 For password hashing

| Strategy | Cost | Verdict |
|---|---|---|
| **`hashlib.scrypt` (stdlib)** | Zero dependencies, ~30 lines | **Recommended.** Memory-hard, ships with Python, and the threat model is a household LAN, not a leaked database of millions |
| `argon2-cffi` | One runtime dependency, a C extension in the image | Better algorithm on paper. Rejected for a two-row `users` table: the project keeps ten runtime dependencies and this would be the first one added for a marginal gain |
| `bcrypt` | One dependency, 72-byte password truncation | Rejected. Same dependency cost as argon2 with a worse algorithm and a real footgun |
| A single shared password in an env var | ~⅓ sprint | This is what product spec §9 originally proposed, and it cannot express two users. Rejected by the requirement itself |

### 5.3 For sessions

| Strategy | Cost | Verdict |
|---|---|---|
| **Opaque token, hashed in a `sessions` table, 400 days (§2.2)** | Included above | **Recommended.** Revocable, listable, and long enough that a phone logs in once |
| Signed stateless cookie (JWT or `itsdangerous`) | ~½ sprint less; no table | Rejected. A 400-day credential that cannot be revoked is the wrong trade, and "sign out everywhere" becomes impossible without a key rotation that logs everyone out |
| Short session plus refresh token | ~½ sprint more | Rejected. It buys security this threat model does not need and spends it in exactly the currency the owner asked to save |

### 5.4 For reducing login friction further

| Strategy | What it is | Cost | Verdict |
|---|---|---|---|
| **Trusted header from Tailscale Serve (§2.6)** | The tailnet already authenticated the request; read the identity it asserts. | ~½ sprint, inside 081 | **Recommended, off by default.** The largest possible friction reduction for the stated primary deployment. Also the most dangerous setting here, hence the peer allowlist and the loud documentation |
| Passkeys / WebAuthn | A fingerprint or face unlock instead of a password. | ~1–1.5 sprints: a library, a credential table, a registration flow, a cross-device story, and a recovery path when the phone is lost | Genuinely lower friction than a password, and genuinely more machinery. **Not scheduled.** Becomes worth it if the trusted header proves insufficient; the `users` table is designed so credentials can be added beside the password rather than replacing it |
| A magic link | Emailed one-time login. | ~1 sprint plus SMTP configuration | Rejected. It adds mail as a dependency of logging in |
| A remembered device PIN | Short numeric code after first login. | ~½ sprint | Rejected as strictly worse than a 400-day session: same convenience, extra code, weaker secret |
| No session expiry at all | The cookie never expires. | Free | Rejected only because a lost phone should be revocable; the 400-day session with server-side revocation is this option with an off switch |

### 5.5 For the sprint count

| Strategy | Cost | Verdict |
|---|---|---|
| **Eight sprints, 075–082 (§3)** | As above | **Recommended.** Each leaves a demonstrable increment and a green gate |
| Five sprints, merging 076 into 077 and 080/081 into 082 | ~3 sprints less on paper | Rejected. 076 is a 24-site refactor with no user-visible output; merging it into the sprint that introduces login means a failure in either is diagnosed as a failure in both |
| Two sprints — "add auth", "add users" | Rejected on sight | This is the plan that produces a half-migrated schema and an authorization hole. The isolation suite in 079 exists precisely because "it seems to work" is not evidence here |
| Twelve sprints, one per screen | ~4 more | Rejected. The screens do not change; only the resolver does |

---

## 6. Risks

1. **An authorization hole is silent.** Unlike a layout defect, a leak between two libraries looks
   exactly like working software. Sprint 079's isolation suite — every route, probed as user B
   against user A's ids, expecting 404 rather than 403 so ids do not leak — is the mitigation, and
   it is an acceptance criterion, not a nice-to-have.
2. **Sprint 076 is a wide refactor with no visible output.** Mitigated by the guard test that
   fails if a `user_id` literal reappears, and by the rule that the existing suite must pass
   unchanged.
3. **The migration touches every user-owned table.** Mitigated by the existing startup backup
   (DEC-039), a migration test from the current head, and 075 shipping with no behaviour change so
   a rollback is a downgrade rather than a restore.
4. **The trusted-proxy header is a bypass if misconfigured.** Mitigated by: off by default, a
   required peer allowlist, refusing to start if the header is configured without one, and the
   warning living in `.env.example` next to the setting rather than in a document nobody opens.
5. **`Secure` cookies and plain-HTTP LAN access conflict.** Mitigated by deriving the flag from the
   request scheme rather than from a static setting, with an override for a proxy that terminates
   TLS and forwards plain HTTP.
6. **The e2e suite gains a login step.** 130 tests currently assume an open application. Mitigated
   by `AKASHA_AUTH=off` remaining the default in the dev server, so only the new auth specs opt in.

---

## 7. Open questions for the owner

These change user-visible behaviour or the data model, so they are asked rather than assumed.

1. **Are attachments shared or per-user?** (§2.4) They hang off `items` today. Recommendation:
   leave them shared, because privacy is not a concern and one copy is better organization than
   two. Cheap now, expensive after 2.0.
2. **Should the admin's "view as" be able to *write*, or only read?** Recommendation: write.
   "Unrestricted access" was the instruction, and a read-only mode cannot fix the mistake it was
   opened to investigate.
3. **Is the trusted-header path wanted at all** (§2.6, §5.4), given it is the one setting in this
   proposal that can be misconfigured into a bypass? Recommendation: yes, off by default. It is
   the single largest friction win available for a Tailscale deployment.
4. **Does the second user need their own Calibre library?** The Calibre mount is one read-only path
   for the whole install today. Recommendation: leave it deployment-wide for 2.0 and treat a second
   mount as a later question — it is a Compose change and an importer argument, not a schema one.
