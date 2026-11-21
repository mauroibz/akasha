# Sprint 128 — Public exposure hardening

**Sprint:** 128
**Status:** in_progress
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

_Not started._
