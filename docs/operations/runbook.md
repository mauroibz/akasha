# Operator runbook

Everything here has been performed against a running container, not written from
the source. Commands assume the repository checked out on the host and `docker`
with the Compose plugin installed; nothing else is needed.

**Authentication is off by default.** With `AKASHA_AUTH=off` anyone who can
reach the port can read and change every rating, note and shelf — keep it on a
trusted LAN. Turning authentication on is its own section below:
[Turning authentication on](#turning-authentication-on). Publishing it on the
internet is another:
[Publishing on the internet](#publishing-on-the-internet-cloudflare-tunnel-and-access).

**The exposure rule.** No internet-reachable proxy, DNS name or port forward
unless all four hold: `AKASHA_AUTH=on`; TLS terminating in front; the session
cookie `Secure`; and setup completed (or the admin bootstrapped from the
environment) *before* the hostname is published (DEC-180).

## First install

```bash
cp .env.example .env      # then edit it
mkdir -p calibre
docker compose up -d
```

`USER_AGENT_CONTACT` is required and startup refuses without it: Open Library
asks callers to identify themselves. `GOOGLE_BOOKS_API_KEY` is optional; without
it search runs on Open Library alone and Spanish-language coverage is poor.

`data` and `backups` are named Docker volumes by default (DEC-075), seeded from
the image with the right ownership already on them — there is nothing to `chown`.
Want either as a real host directory instead (a NAS-backed `BACKUP_DIR`, direct
host access to the sqlite file)? See "Bind-mounting data and backups" below.

Check it came up:

```bash
docker compose ps                     # State should be "healthy"
curl -fsS http://localhost:4441/api/health/ready
```

The published port defaults to **4441**. An install that upgraded from an
earlier version and never set a port: put `AKASHA_PORT=8000` in `.env` to keep
the old address.

## Upgrading

```bash
docker compose pull
docker compose up -d
```

No `git pull`, no toolchain, no build: `docker compose pull` fetches the tag
`AKASHA_VERSION` names from `ghcr.io/mauroibz/akasha` — CI publishes it there
on every version tag — and `up -d` recreates the container from it. Pin the
version rather than trailing `latest`, so an upgrade is a decision you make
instead of one that happens to you on the next restart:

```bash
echo "AKASHA_VERSION=1.5.3" >> .env
docker compose pull
docker compose up -d
```

`AKASHA_VERSION` is read by every later `docker compose` command too — `down`,
`logs`, `scripts/backup.sh` — so keep it in `.env` once it is set. `latest`
always resolves to whatever the newest published tag is, major versions
included; a pinned version is the one you actually reviewed.

Building from source is still available — a fork, a local patch, or an
architecture other than the published `linux/amd64` — through the local-build
overlay:

```bash
git pull
docker compose -f compose.yaml -f compose.build.yaml up -d --build
```

The Dockerfile's two base images are pinned by digest, so a local build never
picks up an unreviewed change either — see the comment above its first `FROM`
line for the one-command refresh procedure, or let Dependabot's `docker`
ecosystem propose the update as a pull request.

Migrations run automatically at startup, and startup takes an online backup
first whenever there are pending revisions (DEC-039). That copy lands in
`/backups/pre-migration-<timestamp>/` and is **never** removed by nightly
retention, because it is the rollback point for that upgrade. If the backup
cannot be written the application refuses to migrate and exits, which is
deliberate: an unprotected schema rewrite on a database full of your own ratings
is worse than downtime.

The whole upgrade runs in one SQLite transaction, schema changes included: a
migration that fails part-way (disk full, a killed container) leaves the
database exactly at the revision it started from, and the next start simply
tries again. Under `restart: unless-stopped` that retry loop does not pile up
backups: a start reuses an existing pre-migration copy only while it still holds
exactly what the live database holds (its manifest records a content digest).
Once the library has changed since — for example after a rollback and some weeks
on the previous version — the next upgrade takes a fresh copy, and the log line
is `pre_migration_backup_written` rather than `pre_migration_backup_reused`.

Migration `0007` rewrites every row in `items`. On a library of a few thousand
books it takes well under a second; the log line to look for is
`pre_migration_backup_written`.

## Rolling back

Alembic here is forward-only, so a rollback is a restore plus an older image.
Published images keep every prior tag available, so the image side of a
rollback is a pull rather than a rebuild.

Docker has no way to rename a volume, so this restores into a fresh one and
flips which volume Compose points at, rather than swapping directories on the
host. The volume `data` is currently attached to is left untouched — it's the
rollback point for the rollback, if this ever needs undoing.

```bash
docker compose down
docker run --rm -v akasha_backups:/backups:ro alpine ls /backups   # find the pre-migration copy
docker volume create akasha_data_rollback
docker run --rm --user 10001 \
  -v akasha_backups:/backups:ro -v akasha_data_rollback:/data \
  ghcr.io/mauroibz/akasha:<the-previous-version> akasha-backup restore /backups/pre-migration-<stamp> --into /data
echo "AKASHA_DATA_VOLUME=akasha_data_rollback" >> .env
echo "AKASHA_VERSION=<the-previous-version>" >> .env   # the image that was running before
docker compose up -d
```

`docker run` pulls an image it does not already have, so naming the previous
version is enough — there is nothing to rebuild. If the previous version
predates the published image (v1.5.2 and earlier), fall back to the old
procedure for that one rollback only — `git checkout <previous-tag-or-commit>
&& docker compose -f compose.yaml -f compose.build.yaml up -d --build`.

On `compose.bind-mounts.yaml` (a real `backups/` directory), replace both
`-v akasha_backups:/backups:ro` above with `-v "$PWD/backups:/backups:ro"`, and
`ls backups/` works directly — `akasha-backup restore` itself doesn't care
which kind of mount either side is.

Restore refuses to write into a directory that is not empty, so it cannot
silently overwrite a database you meant to keep. To undo the rollback later,
remove the `AKASHA_DATA_VOLUME` line from `.env` and `docker compose up -d`
again — the volume it names is still there, untouched.

## Nightly backups

Schedule from the host, not from inside the container — the application is one
process and is not a cron daemon.

```cron
15 3 * * *  cd /srv/akasha && BACKUP_RETENTION=7 ./scripts/backup.sh >> backups/akasha-backup.log 2>&1
```

Write the log somewhere you choose — the example uses the checkout's own
`backups/` directory because a host with a read-only root filesystem (several
appliance distributions ship one) has no writable `/var/log`.

`BACKUP_RETENTION` is read by `scripts/backup.sh` from the **process
environment**, and cron does not source `.env`: a value in `.env` is silently
ignored. Set it in the crontab line, as above, or in the environment that
launches cron — the same is true wherever that variable is documented,
including `.env.example`.

`scripts/backup.sh` requires the stack to be running: an online backup reads a
live database through SQLite's backup API rather than copying a WAL file out
from under a writer. Each run writes a directory containing `books.db`,
`manifest.json` and `checksums.sha256`, verifies its own output with
`PRAGMA integrity_check`, and then deletes the oldest `nightly-` backups beyond
`BACKUP_RETENTION` (default 7). Below `AKASHA_MIN_FREE_BYTES` of free space on
the backup destination, the run refuses before writing anything rather than
leaving a partial backup behind.

Covers and attached files are both carried as **hardlinks** — covers in a
`covers/` directory, attachments in `attachments/` — and the manifest lists
each one's name (or digest, for attachments) and size. Neither is tarred and
attachments are not compressed: an epub is already a ZIP, so gzip measured a
ratio of 1.0003 on them while costing ten times the runtime, and a tar shares
no bytes with the one written the night before (DEC-047; covers get the same
treatment as of Sprint 060, DEC-123). Sharing is why seven nights of these cost
about one copy instead of seven. Deleting an expired backup only decrements a
link count, so it can never take a blob another backup still needs — and a
backup keeps a cover or attachment recoverable after you change or delete it in
the library, which is the point of having one.

`/data/imports` — a batch's staging directory while an import is in progress —
is not backed up at all: nothing reads it back after a commit, and the
application collects a committed batch's copy on its own once its 24-hour undo
window passes, with no schedule or `--apply` flag to remember (Sprint 060,
DEC-123).

If `BACKUP_DIR` is on a different filesystem from the data volume — which is the
normal Compose setup — attachment blobs link from the previous backup instead,
so sharing still holds; a copy is only paid on the very first backup to a fresh
disk. Covers do not fall back to a sibling backup the same way, because a cover
is not content-addressed and can be replaced in place — a sibling's copy is not
guaranteed to still be current the way a digest-addressed attachment's is. On a
separate-filesystem `BACKUP_DIR`, every backup gets a fresh copy of each cover
directly from the live store instead, which is no worse than every backup
tarring all of them cost before this sprint.

Check one by hand at any time:

```bash
docker compose exec akasha akasha-backup verify /backups/nightly-<stamp>
```

### Pruning pre-migration backups

The backup taken automatically before a migration (DEC-039) is never touched by
nightly retention — it is the rollback point for that upgrade, and it stays
until you decide otherwise. List what has accumulated, and prune only what you
name:

```bash
docker compose exec akasha akasha-backup prune-pre-migration
# name one or more to actually consider deleting them:
docker compose exec akasha akasha-backup prune-pre-migration pre-migration-20260815T142246Z --apply
```

The newest one and the one matching the database's current schema revision are
refused even if you name them — those are the two DEC-039 exists to protect.
Nothing is deleted without `--apply`, and this command is never called from a
schedule or from `create`.

## Reclaiming attachment space

A blob whose last row goes away is removed with it. A few routes leave one behind
anyway — an item deleted outside the application, a crash between writing the file
and recording the row — and nothing else collects those. This finds them:

```bash
docker compose exec akasha akasha-attachments reclaim
```

It **reports and removes nothing** by default: what it would delete, what it kept
because a row still points at it, and anything under `attachments/` it did not
put there and will not touch. Read that list, then run it again to act on it:

```bash
docker compose exec akasha akasha-attachments reclaim --apply
```

Safe to run at any time, including while the stack is serving. A blob written in
the last hour is never touched, which is what keeps it away from an upload whose
file has landed but whose database row has not been committed yet; pass
`--grace-seconds` if you ever need to narrow that window. A blob a backup has
linked survives this — the backup holds its own reference to the same inode, so
reclaiming the live copy cannot reach the bytes.

There is no schedule for it and it deliberately does not run itself. It deletes
by inference, and inference belongs behind a person.

## Pruning the item cache

Deleting an entry — the detail page's Delete, triage's Discard, an import undo —
leaves its item behind on purpose: the item is the metadata cache that makes
re-adding instant, and since 2.0 it is shared between users, so one person's
discard cannot take the row another person's entry still uses. But nothing
collected the items that lost their *last* entry, so the cache only grew. This
sweep closes that half of the lifecycle:

```bash
docker compose exec akasha akasha-prune prune
```

Like `akasha-attachments reclaim`, it **reports and removes nothing by default**.
An item is a candidate only when no entry of any user references it and no
import record still claims it — a batch inside its undo window can still
resurrect its rows, and an undo that finds them gone would do less than it
promises. With the item go its cover file, its identifiers and sources (which
cascade with the row), and its attachment blobs once no other row shares the
digest. Anything under `covers/` that is not a `{item_id}.jpg` the application
wrote is reported and left alone. Read the list, then act on it:

```bash
docker compose exec akasha akasha-prune prune --apply
```

Safe to run while the stack is serving: SQLite serializes writers, and the
candidate list is read in one pass before any removal begins. Nothing is
scheduled and nothing runs on its own, for the same reason as the attachment
sweep — deletion by inference belongs behind a person.

## Restoring

As with a rollback, this restores into a fresh volume and flips which one
Compose points at, rather than swapping directories on the host — the volume
`data` is currently attached to is left alone.

```bash
docker compose down
docker volume create akasha_data_restored
docker run --rm --user 10001 \
  -v akasha_backups:/backups:ro -v akasha_data_restored:/data \
  ghcr.io/mauroibz/akasha:${AKASHA_VERSION:-latest} akasha-backup restore /backups/nightly-<stamp> --into /data
echo "AKASHA_DATA_VOLUME=akasha_data_restored" >> .env
docker compose up -d
```

On `compose.bind-mounts.yaml`, replace `-v akasha_backups:/backups:ro` above
with `-v "$PWD/backups:/backups:ro"` — `akasha-backup restore` doesn't care
which kind of mount either side is.

Restore verifies every checksum and re-runs `integrity_check` before writing
anything. It needs no configuration at all — not even `USER_AGENT_CONTACT` —
because the restore path deliberately does not build the application. To go
back, remove the `AKASHA_DATA_VOLUME` line from `.env` and `docker compose up
-d` again — the old volume is still there.

### Bind-mounting data and backups

Prefer `./data` and `./backups` as real host directories — a NAS-backed
`BACKUP_DIR`, direct host access to the sqlite file? Opt into
`compose.bind-mounts.yaml`, which brings back the pre-DEC-075 mounts and their
one extra requirement:

```bash
mkdir -p data backups
sudo chown -R 10001:10001 data backups   # the container runs as uid 10001
docker compose -f compose.yaml -f compose.bind-mounts.yaml up -d
```

Use the same two `-f` flags on every subsequent `docker compose` command for
this stack — upgrades, `down`, `logs`, all of it.

### Backups on their own disk

DEC-040 says a backup on the same disk as the database does not survive losing
that disk — and on the default named volumes, both land under the same Docker
data root. `compose.backups-host.yaml` is the shape that closes the gap: it
binds **only** `/backups` to a host path and leaves `/data` the named volume
`compose.yaml` gives it, so the database keeps the seed-with-ownership default
(DEC-075) while backups go to a second disk, a NAS share, anywhere that is not
the database's disk.

```bash
mkdir -p /mnt/second-disk/akasha-backups
sudo chown 10001:10001 /mnt/second-disk/akasha-backups   # the one privileged command this deployment needs
BACKUP_DIR=/mnt/second-disk/akasha-backups docker compose -f compose.yaml -f compose.backups-host.yaml up -d
```

The `chown` prints nothing and exits 0. Compose would create a missing
directory as root:root, which the container's uid 10001 cannot write into —
that is the failure the `mkdir` + `chown` pair exists to prevent, and it fails
at 3am as `attempt to write a readonly database` if skipped.

The compose files, as a set:

| Tier | Files | `/data` | `/backups` | One-time setup |
|---|---|---|---|---|
| 1 — default | `compose.yaml` | named volume | named volume | none |
| 2 — both on host paths | `+ compose.bind-mounts.yaml` | host directory | host directory | `mkdir` + `chown` both |
| 3 — backups on their own disk | `+ compose.backups-host.yaml` | named volume | host directory | `mkdir` + `chown` the backups directory only |

Each overlay is opt-in, invoked explicitly, and never merged in by accident —
none is named `docker-compose.override.yml`. Use the same `-f` flags on every
subsequent `docker compose` command for the stack.

## Turning authentication on

Akasha ships with `AKASHA_AUTH=off`: one shared library, no login, trusted LAN
only. Turning auth on adds accounts — a first-run setup screen, per-user
libraries, 400-day sliding sessions, a sessions screen to revoke a lost device,
and an admin who can manage accounts and (as themselves) look into another
user's library. It changes nothing else: your existing library becomes the
admin's, and no migration is needed beyond the ones the upgrade already runs.

Do it in this order:

1. Put `AKASHA_AUTH=on` in `.env`:

   ```bash
   echo "AKASHA_AUTH=on" >> .env
   docker compose up -d
   ```

2. Open the application. The first visit shows the **setup screen**, not the
   library: choose a username, a display name and a password. This account is
   the admin, and every entry and shelf already in the database becomes theirs —
   nothing is lost, nothing is reassigned by hand.

   Automation instead of the screen (optional): set the paired
   `AKASHA_ADMIN_USERNAME` and `AKASHA_ADMIN_PASSWORD` in `.env` before the
   first auth-on start. Both must be set together or startup refuses. The
   password lives in a plaintext file, so prefer the setup screen unless you
   need this; if you do use it, restrict the file's permissions.

3. Create the second person as the admin: sign in, open **Settings → People**,
   *Add person*. Their library starts empty. Give them the *Admin* flag only if
   you mean it — an admin can reset passwords, rename accounts and look into
   any library.

4. Sign in as them (or hand them the URL) and confirm their library is empty
   and yours is unchanged.

**One expectation to set before the first sign-in.** The library's default view
hides `unsorted` rows — it always has. A library whose imports were never
triaged will look nearly empty on first sight (the inbox/Triage screen holds
them all, and the status filter can include them). If the library looks
smaller than expected after the upgrade, that is the filter, not data loss;
the entry counts in Settings → People name the real totals.

**What each user sees.** Entries, shelves, imports, exports and triage are
private: two people adding the same book create one shared catalogue record
(the cover, the metadata) but separate ratings and notes. Cross-user ids answer
`404`, so one user cannot probe whether another's ids exist.

**When a password is lost.** An admin resets it: Settings → People → the
account → *Reset password*. This signs that account out of every device. The
admin's own password has no second admin to reset it — recovery for it is
restoring a database backup from before it was set and redoing setup, so keep
it in a password manager.

**When a proxy misconfiguration locks everyone out.** Auth-on does not disable
the fallback: if login ever fails because of a proxy (a wrong
`X-Forwarded-Proto`, a stripped cookie), reach the container directly on the
LAN — the published port still serves the ordinary login screen, and password
login is never disabled by the trusted-header settings. Worst case, set
`AKASHA_AUTH=off` in `.env` and `docker compose up -d` again: the account
system stays in the database untouched, and turning auth back on later returns
to exactly this section. An install published on the internet has no LAN port
and must never run with auth off; it has its own recovery path,
[When you are locked out](#when-you-are-locked-out).

**Sessions, and signing a device out.** Each sign-in lasts 400 days and slides
forward while in use, so a regularly used device never asks again
(`AKASHA_SESSION_DAYS` changes the 400; the public overlay sets 30). The
account section (top-right name → *Account*) lists every signed-in device with
its last use and user agent: *Revoke* ends one, *Sign out everywhere* ends
them all. Use it when a phone is lost.

### Running behind `tailscale serve`

Tailscale Serve can assert who is at the other end of the tailnet, which lets a
phone open Akasha signed in already — no login form. It is opt-in and needs
three settings in `.env`:

```ini
AKASHA_AUTH=on
AKASHA_TRUSTED_PROXY_HEADER=Tailscale-User-Login
# the address the access log shows for Serve's requests — see below
AKASHA_TRUSTED_PROXY_PEERS=["172.18.0.1"]
```

- The peer allowlist is the address Akasha sees the proxy coming from — and
  through Docker's port publishing that is usually **not** `127.0.0.1`. A
  connection `tailscale serve` makes to `127.0.0.1:4441` on the host reaches
  the container from the Docker network's gateway (an address such as
  `172.18.0.1`), because Docker forwards it across the bridge. Check before
  trusting: sign in once through Serve, then read the peer address in the
  access log (`docker compose logs akasha | tail`), and put that address in
  the allowlist. Every process on the host that connects to the published
  port arrives from the same gateway, which is one more reason to keep the
  port on loopback. **Akasha refuses to start with a header configured and no
  peer allowlist** — an unbounded allowlist is an authentication bypass, which
  is exactly what the refusal prevents.
- The header value must match a username (it is matched case-insensitively
  after trimming). Your tailnet login `you@example.com` matches a user created
  with that exact name. An unknown identity is refused with `403` unless
  `AKASHA_TRUSTED_HEADER_AUTOCREATE=true` — which creates a fresh non-admin
  account with an empty library and no password on first sight, and is the
  setting to reach for only if you want every tailnet member to get an account.
- Then publish the container on loopback only and let Serve own the ingress:

  ```bash
  # .env
  AKASHA_BIND=127.0.0.1
  # on the host, once
  tailscale serve https / http://127.0.0.1:4441
  ```

- Password login stays available alongside the header. A device that arrives
  without the header (Funnel traffic, a tagged node, a misconfigured proxy)
  gets the ordinary login screen — the two are alternatives, not exclusives,
  so a proxy problem can never lock you out.
- Bind the published port to loopback (or the LAN address only) when the
  header is configured: a caller that reaches the port directly can assert any
  identity, and the peer allowlist only governs what the proxy is allowed to
  claim from that address.
- Tailscale's header name is their contract, not this repository's: if their
  documentation names a different header one day, change
  `AKASHA_TRUSTED_PROXY_HEADER` — it is configuration precisely so a rename
  upstream is an `.env` edit and not a release.

## Reverse proxy

Nginx Proxy Manager on the same LAN, e.g. `books.home.lan` → `http://<host>:4441`.
Do not expose that hostname beyond the LAN, do not forward a port to it, and do
not put it behind a proxy that terminates on a public address — unless all
four exposure conditions hold: `AKASHA_AUTH=on`, TLS terminating in front,
the session cookie `Secure`, and setup completed before the hostname is
published. With auth off there is no login to stop anyone who arrives. For the
internet, prefer the Cloudflare route below to a port forward: it publishes no
port at all.

Whatever the proxy, do not set uvicorn's `FORWARDED_ALLOW_IPS` (and never to
`*`): it would let any client name its own address. Akasha reads a forwarded
scheme, an identity header or a client address header only from the peers in
`AKASHA_TRUSTED_PROXY_PEERS`.

Set `AKASHA_BIND=127.0.0.1` if the proxy runs on the same machine, so the
container port is not reachable from the network directly. And note what
`0.0.0.0` publishes on: a host that has joined a VPN or mesh network
(WireGuard, Tailscale, ZeroTier and the like) carries an extra interface, and
`AKASHA_BIND=0.0.0.0` publishes on that one too — a port reachable from
outside the building without anyone having forwarded anything. The way to
exclude it is to bind `AKASHA_BIND` to one address rather than to
everything. The property belongs to overlay networks generally, not to any
particular one.

For Tailscale specifically — including the zero-tap identity-header login —
see [Running behind `tailscale serve`](#running-behind-tailscale-serve) above.

## Publishing on the internet (Cloudflare Tunnel and Access)

This is how to open Akasha at a name such as `https://akasha.example.com` from
anywhere, without forwarding a port on the router and without putting the rest
of the home server at risk (DEC-180). It takes about an hour the first time.
Do the steps in order; each one assumes the ones before it.

The shape of it: a visitor reaches Cloudflare. **Cloudflare Access** asks who
they are (a code mailed to an allowed address, or a Google sign-in) and turns
everyone else away. What Access lets through travels down a **Cloudflare
Tunnel** — an outbound connection that a small `cloudflared` container on your
server keeps open to Cloudflare — to the Akasha container, which then shows its
own login. Nothing on your server listens on the internet, and the router stays
closed.

### What you need

- A domain whose DNS is managed by Cloudflare (a free account is enough).
- Docker Compose 2.24 or later on the server (`docker compose version`).
- Some time in the Cloudflare dashboard. Its menus get renamed now and then;
  the names below are the ones it used when this was written, and the things
  to look for stay the same whatever they are called.

### 1. Finish setup on the LAN first

The fourth exposure condition: the admin account exists before the hostname
does. Whoever completes setup becomes the admin and owns the library.

```bash
echo "AKASHA_AUTH=on" >> .env
docker compose up -d
docker compose logs akasha | grep -i setup     # the one-time setup code
```

Open `http://<server>:4441` on the LAN, enter the setup code from the log, and
create the admin with a long password from a password manager (new passwords
need at least 12 characters). Sign out and in once to check it works.

### 2. Create the tunnel

In the Cloudflare dashboard, open **Zero Trust → Networks → Tunnels** and create
a tunnel of type **Cloudflared**, named `akasha`. When it offers install
commands, choose **Docker** and copy only the long token after `--token`. Do not
run the command it shows: `compose.public.yaml` runs `cloudflared` for you,
hardened.

Put the token in `.env` and make the file readable by you alone — whoever holds
the token can serve your hostname:

```bash
echo "TUNNEL_TOKEN=<the token>" >> .env
chmod 600 .env
```

Then add the tunnel's **public hostname** (also called a *published application
route*): subdomain `akasha`, your domain, service type **HTTP**, URL
`akasha:8000`. `akasha` is the application container's name on the private
network it shares with `cloudflared`.

### 3. Put Cloudflare Access in front of the whole hostname

Open **Zero Trust → Access → Applications** and add a **Self-hosted**
application:

- **Domain:** `akasha.example.com`, with the path left **empty**, so it covers
  every page and every API route. Add no second, narrower application and no
  *Bypass* policy for any path: an exception is a door around the gate.
- **Session duration:** how often Access asks again. 24 hours is a sensible
  start; a week is fine for a household.
- **Login methods:** **One-time PIN** (a code mailed to the address) needs no
  setup; **Google** works too once added under *Settings → Authentication*.
- **Policy:** action **Allow**, include **Emails**, listing each person's
  address. Never *Everyone*, and never a whole email domain such as
  `gmail.com`.

Save, then copy two values into `.env`: the application's **Application
Audience (AUD) Tag**, from its overview, and your **team domain**,
`<team>.cloudflareaccess.com`, from *Settings → Custom Pages* (it is also in the
address bar of the Access sign-in page).

```ini
AKASHA_CF_ACCESS_TEAM_DOMAIN=<team>.cloudflareaccess.com
AKASHA_CF_ACCESS_AUD=<the AUD tag>
```

With these two set, Akasha checks Cloudflare's signature on every request
itself and refuses anything Access did not sign (`403 access_denied`). A
mistake in the Access configuration, or another container on the server, then
still cannot reach the login screen around Access. The container's own
healthcheck is the one request exempt from it.

### 4. Start the public stack

```bash
docker compose -f compose.yaml -f compose.public.yaml up -d
docker compose -f compose.yaml -f compose.public.yaml ps   # akasha healthy, cloudflared up
```

Every later command for this install names both files the same way — or put
`COMPOSE_FILE=compose.yaml:compose.public.yaml` in `.env` and leave them out,
which also keeps `scripts/backup.sh` and upgrades on the right files.

The overlay publishes **no port**: `http://<server>:4441` stops answering on the
LAN, on purpose. It also forces `AKASHA_AUTH=on`, a `Secure` cookie and
`AKASHA_METRICS=off`, and reads each visitor's address from Cloudflare's
`CF-Connecting-IP` header — believed only from the `cloudflared` container — so
the login limiter counts each visitor separately rather than all of them as one.

Check from a private browser window: `https://akasha.example.com` shows
Cloudflare's sign-in first, then Akasha's. The tunnel shows *Healthy* in the
dashboard. Then check that the application's own gate is on — a request that
did not come through Access must be refused:

```bash
docker run --rm --network akasha_ingress --entrypoint python \
  ghcr.io/mauroibz/akasha:2.8.0 -c \
  "import urllib.request as u; u.urlopen('http://akasha:8000/api/auth/me')"
# expected: urllib.error.HTTPError: HTTP Error 403: Forbidden
```

(Use the version you run in place of `2.8.0`.)

### 5. Keep the containers off the LAN

A container can, by default, reach everything the server can: the router's admin
page, the NAS, the Tailscale network, the server's own services.
`scripts/akasha-egress-firewall.sh` narrows that for the two public containers
to what they need — Akasha to web sites (metadata, covers) and DNS, `cloudflared`
to Cloudflare — and refuses new connections from them to the server itself.

```bash
sudo scripts/akasha-egress-firewall.sh --dry-run   # read what it will do
sudo scripts/akasha-egress-firewall.sh
sudo iptables -L AKASHA-EGRESS -n -v               # the rules, with counters
```

It needs Docker's default iptables firewall; with `ufw` or `firewalld` managing
the host, read its comments and translate the rules rather than run it. It
relies on IPv6 staying off on these networks, which the overlay sets.

The rules vanish on reboot. Make them permanent with a systemd unit — edit the
path to where the repository lives. The script runs as root, so keep it owned by
root and writable by no one else:

```ini
# /etc/systemd/system/akasha-egress-firewall.service
[Unit]
Description=Akasha egress firewall
After=docker.service
Requires=docker.service
PartOf=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/opt/akasha/scripts/akasha-egress-firewall.sh
ExecStop=/opt/akasha/scripts/akasha-egress-firewall.sh --remove

[Install]
WantedBy=docker.service
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now akasha-egress-firewall
```

Check it from inside the application container: your router's address must be
refused, a public site must answer.

```bash
docker compose -f compose.yaml -f compose.public.yaml exec akasha python -c \
  "import socket; socket.create_connection(('192.168.1.1', 80), 3)"   # refused
docker compose -f compose.yaml -f compose.public.yaml exec akasha python -c \
  "import urllib.request as u; print(u.urlopen('https://openlibrary.org').status)"   # 200
```

### 6. Cloudflare settings for this hostname

- **Rate-limit the login.** *Security → WAF → Rate limiting rules*: when the URI
  path equals `/api/auth/login` and the method is `POST`, block an address that
  exceeds about 5 requests a minute. The free plan offers shorter periods; pick
  the longest it allows. Akasha limits sign-in attempts itself as well; this
  stops a flood before it reaches the server.
- **Never cache the application.** No *Cache Everything* cache rule or page rule
  on this hostname. The API answers `no-store`, but such a rule overrides it and
  could serve one person's library to another.
- **Leave the page's scripts alone.** Turn off *Rocket Loader* and *Email
  Address Obfuscation* for this hostname (a *Configuration Rule* does it per
  hostname): both inject scripts, which Akasha's Content-Security-Policy blocks.
- **Always Use HTTPS** on.

### 7. Backups go where the server cannot delete them

If the application were ever taken over, whoever held it could delete
`/backups` too: the application writes there, so it can. A backup that survives
that lives on another machine and is **pulled** from the server, never pushed
by it — for example a NAS or another computer that copies the backups volume
over SSH every night (`rsync`, see [Nightly backups](#nightly-backups)) and
keeps dated snapshots on its own side. The server holds no credential for that
machine.

### When you are locked out

If Cloudflare, the tunnel or a policy breaks, reach Akasha from the server
itself. Start it without the public overlay, on the server's loopback only, and
with the Access check off for this run:

```bash
AKASHA_BIND=127.0.0.1 AKASHA_CF_ACCESS_TEAM_DOMAIN= AKASHA_CF_ACCESS_AUD= \
  docker compose -f compose.yaml up -d --remove-orphans
```

From your computer, `ssh -L 4441:127.0.0.1:4441 <server>` and open
`http://localhost:4441`: the ordinary login screen. When done, run step 4's
command again; it removes the loopback port and restores the Access check.

### What each layer protects

| Layer | Stops |
|---|---|
| Cloudflare Access | Strangers: they never see Akasha's login page. |
| Akasha's own Access check (`AKASHA_CF_ACCESS_*`) | A request that went around Access: a policy mistake, another container on the server. |
| Akasha's login | Someone Access let in who has no Akasha account; guesses are counted and limited per visitor. |
| Setup before publishing, and the setup code | A stranger claiming the first admin account. |
| No published port | Anyone on the LAN or the internet reaching the container directly. |
| Read-only, unprivileged container | A compromised application rewriting its own code or gaining privileges. |
| Egress firewall | A compromised application reaching the router, the NAS, Tailscale or the server. |
| Pulled, off-host backups | A compromised application deleting the library and its backups together. |

None of these stands alone, and none is a reason to skip another.

### Watching for attacks

Every refusal at Akasha's own door leaves one JSON line with
`"category": "security"`: `login_failed`, `login_rate_limited`,
`login_succeeded`, `setup_code_invalid`, `setup_rate_limited`,
`password_change_failed`, `password_change_rate_limited` and
`cross_site_request_refused`, each with the `client` address the limiter used
and, for logins, the `username` tried (never a password). Requests refused by
the Access check log `cloudflare_access_refused`.

```bash
docker compose logs akasha | grep '"category": "security"'
```

A burst of `login_failed` from one address, or `login_succeeded` from an
address you do not recognise, is the reason to look at *Account → Sessions*
and revoke. These lines are what a log alert or fail2ban filter should match.

## Metrics

Set `AKASHA_METRICS=on` in `.env` and restart to serve Prometheus text at `/metrics`. It reports
jobs waiting or running, jobs by kind and state, provider calls by outcome with time spent, and
API request latency by route template. Provider counters reset when the process restarts.

With `AKASHA_AUTH=off` the route is open to whoever reaches the port, and it names providers and
routes: scrape it from the LAN and do not proxy it to the internet. With auth on it answers only an
admin's session (Sprint 128), so a Prometheus scraper cannot read it there. A public install keeps it off; `compose.public.yaml`
forces `AKASHA_METRICS=off`.

*Search is running on fewer providers* on the Add page now also names a configured provider that
has stopped answering. That is a provider outage, not a fault in Akasha: searches keep working on
the other providers, and the notice clears once the provider answers again.

## Durability and caching (Sprint 129)

- **Upgrades are one transaction.** A migration that fails leaves the database at the
  revision it started from, so the next start retries cleanly instead of looping on a
  half-applied schema.
- **SQLite runs `synchronous=NORMAL` under WAL.** A power cut can lose the last few
  commits but cannot corrupt the database. Covers and attachment files are synced to
  disk before the rows that point at them commit, and a damaged attachment blob is
  replaced when the same file is uploaded again.
- **Interrupted imports finish themselves.** Covers and ebooks are installed after an
  import commits; if the process dies part-way, the next start completes the install.
  A batch's staging folder is never removed while it still holds uninstalled files (the
  log says `import staging kept`, retried once an hour).
- **Jobs:** a cancelled job stays cancelled; a job whose lease keeps expiring (it
  crashes the process) is failed with `lease_expired` after its retries.
- **Stopping** takes well under ten seconds even with a tab open (`/api/events` ends at
  shutdown; uvicorn's graceful shutdown is bounded at 10 s).
- **Caching and compression:** `/assets/*` is immutable for a year (file names carry a
  content hash); the page shell, `sw.js` and `theme-init.js` revalidate every load.
  Responses over 1 KB are gzip-compressed, except images, downloads and `/api/events`.
  A reverse proxy or Cloudflare can pass compressed responses through unchanged.

## When something is wrong

| Symptom | Cause |
|---|---|
| `attempt to write a readonly database` | on `compose.bind-mounts.yaml` only: `data/` is not owned by 10001 |
| Startup exits with `Refusing to migrate without a backup` | on `compose.bind-mounts.yaml` or `compose.backups-host.yaml`: `backups/` is missing or not owned by 10001 |
| `/api/health/ready` returns 503 `schema_not_current` | migrations have not finished, or failed; check the logs |
| Search finds nothing and the UI says degraded | no `GOOGLE_BOOKS_API_KEY`, or no outbound network |
| The backup script says the service is not running | start the stack; an online backup needs a live database |
| Every request answers `403 access_denied` | `AKASHA_CF_ACCESS_*` is set and the request did not carry a valid Cloudflare Access token: a wrong AUD tag or team domain, the hostname not covered by the Access application, or a request that did not come through Cloudflare. The log line `cloudflare_access_refused` names the reason |
| `Read-only file system` in the logs | something wrote outside `/data`, `/backups` and `/tmp`; the root filesystem is read-only since Sprint 128. Report it; as a stopgap, `read_only: false` in an override file |
| `cloudflared` keeps restarting | `TUNNEL_TOKEN` is missing or wrong; `docker compose -f compose.yaml -f compose.public.yaml logs cloudflared` says which |

On the default named-volume mounts, neither ownership row above is reachable —
there's no host directory to get wrong. Bring a host directory in for either
mount (`compose.bind-mounts.yaml`, or `compose.backups-host.yaml` for backups
only) and its row becomes reachable for that mount.

Logs are JSON, one object per line: `docker compose logs -f akasha`. Notes,
review text, import rows and API keys are redacted before they are written.
