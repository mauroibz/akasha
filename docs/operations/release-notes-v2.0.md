# Akasha v2.0 — release notes

**Two libraries, one install.** The owner's 2026-09-07 request was plain:
*"proper auth and multiuser support… a single install serve at least two
independent libraries to two users… a single user setup without auth could
still be available for easy deployments… easy mobile access is a priority."*
Eight sprints (075–082, accepted whole as [DEC-146](../decisions.md)) built it,
and this release ships it.

**Tagged `v2.0.0`.**

## A note on versioning

`2.0.0` is a major-sounding number for a non-breaking release, and that is
deliberate: the version says *the security model changed*, not that your data
moves. **Nothing migrates destructively and an existing install upgrades with
no action** — `docker compose pull && docker compose up -d`, the same two
commands as every v1 release. The pre-upgrade backup still runs on startup;
the five new migrations (0017–0021) add the users and sessions tables, attach
ownership to the import ledger and jobs, and give the seeded implicit user a
real row. Your library becomes the admin's the moment you turn auth on;
until then nothing visible changes at all.

The version surfaces — `backend/pyproject.toml`, `frontend/package.json`, the
FastAPI version and the generated OpenAPI contract — say `2.0.0` together, and
`make check` now fails when they disagree (Sprint 082, closing DEC-145's
finding that nothing cheap enforced it).

## What's new since v1.8.0

- **Authentication, off by default.** `AKASHA_AUTH=off` (the default) is the
  v1 behavior exactly: one shared library, no login, trusted LAN. `=on` adds a
  first-run setup screen that creates the admin account — and every entry and
  shelf already in the database becomes theirs. No reassigning by hand, nothing
  lost. The runbook's [Turning authentication on](runbook.md#turning-authentication-on)
  is the whole procedure.
- **Per-user libraries.** With auth on, entries, shelves, imports, exports and
  triage are private to each user. Two people adding the same book create one
  shared catalogue record — the cover and the metadata are a cache — but
  separate ratings, notes and shelves. Cross-user ids answer `404`, so one
  user cannot even probe whether another's exist.
- **Accounts, managed by an admin.** Settings → People: create an account,
  rename it, reset its password (which signs it out everywhere), flip its
  admin flag, and — when someone leaves — transfer or delete their library as
  an explicit choice. Each person can change their own password without the
  admin.
- **The admin can look into any library, as themselves.** *Act as* opens
  another person's library behind a banner that cannot be dismissed, stamps
  every write to its owner, and returns to the admin's own library in one
  action. The signed-in identity never changes; one audit event per request
  records who looked where. Acting ends on logout, expiry, password change or
  the target's deletion.
- **Sign in once.** A session lasts 400 days and slides forward while in use —
  a device you touch weekly never asks again (DEC-153). The account section
  lists every signed-in device with its last use and user agent: revoke one,
  or *Sign out everywhere* when a phone is lost.
- **Zero-tap login behind `tailscale serve`, optional.** Configure
  `AKASHA_TRUSTED_PROXY_HEADER` and a peer allowlist and a phone on the
  tailnet opens Akasha signed in already — the proxy asserts who is at the
  other end of the WireGuard tunnel. Safe by construction: the app refuses to
  start with a header but no allowlist, strips the header from any peer not on
  the list before anything reads it, refuses unknown identities unless
  autocreate is explicitly on, and never disables password login alongside.
  The runbook's [Tailscale section](runbook.md#running-behind-tailscale-serve)
  is the guide.
- **The screens work on a phone.** Login, setup and the account section render
  at 390px with no zoom-on-focus, 44px targets and the right keyboard types.
- **`make check` catches a version-surface drift in a second** — the four
  surfaces (pyproject, package.json, the FastAPI version, the generated
  contract) are compared on every check run, not only inside the minutes-long
  container test.

## The exposure rule, narrowed

v1 said: *no auth, so never expose it.* v2.0 says the same thing with a door:

> No internet-reachable proxy, DNS or port forward unless `AKASHA_AUTH=on`,
> TLS terminates in front, and the session cookie is `Secure`.

Authentication is the precondition for exposure, not permission for it. The
warning in `compose.yaml`, `.env.example`, the README and SECURITY.md all say
this one rule in the same words now.

## What an existing install has to do

**Nothing.** Auth stays off, the address stays the same, the data stays where
it was. The day you want accounts, the runbook's auth section is a five-minute
procedure that ends with you choosing a password on the setup screen.

If you turn auth on and something about a proxy goes wrong, password login is
never disabled — reach the container directly on the LAN, or set
`AKASHA_AUTH=off` again; the account system waits in the database untouched.

## What still isn't here

Public share links, Calibre write-back, OPDS, passkeys, email of any kind,
per-user settings — all still deferred, all still deliberate (DEC-146 §4).
Sharing becomes cheap now that authorization is a separate check, and it is
still a separate feature.

## Known deviations from the plan, recorded

- Sprint 081's real-tailnet walkthrough was waived by the owner at close
  (DEC-154): the smoke gate proves Akasha's half of the trusted-header
  contract against the real image — startup refusal, untrusted-peer stripping,
  allowlisted admission, unknown-identity refusal — and the first deployment
  behind `tailscale serve` doubles as the live proof. The failure mode is
  closed: a proxy that does not assert an identity leaves the ordinary login.
- At 10,000 entries with 200 queued import jobs, three contended insights
  scenarios exceed 500 ms p95 (worst `publisher/count` 1234.8 ms) — a scale
  never measured before, recorded in DEC-154 for a future sprint to budget.
  The first library page, which the spec budget does bind, measured 147.8 ms
  contended p95 at the same scale.
