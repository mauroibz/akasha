# Sprint 128 — Public exposure hardening

**Sprint:** 128
**Status:** completed
**Roadmap revision:** 52
**Depends on:** 127
**Owner:** Mauro

## Objective

An `AKASHA_AUTH=on` install can be published on a personal domain (for example
`akasha.ibz.com.ar`, behind Cloudflare Tunnel and Access) without a known way for a stranger
to get in, and without a compromised account — or a compromised application process — reaching
the rest of the home server (DEC-180).

## Required context

- `SECURITY.md`, `docs/operations/runbook.md` (*Turning authentication on*, *Running behind
  tailscale serve*, *Reverse proxy*, *Metrics*).
- DEC-151 (shared item cache, per-user libraries), DEC-180 (this sprint).
- `backend/src/book_tracker/app/middleware.py`, `api/auth.py`, `api/identity.py`,
  `application/sessions.py`, `application/passwords.py`, `config.py`, `app/lifespan.py`,
  `main.py`, `Dockerfile`, `compose.yaml`.

## Current implementation baseline

A six-way audit on 2026-11-21 (authentication, authorization, input handling, browser surface,
container, dependencies) against `12705c9` found, with proofs of concept run in-process:

| # | Severity | Finding |
|---|---|---|
| F1 | critical | Calibre export upload writes attacker-named files anywhere the app user can write (`domains/book/calibre.py` `_materialize_export`, `name` from the uploaded `metadata.db` is not confined) — with `/app` owned by the app user this is code execution on restart and script injection into the served SPA. |
| F2 | high | Authentication bypass: the middleware decides on `request.url.path`, built from the unvalidated `Host` header; `Host: x/api/health/?` skips the boundary for every route without a `CurrentUser` dependency (search, import detect/browse, enrichment backfill, docs). |
| F3 | high | Unlimited password guessing: once a peer is rate limited, wrong guesses answer 429 without being counted and the right one answers 200. Behind a tunnel every visitor is one peer. |
| F4 | high | First-run setup is open to whoever arrives first and makes them admin, owning the existing library. |
| F5 | high | Attachments carry no owner: any user who adds the same work (same ISBN, or the shared `manual` source id) lists, downloads, renames and deletes another user's private files, and edits the shared item's metadata and cover for everyone. |
| F6 | high | Pillow 11.3 (many decoder CVEs), opened with every decoder enabled on user uploads. |
| F7 | high | Upload caps are checked after the whole multipart body is spooled to disk; JSON bodies are read whole into memory before validation, including unauthenticated login. |
| F8 | medium | `GET /api/export` lists every item in the install, with manual source ids that enable F5. |
| F9 | medium | CSRF from sibling subdomains (`SameSite=Lax`, body-less or content-type-less JSON accepted). |
| F10 | medium | Owner lockout: five failures per five minutes per username refuse even the right password. |
| F11 | medium | Passwords of one character are accepted. |
| F12 | medium | Cookie not `Secure` behind a tunnel unless configured, no `__Host-` prefix (sibling-subdomain session fixation). |
| F13 | medium | No security headers (CSP, frame-ancestors, nosniff, Referrer-Policy), no `Cache-Control` on authenticated JSON. |
| F14 | medium | CPU denial of service: `csv.Sniffer` and `<[^>]+>` regexes on attacker input; unbounded gunzip in sniffing. |
| F15 | medium | Cover fetch follows redirects inside httpx, so the per-hop allowlist and HTTPS checks never run. |
| F16 | medium | Starlette 0.46 advisories (Host-derived URL, Range DoS, multipart). |
| F17 | medium | Non-admins browse and import the operator's Calibre mount; non-admins queue install-wide enrichment backfill. |
| F18 | low | `/metrics` public when enabled; `/api/health/providers` public. |
| F19 | low | Exception logging bypasses secret scrubbing; `TMDB_READ_TOKEN` not scrubbed. |
| F20 | hardening | Container: app user owns `/app`, writable root filesystem, all capabilities, no resource limits, port published on every interface, secrets only through environment, no egress containment. |
| F21 | low | Limiter memory unbounded; sessions not rotated on password change; ownerless jobs readable by any user; EPUB entity check bypassable with UTF-16; uploaded `metadata.db` opened without `trusted_schema=OFF`. |

## Deliverables

