# Publishing images

**Status:** canonical

How `ghcr.io/mauroibz/akasha` gets built and published, how to verify a published
image, and the one-time GitHub account setup only the repository owner can perform.

## What the workflow does

`.github/workflows/release.yml` runs on every push of a tag matching `v*` — never on a
branch push or a pull request. It:

1. checks out the tagged commit;
2. derives three tags from the pushed tag name — the full version (`1.5.3`), the minor
   line (`1.5`), and `latest`;
3. logs in to `ghcr.io` with the workflow's own `GITHUB_TOKEN`, scoped to this run by
   `permissions: packages: write` — **no personal access token or repository secret is
   created for this**;
4. builds the repository's own `Dockerfile` — the same one `.github/workflows/ci.yml`'s
   `container` job already smoke-tests on every push, so there is no second definition of
   the image — and pushes it under all three tags, carrying
   `org.opencontainers.image.source` so the package links back to this repository.

## What a release looks like, end to end

1. Everything intended for the release is on `main`, `make check` and `make test` are
   green, and `bash scripts/smoke_container.sh` passes against the frozen tree.
2. Bump the version surfaces if a sprint has not already done it (`backend/pyproject.toml`,
   `frontend/package.json`, `main.py`'s FastAPI `version=`) and regenerate
   `frontend/openapi.json` (`make openapi`).
3. Tag and push — see "Push a version tag" below. This is an owner action.
4. Watch the *Actions* tab for the `Release` run. A green run's log ends with the pushed
   tags: `1.5.3`, `1.5`, `latest`.
5. Update `AKASHA_VERSION` in the runbook's examples and this release's
   `docs/operations/release-notes-vX.Y.Z.md` if the version changed.

## Verifying a published image

From a machine with only Docker installed — no source tree, no source-checkout-only
`compose.build.yaml` overlay needed:

```bash
docker pull ghcr.io/mauroibz/akasha:1.5.3
docker inspect ghcr.io/mauroibz/akasha:1.5.3 --format '{{json .Config.Labels}}'
```

The labels include `org.opencontainers.image.source`, pointing at this repository. To run
it, fetch `compose.yaml` and `.env.example` the way the README's Quick start does, then
`docker compose pull && docker compose up -d` — see the main
[README](../../README.md#quick-start).

## The owner actions

Three things can only be done by the account that owns the repository. The workflow can
publish without a single secret being created — these are the exceptions.

### 1. Allow the workflow to write packages

GitHub → the repository → **Settings** → **Actions** → **General** → **Workflow
permissions**. The publish job requests `packages: write` explicitly, which is normally
sufficient on its own; if the first release run fails with a `403` or `denied` from
`ghcr.io`, this setting is why.

**Expected result:** the release run's `docker/login-action` step succeeds and the push
step reports a digest.

### 2. Push a version tag, and watch the run

```bash
git tag v1.5.3
git push origin v1.5.3
```

Then open the *Actions* tab.

**Expected result:** one workflow run named for the tag, green, whose log ends with the
pushed tags `1.5.3`, `1.5` and `latest`.

### 3. Decide the package's visibility, once

A package published by a workflow starts **private**, even when the repository is public.
On the package's *Package settings* page, either:

- **change visibility to public** — the recommendation, since the repository and its
  licence already are, and it means a server pulls with no credentials at all; or
- **leave it private** and accept that every machine that pulls needs
  `docker login ghcr.io` with a token carrying `read:packages`.

**Expected result for the public path:** `docker pull ghcr.io/mauroibz/akasha:1.5.3`
succeeds from a machine that has never authenticated to GHCR.

**If the answer is "private":** every server that runs this needs the login procedure
below, and the credential then lives on each of them.

```bash
# On each machine that pulls a private package, once:
echo "<a token with read:packages>" | docker login ghcr.io -u <github-username> --password-stdin
```

## Refreshing a base image digest

Both `FROM` lines in the `Dockerfile` pin `tag@sha256:…`. Refresh one with:

```bash
docker pull <tag>
docker inspect --format '{{index .RepoDigests 0}}' <tag>
```

Update the digest in the `Dockerfile`, and the human-readable tag beside it if the tag
itself moved (`node:22-alpine` → `node:24-alpine`). Dependabot's `docker` ecosystem
(`.github/dependabot.yml`) proposes this automatically as a pull request; CI's `checks`,
`e2e` and `container` jobs gate it like any other change.

## Non-scope

- **Multi-architecture images.** The published image is `linux/amd64` only. The
  local-build overlay (`compose.build.yaml`) is the path for another architecture.
- **Signing, SBOMs and provenance attestation.** Not built here.
- **Automatic deployment.** Nothing in the release workflow pushes, deploys or restarts
  anything on a server. Publishing is where CI stops; `docker compose pull` is a person's
  decision.
