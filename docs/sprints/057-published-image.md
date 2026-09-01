# Sprint 057 — An image you pull, not a build you run

**Status:** ready
**Depends on:** 056

**Roadmap revision:** 30

## Objective

An upgrade becomes `docker compose pull && docker compose up -d`: seconds, no toolchain, no network
weather, and a previous version that is still sitting there to go back to.

Today every install of this application is a build. `compose.yaml` carries `build: .`, so the machine
running it needs the source tree, a Node toolchain, a Python toolchain and reachable npm, PyPI and
Docker Hub, and it pays a full frontend build for every upgrade. The artifact that CI already
verifies is thrown away and rebuilt on the server instead of being the thing that ships.

## Required context

- `.github/workflows/ci.yml` — the three jobs that exist, and where a publish job belongs relative
  to them.
- `Dockerfile` — the three stages, and its base images: `node:22-alpine` and `python:3.12-slim`, both
  floating tags today.
- `compose.yaml` and Sprint 056's `image: akasha:${AKASHA_VERSION:-local}`, which this sprint
  replaces with a registry reference.
- `docs/operations/runbook.md`'s "Upgrading" and "Rolling back" sections, rewritten here.
- `scripts/smoke_container.sh` — it builds locally by design; this sprint must keep it able to.
- `docs/decisions.md`: DEC-075 (named volumes), and Sprint 018's release procedure.
- `README.md`'s quick start, which currently begins with `git clone`.

## Current implementation baseline

To be confirmed at activation. As observed 2026-09-01:

- CI runs `checks`, `e2e` and `container` on every push and pull request. **Nothing publishes
  anything.** There is no release workflow and no registry account in use.
- `compose.yaml` has `build: .`. An upgrade is `git pull && docker compose up -d --build`, which is
  what `docs/operations/runbook.md` documents.
- Base images are floating tags. A rebuild months later silently takes whatever `node:22-alpine`
  and `python:3.12-slim` point at that day, which is the opposite of the reproducibility the rest of
  the build has — `uv.lock` and `package-lock.json` are both committed and both used with
  `--frozen`/`ci`.
- There is no `.github/dependabot.yml` and no other dependency-update automation.
- The repository is public, and tags `v1.0.0` through `v1.5.0` are pushed.

## Deliverables

### 1. A publish job, on a tag

A workflow that builds the image once and pushes it to GHCR when a `v*` tag is pushed. It must:

- run only on a tag, never on a branch push or a pull request;
- authenticate with the workflow's own `GITHUB_TOKEN` under `permissions: packages: write`, so that
  **no personal access token or repository secret is created for it**;
- tag the result with the full version, the minor line and `latest` — `1.5.2`, `1.5`, `latest` — so
  an operator can pin as tightly as they like;
- carry OCI labels, `org.opencontainers.image.source` among them, which is what links the published
  package back to this repository;
- be the same `Dockerfile` the `container` job already smoke-tests. There must not be a second
  definition of the image.

### 2. Compose points at the published image; the local build stays available

`compose.yaml` becomes pull-based: a registry reference with the version as a variable, defaulting to
a released tag. The local build moves to its own overlay — `compose.build.yaml` — so
`docker compose -f compose.yaml -f compose.build.yaml up -d --build` is the development and
unsupported-architecture path.

`scripts/smoke_container.sh` must keep testing **the built image**, since its whole purpose is to
prove the artifact before it ships. Point it at the build overlay explicitly.

The trap worth naming: a compose service carrying both `image:` and `build:` builds silently when the
image is missing locally, so an operator who thinks they are pulling gets a build instead — and
learns this only on a machine that cannot do one. Splitting the two files is what makes the
distinction honest.

### 3. Base images pinned by digest

Both `FROM` lines pin `tag@sha256:…`, keeping the human-readable tag beside the digest so the line
still says what it is. Document the refresh procedure — where the digest came from and the one
command that produces a new one — as a comment in the `Dockerfile` and a line in the runbook.

### 4. Dependency updates arrive as pull requests