1. **The boundary** — the middleware decides on `scope["path"]`; `/metrics` and provider health
   behind the boundary; a one-time setup code; counted, per-client login limiting with a client
   address taken from a configured header only from a trusted peer; a 12-character minimum for
   new passwords; an Origin/`Sec-Fetch-Site` check on unsafe API requests; a `__Host-` cookie
   when Secure; session rotation on password change; security headers and `no-store` on the API;
   API docs off with auth on.
2. **Ownership** — attachments owned per user (migration), manual items per user, shared item
   edits limited to admins or the item's only owner, the JSON export scoped to the user's items,
   the Calibre mount and enrichment backfill admin-only, every API route with a principal.
3. **Untrusted input** — Calibre export paths confined; request bodies capped while streaming;
   linear-time sniffing and tag stripping; no redirects inside the cover client; Pillow limited to
   JPEG/PNG/WebP; bounded reads.
4. **Dependencies and logs** — Pillow ≥ 13, FastAPI/Starlette past the advisories, certifi
   refreshed; exception text scrubbed.
5. **Containment** — root-owned application files, read-only root filesystem, dropped
   capabilities, limits, temp files on the data volume, `/run/secrets` support, a public compose
   overlay with a Cloudflare Tunnel sidecar and no published port, optional verification of the
   Cloudflare Access JWT in the application, an egress firewall recipe, and the public exposure
   guide in the runbook.

## Acceptance criteria

1. Every finding F1–F21 is fixed or, where it is an operator choice, documented with the
   recommended setting; each fix is covered by a test that failed before it.
2. A forged `Host` header cannot reach any route without a session (tested).
3. Wrong passwords are counted however the limiter answers; the right password from a client
   that has not failed still signs in while another client is being refused (tested).
4. Setup without the code shown in the server log answers 403 (tested).
5. One user cannot list, read, rename or delete another's attachment, nor edit an item another
   user also holds, nor see another user's items in the export (tested).
6. A Calibre export naming `../` or an absolute path is refused and writes nothing outside its
   folder (tested).
7. Oversized bodies answer 413 before being spooled (tested).
8. The existing suites covering the changed modules, `make check` and the Playwright specs for
   the setup, login and account screens pass; the changed screens are seen in the running app.

## Verification

Per DEC-167: the tests for the changed code, `vitest related`, `make check`, the Playwright
specs for the changed screens, and the changed flow seen in the running app. Because this sprint
changes the request boundary under every route, the full backend suite is run as well.

## Explicit non-scope

- Choosing and configuring the real Cloudflare account, tunnel and Access policy (the owner does
  that on the server; the runbook says how).
- Two-factor authentication in the application (Access in front provides it).
- Per-user storage quotas (DEC-146 §4 stands; the body caps bound a single request).

## Outcome

Delivered 2026-11-21 on branch `ccr-61c66a6d-g1wptf`. The audit ran as six read-only reviews;
the fixes ran as five parallel work streams merged into the branch, followed by the merge
repairs below.

**By finding** (commit in brackets):

- **F1** Calibre export `data.name`/`format` must be one safe segment and resolve inside the
  book folder; uploaded `metadata.db` opened with `trusted_schema=OFF` (`c2507cf`).
- **F2** the boundary reads `scope["path"]`; a forged `Host` answers 401 (`57e964d`).
- **F3, F10** counted limiting per (username, client), per username at 10×, per client at 4×;
  a limited request is refused before the password is checked; bounded memory; client from
  `AKASHA_CLIENT_IP_HEADER` only from a trusted peer (`57e964d`).
- **F4** one-time setup code (`AKASHA_SETUP_TOKEN`, or generated and logged while no account
  has a password) (`57e964d`, `ed7aee5`).
- **F5** attachments owned (migration `0034_attachment_owners`), manual items per user,
  `403 item_shared` for a non-admin editing an item someone else holds (`d16e268`); a
  transfer keeps the files (`4e5ecd3`).
- **F6, F16** Pillow 13.0, Starlette 1.10 / FastAPI 0.136.3, anyio 4.16, certifi 2026.11.20;
  covers decode JPEG/PNG/WebP only (`4646614`, `7b0bc7f`). `pip-audit`: no known
  vulnerabilities; `npm audit --omit=dev`: 0 (`d69cb00`).
- **F7** bodies capped while streaming (`app/body_limits.py`, default 1 MiB, per-route upload
  caps, `413 payload_too_large`; `507` before reading when the disk would run low)
  (`9ee6ead`, `7aed4d4`).
