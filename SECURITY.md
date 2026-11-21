# Security

## The threat model, stated plainly

**Akasha ships with authentication off by default.** In that mode it is built
to run on one machine on a trusted home network: anyone who can reach the port
can read and change every rating, note and shelf, with no login and no
authorization checks.

**With `AKASHA_AUTH=on`** the application has real accounts: a first-run setup
screen creates the admin, each user has a private library (entries, shelves,
imports, exports — all scoped per user; items and covers are a shared cache),
sessions are opaque server-side rows revocable from the account screen, and
cross-user ids answer `404` so they cannot be probed.

The exposure rule is the same in both modes, and it is a rule, not a suggestion:

- **No internet-reachable proxy, DNS or port forward, unless all four hold:
  `AKASHA_AUTH=on`, TLS terminates in front, the session cookie is `Secure`**
  (`AKASHA_COOKIE_SECURE=true`, or a trusted proxy's `X-Forwarded-Proto`
  deriving it), **and setup is completed** (or the admin bootstrapped from the
  environment) **before the hostname is published** (DEC-180).
- The supported way onto the internet is Cloudflare Tunnel with Cloudflare
  Access in front, through `compose.public.yaml`: no published port, Access
  as a first gate, the application's own login as a second. The runbook's
  [Publishing on the internet](docs/operations/runbook.md#publishing-on-the-internet-cloudflare-tunnel-and-access)
  section is the guide.
- Do not forward a port to it.
- Do not put it behind a reverse proxy that terminates on a public address.
- A host that has joined a VPN or mesh network (WireGuard, Tailscale, ZeroTier
  and the like) carries an extra interface, and `AKASHA_BIND=0.0.0.0` publishes
  on that one too — a port reachable from outside the building without anyone
  having forwarded anything. Exclude it by binding `AKASHA_BIND` to one address
  rather than to everything.
- A reverse proxy on the LAN (e.g. Nginx Proxy Manager at `books.home.lan`)
  is the supported deployment, and it is documented in
  [the operator runbook](docs/operations/runbook.md).
- Behind `tailscale serve`, the proxy can additionally assert each request's
  identity through `Tailscale-User-Login` — opt-in, allowlist-gated, and
  refused at startup without the peer allowlist. The runbook's
  [Tailscale section](docs/operations/runbook.md#running-behind-tailscale-serve)
  is the guide.

**Defence in depth with auth on (Sprint 128).** The first-run setup screen
asks for a one-time code printed in the server log, so a stranger who arrives
first cannot claim the admin account. Failed sign-ins are counted per client
however the limiter answers; behind a trusted proxy the client address comes
from a configured header (`CF-Connecting-IP` behind Cloudflare), believed only
from the proxy's address. Unsafe API requests from another origin are refused;
responses carry a Content-Security-Policy, `frame-ancestors`, `nosniff`, a
Referrer-Policy and `no-store` on the API; request bodies are capped while they
stream. With `AKASHA_CF_ACCESS_TEAM_DOMAIN` and `AKASHA_CF_ACCESS_AUD` set,
every request must carry a valid Cloudflare Access token, so one that went
around Access is refused inside the container.

**Containment.** The container runs as an unprivileged user that owns its data
and nothing else: the application code is root's, the root filesystem is
read-only, every Linux capability is dropped, privileges cannot be regained,
and memory, CPU and process count are capped. The public overlay publishes no
port, and `scripts/akasha-egress-firewall.sh` keeps the containers off the LAN
and off the host. Settings can be read from Docker secrets (`/run/secrets`)
rather than the environment. None of this makes a compromised application
harmless — it still holds the library and can reach the internet on 80/443 —
but it bounds what it can reach beyond that.

**"There is no authentication" is not a vulnerability report** for an install
running `AKASHA_AUTH=off` — it is the documented boundary. A report that an
unauthenticated install exposed on a public IP can be read by strangers
describes the licence's absence of warranty and this file, not a defect. A
report against an `AKASHA_AUTH=on` install is in scope below.

## What *is* in scope

Within that boundary, the application is expected to hold the following. A
failure of any of these is a real vulnerability and worth reporting:

- **Authentication and session integrity when `AKASHA_AUTH=on`.** Passwords are
  scrypt-hashed with per-user salts; the cookie holds a random token while
  only its SHA-256 is stored; a session cannot be used for another user; an
  unknown proxy-asserted identity is refused; setup needs the one-time code. A
  bypass of any of these is in scope.
- **The Cloudflare Access check when configured.** A request reaching any route
  other than the in-container healthcheck without a token signed by the
  configured team for the configured audience is in scope.
- **Containment.** A way for the application process to write its own code,
  regain a capability, or write outside `/data`, `/backups` and `/tmp` in the
  shipped container is in scope.
- **Cross-user isolation.** One signed-in user reading or writing another's
  entries, shelves, imports or sessions — including through an id that should
  have answered `404` — is in scope.
- **Path containment.** The SPA static handler and the Calibre adapter both
  resolve and confine paths. Escaping either — reading a file outside the static
  root or outside the Calibre mount — is in scope.
- **Calibre is read-only.** It is mounted `:ro` and opened with `mode=ro` plus
  `PRAGMA query_only`. Any write reaching a Calibre library is in scope.
- **Upload and fetch limits.** A 5 MiB cap on Goodreads CSV uploads; byte,
  pixel, host-allowlist and redirect caps on cover fetching; a 2 MiB payload cap
  and 5 s timeout on provider responses. A way past any of these — memory
  exhaustion, SSRF to an unlisted host, a decompression bomb — is in scope.
- **Log redaction.** Notes, review text, import rows, API keys and tokens are
  redacted before anything is written, and configured secrets are scrubbed out
  of arbitrary strings. Passwords and session tokens never enter a log. A path
  that leaks any of them is in scope.
- **Backup integrity.** A restore that silently produces a corrupt or partial
  database rather than failing loudly is in scope.
- **Dependency vulnerabilities** with a plausible path to exploitation in this
  application's actual usage.

## What is out of scope

- An operator exposing an `AKASHA_AUTH=off` install to a network they do not
  trust, against the rule above. The absence of rate limiting per user, CSRF
  tokens and audit logging on that surface follows from the single-user model.
- Anything requiring the operator to have already ignored the deployment
  guidance, such as exposing the port publicly.
- Findings from an automated scanner with no demonstrated impact here.

## Reporting

Open a **private security advisory** through GitHub's *Security* tab on this
repository. That keeps the report confidential until there is a fix.

Please include what you did, what happened, and what you expected. A minimal
reproduction against a local container is ideal.

This is a personal project maintained by one person in their own time. Expect a
first response within a couple of weeks, and no bounty — there is no budget for
one. Credit in the release notes is offered gladly if you would like it.

## Supported versions

The `main` branch is the only supported version. There is no backporting.
