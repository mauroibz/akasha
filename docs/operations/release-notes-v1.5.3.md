# Akasha v1.5.3 — release notes

The published-image release, from Sprint 058: how the software is obtained changes, and
nothing about the application does. No migration, no screen, no request path. `books.db`,
covers, attachments and backups are all untouched — this release changes the box the
container comes in, not what is inside it.

## Read this first if you already run Akasha

**Every install has been a build until now.** `compose.yaml` carried `build: .`, so an
upgrade meant a source checkout, a working Node and Python toolchain, and reachable npm,
PyPI and Docker Hub — plus a full frontend build on every upgrade. From this release,
`compose.yaml` points at a published image and carries no `build:` key at all.

**If your `.env` or shell already exports `AKASHA_VERSION`, nothing changes yet** — `up -d`
still needs an image with that tag, and until you `docker compose pull` there is nothing
new to fetch.

**To move onto the published image:**

```bash
echo "AKASHA_VERSION=1.5.3" >> .env
docker compose pull
docker compose up -d
```

`git pull` is no longer part of the normal upgrade path. If you keep the repository
checked out anyway — for the local-build overlay, or to read the docs — pulling it stays
harmless; it just isn't required to upgrade any more.

**Building from source is still supported**, for a fork, a local patch, or an architecture
other than the published `linux/amd64`:

```bash
git pull
docker compose -f compose.yaml -f compose.build.yaml up -d --build
```

## What's new since v1.5.1

- **A published image.** `ghcr.io/mauroibz/akasha` is built and pushed by
  `.github/workflows/release.yml` on every `v*` tag, tagged with the full version, the
  minor line, and `latest`. See
  [`docs/operations/publishing-images.md`](publishing-images.md) for how it works and how
  to verify one.
- **Compose is pull-based.** `compose.yaml`'s `image:` is now a registry reference,
  `ghcr.io/mauroibz/akasha:${AKASHA_VERSION:-1.5.3}`, and no longer carries `build:`. The
  local build moved to its own overlay, `compose.build.yaml` — a service naming both
  `image:` and `build:` builds silently instead of pulling when the local image is
  missing, which is the trap this split removes.
- **Base images are pinned by digest.** Both `Dockerfile` `FROM` lines now pin
  `tag@sha256:…` rather than a floating tag, so a rebuild months from now gets exactly the
  same bytes. The refresh procedure is a comment above the first `FROM` line.
- **Dependency updates arrive as pull requests.** `.github/dependabot.yml` covers npm,
  the Python project, the Dockerfile's base images and GitHub Actions, weekly. CI's
  existing `checks`, `e2e` and `container` jobs gate every one automatically.
- **The Quick start no longer clones the repository.** `README.md` fetches `compose.yaml`
  and `.env.example` directly and pulls the image; cloning is now the source-build path.
- **The runbook's "Upgrading" and "Rolling back" sections are pull-based.** A rollback
  names a previous version and `docker run`/`docker compose pull` fetches it — there is
  nothing to rebuild, as long as the version predates this release's own switch.

## Upgrading

```bash
echo "AKASHA_VERSION=1.5.3" >> .env
docker compose pull
docker compose up -d
```

Nothing migrates and no data volume moves. If a previous version was never published (any
version up to and including v1.5.2), a rollback to it still needs the old build path —
`git checkout <tag> && docker compose -f compose.yaml -f compose.build.yaml up -d --build`
— for that one rollback only; every version from here on rolls back with a pull.

## What this release deliberately does not do

- **Authentication.** Unchanged, and still not on the roadmap.
- **Multi-architecture images.** The published image is `linux/amd64` only; another
  architecture uses the local-build overlay.
- **Signing, SBOMs or provenance attestation.** Not built here.
- **Automatic deployment.** The workflow publishes; nothing pushes, deploys or restarts
  anything on a server. `docker compose pull` stays a person's decision.