`.github/dependabot.yml` covering the four ecosystems this repository actually has: npm
(`frontend/`), the Python project (`backend/`), Docker (the `Dockerfile`'s base images) and GitHub
Actions. Weekly is right for a project this size; group patch updates so the noise stays proportional
to the attention available.

CI already gates every one of those pull requests with `checks`, `e2e` and `container`, which is what
makes them safe to act on. That is the point: the value is not the notification, it is that the
existing gates run against the update before anyone reads it.

### 5. The runbook's upgrade path is a pull

Rewrite "Upgrading" and "Rolling back" around `docker compose pull`, pinning `AKASHA_VERSION`, and
going back by naming an older tag — no `git pull` and no rebuild in the normal path. Keep the
pre-migration backup paragraph exactly as it is; DEC-039 is unchanged by any of this.

`README.md`'s quick start gets the same treatment: the supported install stops being a clone.

### 6. `docs/operations/publishing-images.md`

A short canonical operations document: what the publish workflow does, what a release looks like end
to end, how to verify a published image, and the one-time account setup that only the owner can
perform (deliverable 7). Add it to the canonical table in `docs/README.md`.

### 7. The owner actions, written out

The workflow can publish without a single secret being created, but three things can only be done by
the account that owns the repository. They belong in `docs/operations/publishing-images.md` in
exactly this shape — what it does, the exact step, and what a correct result looks like:

1. **Allow the workflow to write packages.** GitHub → the repository → *Settings* → *Actions* →
   *General* → *Workflow permissions*. The publish job requests `packages: write` explicitly, which
   is normally sufficient; if the first release run fails with a `403` or `denied` from `ghcr.io`,
   this setting is why. Expected result: the release run's `docker/login-action` step succeeds and
   the push step reports a digest.
2. **Push a version tag, and watch the run.** `git tag v1.5.2 && git push origin v1.5.2`, then the
   *Actions* tab. Expected result: one workflow run named for the tag, green, whose log ends with
   the pushed tags `1.5.2`, `1.5` and `latest`.
3. **Decide the package's visibility, once.** A package published by a workflow starts **private**
   even when the repository is public. On the package's *Package settings* page, either change
   visibility to public — the recommendation, since the repository and its licence already are, and
   it means a server pulls with no credentials at all — or leave it private and accept that every
   machine that pulls needs `docker login ghcr.io` with a token carrying `read:packages`. Expected
   result for the public path: `docker pull ghcr.io/<owner>/akasha:1.5.2` succeeds from a machine
   that has never authenticated.

If the answer to step 3 is "private", the document must also carry the login procedure and say
plainly that the credential then lives on every server that runs this.

### 8. Release notes for v1.5.2

`docs/operations/release-notes-v1.5.2.md`. This release changes how the software is obtained, so the
notes carry the migration for an existing install: how to stop building and start pulling, and that
the data volumes are untouched by the switch.

## Acceptance criteria

1. Pushing a `v*` tag publishes an image; pushing a branch or opening a pull request does not.
2. The published image carries `1.5.2`, `1.5` and `latest`, and its labels include
   `org.opencontainers.image.source` pointing at this repository.
3. A machine with only Docker installed — no source tree, no Node, no Python — can run the
   application from the published `compose.yaml` and reach a healthy container.
4. `docker compose pull && docker compose up -d` upgrades between two published versions and the
   library survives it, proved by reading an entry written before the upgrade.
5. Pinning `AKASHA_VERSION` to the previous version and running `up -d` rolls back without a build.
6. No personal access token, deploy key or repository secret was created for any of the above.
7. `make smoke-container` still builds and exercises the image locally, through the build overlay.
8. Both `FROM` lines are digest-pinned, and the procedure for refreshing a digest is written down.
9. Dependabot opens pull requests for all four ecosystems, and CI's existing jobs run on them.
10. `docs/operations/publishing-images.md` exists, is listed in `docs/README.md`, and its owner
    actions have been performed and their results recorded in the Outcome.

## Required tests (TDD)

CI configuration is not unit-testable, and pretending otherwise wastes the sprint. The evidence is
executable instead, and the Outcome records the actual results:

- **A real publish.** The first release run is the test. Record the run, the digest and the tags.
- **A pull-only install.** Bring the stack up on a clean Docker context from the published image with
  no build context available at all — the honest way to prove criterion 3 is to run it somewhere the
  source tree is not.
- **An upgrade and a rollback between two published versions**, with an entry written before the
  upgrade and read after both moves.
- **`make smoke-container` unchanged in outcome**, proving the build path still works after the file
  split.
- A negative for criterion 1: a push to a branch after the workflow lands produces no package
  version.

## Verification

```bash
python scripts/validate_project.py
make check
make smoke-container
docker compose config                    # the registry reference and the resolved tag
docker pull ghcr.io/<owner>/akasha:<version>
docker compose pull && docker compose up -d
```

Plus the GitHub Actions run for the release tag, referenced by run id in the Outcome.

**This sprint declares a narrowed gate**, on the same terms as Sprint 056: its diff is
`.github/`, `compose*.yaml`, `Dockerfile`, `scripts/smoke_container.sh` and documentation, and
**`make test` and `npm run test:e2e` are not owed**. The digest pin is the case worth stating —
it changes the runtime environment, and `make test` cannot see that, because the suites run on the
host and not inside the image. `make smoke-container` can, and does.

CI's own `checks` and `e2e` jobs still run on every push in this sprint as they do in every other, so
the full suites are executed by the pipeline regardless; what the narrowing removes is a session
running them a second time by hand against a diff they cannot reach.

Same proof obligation: `git diff --stat` in the Outcome, and any file under `backend/src/` withdraws
the narrowing.

## Explicit non-scope

- **Multi-architecture images.** Ship `linux/amd64` and say so. Building `arm64` under emulation for
  a Node-plus-Python image is slow enough to need its own justification, and the build overlay is
  the answer for anyone on another architecture until someone actually needs one. Record the
  decision rather than leaving it implied.
- **Signing, SBOMs and provenance attestation.** Worth having eventually, not the thing standing
  between this project and a two-second upgrade.
- **Automatic deployment.** Nothing in this sprint may push, deploy or restart anything on a server.
  Publishing is where CI stops; `docker compose pull` is a person's decision.
- **A public release announcement, a Docker Hub mirror, or documentation aimed at strangers.**
- Auth, the event loop (Sprint 058), and disk housekeeping (Sprint 059).

## Commit checkpoints

1. `[ADD] Publish the image on a version tag`
2. `[CHANGE] Compose pulls; the build moves to its own overlay`
3. `[CHANGE] Pin the base images by digest`
4. `[ADD] Dependency updates arrive as pull requests`
5. `[DOCS] The upgrade is a pull, and how to publish one`
6. `[DOCS] Release notes for v1.5.2`
7. `[DOCS] Close sprint 057 and hand off`

## Risks and decisions to surface

- **The image name is permanent in practice.** `ghcr.io/<owner>/akasha` is what every install will
  carry; changing it later means every operator edits a file. Settle it before the first push.
- **A service with both `image:` and `build:` builds silently when the image is absent.** That is the
  failure this sprint is meant to remove, and it would arrive disguised as success. The file split is
  the mitigation and criterion 3 is the proof.
- **Package visibility is the owner's decision and cannot be made by an agent.** A private package
  puts a credential on every server that runs this. Ask, do not assume; the recommendation is public.
- **`latest` is a convenience and a hazard.** An operator who never pins gets a major version they did
  not choose. Recommend a pinned `AKASHA_VERSION` in the runbook and say what `latest` is for.
- Digest pinning means a base-image security update arrives only when someone refreshes the digest.
  Dependabot's Docker ecosystem is what closes that loop; verify it actually opens the pull request
  rather than assuming it.

## Outcome

_Not started. On completion record delivered behavior, commands and actual results, commit IDs, deviations/decisions, and impact on every future sprint._