- **F8** the JSON export carries only the user's items and files (`8b4e48b`).
- **F9** unsafe `/api/` requests from another site answer `403 cross_site_request`.
- **F11** 12 characters for every new password; login accepts existing ones.
- **F12** `__Host-akasha_session` when Secure; startup warning when Secure cannot be derived.
- **F13** CSP (`script-src 'self'`, the theme script moved to `/theme-init.js`), nosniff,
  `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, COOP, Permissions-Policy, HSTS
  over HTTPS, `no-store` on the API, `no-cache` on the shell; docs off with auth on.
- **F14** linear sniffing and tag stripping, bounded gunzip (`e35bd06`).
- **F15** every cover redirect hop validated (`7b0bc7f`).
- **F17** server Calibre mount and enrichment backfill admin-only; every `/api` route names a
  principal, guarded by a test that walks the routes (`2afc05b`).
- **F18** `/metrics` needs an admin with auth on; `/api/health/providers` needs a session;
  `ready` stops reporting free bytes to strangers.
- **F19** tracebacks rendered before scrubbing; uvicorn's loggers through the same scrubber;
  TMDB token and admin password scrubbed (`6bf70e2`).
- **F20** root-owned code, read-only root filesystem, no capabilities, `no-new-privileges`,
  limits, `TMPDIR=/data/tmp`, `/run/secrets`, `compose.public.yaml` (no published port,
  cloudflared sidecar on an internal network), `scripts/akasha-egress-firewall.sh`, optional
  Cloudflare Access JWT check in the application (`430accd`, `6898bff`), and the runbook's
  *Publishing on the internet* guide (`500aa63`).
- **F21** sessions rotated on password change and on login; `AKASHA_SESSION_DAYS`;
  ownerless jobs visible only through their batch; EPUB entity declarations refused in any
  encoding; provider ids quoted as one path segment (`59f9619`, `ed58325`).

**Acceptance criteria**

1. Every finding fixed or documented, each with a test that failed first: new
   `test_security_boundary.py`, `test_security_ownership.py`, `test_security_input.py`,
   `test_security_body_limits.py`, `test_security_cloudflare_access.py`,
   `test_security_containment.py`, plus additions to `test_logging.py` and `test_users_api.py`.
2. Forged `Host` → 401 (tested; seen live).
3. Counted limiting (tested; seen live: five 401 then 429, the right password from the same
   client 429 until the window passes).
4. Setup without the code → 403 (tested; seen live in the API and on the screen).
5. Cross-user attachment, shared-item and export isolation (tested).
6. Calibre export path escape refused, nothing written (tested; the audit PoC re-run).
7. Oversized bodies → 413 before spooling (tested; a 3 MB login body seen live as 413).
8. Full backend suite: 1934 passed, 1 failed — `test_prune_items::test_the_report_names_a_cover_that_could_not_be_removed`,
   which relies on `chmod` blocking a delete and fails on the unmodified base too when run as
   root, as this container does. Vitest 553 passed. Playwright `auth.spec.ts` and
   `import.spec.ts`: 27 passed. `make check` passed. The image was built and run by the
   containment stream: healthy on a read-only root, no capabilities, no Server header.

**Walkthrough** (built frontend, auth on, fresh data): the setup screen shows the code field
and the 12-character hint; a 5-character password is refused in place; the code from the log
creates the admin; Add, Shelves, Insights, Diary and Import load with **zero console errors
and zero CSP violations**. Probes after setup: forged `Host` 401, `/metrics` 401, `/docs` 401,
a second setup 409, a sibling-site POST 403, the shell `no-cache`, the API `no-store`.

**Deviations and notes**

- FastAPI 0.136.3 rather than the newest: 0.137+ changes `app.routes` in a way three route-
  walking tests depend on; 0.136.3 already runs on the fixed Starlette.
- On a Secure request only the `__Host-` cookie is read (accepting the legacy name there would
  reopen sibling-subdomain fixation); every device signs in once after the upgrade.
- `POST /api/entries` with `source: "manual"` now answers 422; hand-typed adds use the manual
  form, which is unaffected.
- With auth on, Prometheus can no longer scrape `/metrics` without an admin session.
- The egress firewall script was syntax-checked and dry-run only; it has not run on a host.
- Not fixed, recorded: `_EDITION_NOTE` (`[(\[][^)\]]*[)\]]`) is quadratic on a long run of
  unclosed brackets, bounded by title length caps; uvicorn's access log keeps query strings
  (search terms), kept because the runbook uses it to find a proxy's address.
