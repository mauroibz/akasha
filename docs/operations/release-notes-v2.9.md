# Akasha v2.9.0 — release notes

Ready for the internet, and faster. Sprints 128–129 (DEC-180 to DEC-182).

## What you will notice

- **Signing in.** New passwords need at least 12 characters; existing passwords keep working.
  The first-run setup screen asks for a one-time code printed in `docker compose logs akasha`
  (or set `AKASHA_SETUP_TOKEN`). Changing your password signs your other devices out.
- **Faster library and Diary.** On a 10,000-entry library a page of the library loads in
  40 ms instead of 183 ms, the Diary in 0.1 s instead of 2.8 s, and the first load ships a
  quarter of the JavaScript it did. Returning to the tab no longer reloads everything; a change
  made on another device shows within 30 seconds, on the next navigation.
- **Private files stay private.** With several users, attachments and hand-typed items belong
  to the user who added them, and the JSON export carries only your own items.

## Under the hood

- **Public exposure (Sprint 128).** The fixes for a 21-finding security audit: request bodies
  capped while they stream, security headers, a cross-site request check, per-client login
  limiting that no longer locks the owner out, session rotation, a `__Host-` cookie when
  Secure, safer image decoding, and linear-time parsing of untrusted input. A new
  `compose.public.yaml` overlay publishes Akasha through a Cloudflare Tunnel with no open port;
  the runbook's *Publishing on the internet* walks through it.
- **Containment.** `compose.yaml` now runs the container with a read-only root filesystem, no
  Linux capabilities, `no-new-privileges`, and ceilings on memory (1.5 GB), CPU (1) and
  processes (256). Raise them with `AKASHA_MEM_LIMIT`, `AKASHA_CPUS` and `AKASHA_PIDS_LIMIT`.
  The image keeps temporary files on the data volume (`TMPDIR=/data/tmp`).
- **Security log.** Every refusal at the boundary (failed or limited login, setup-code guess,
  password-change guess, cross-site request) is one JSON line with `"category": "security"`.
  See the runbook's *Watching for attacks*.
- **Safer upgrades.** Each upgrade runs as one SQLite transaction, so a migration that fails
  halfway leaves the database where it was. A pre-migration backup is reused only while it
  still holds the live library.
- **Robustness.** A stop with a browser tab open ends in a fraction of a second instead of being
  killed after 20; interrupted import installs resume; files are synced to disk before their
  rows commit; cancelled jobs stay cancelled.

## Upgrade

**Tagged `v2.9.0`.** Two migrations: `0034` gives attachments an owner (an existing one goes to the
user whose import attached it, else the only user with the item, else user 1), `0035` adds two join indexes. The application
backs the database up before migrating.

Take the new `compose.yaml` together with the 2.9.0 image: the read-only container needs the
image's `TMPDIR`, and with the 2.8.0 image uploads would be capped by the 64 MB `/tmp`.

```bash
git checkout v2.9.0            # if you run from a clone, for the new compose.yaml
docker compose pull && docker compose up -d
```

If you pin in `.env`, move the pin to `AKASHA_VERSION=2.9.0` (or track the `2.9` line).

Contract change: `GET /api/entries` with `after=` returns `total: null` and `facets: null`; the
first page is unchanged.
