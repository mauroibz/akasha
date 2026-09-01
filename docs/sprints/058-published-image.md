# Sprint 058 — An image you pull, not a build you run

**Status:** blocked
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
- tag the result with the full version, the minor line and `latest` — `1.5.3`, `1.5`, `latest` — so
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
2. **Push a version tag, and watch the run.** `git tag v1.5.3 && git push origin v1.5.3`, then the
   *Actions* tab. Expected result: one workflow run named for the tag, green, whose log ends with
   the pushed tags `1.5.3`, `1.5` and `latest`.
3. **Decide the package's visibility, once.** A package published by a workflow starts **private**
   even when the repository is public. On the package's *Package settings* page, either change
   visibility to public — the recommendation, since the repository and its licence already are, and
   it means a server pulls with no credentials at all — or leave it private and accept that every
   machine that pulls needs `docker login ghcr.io` with a token carrying `read:packages`. Expected
   result for the public path: `docker pull ghcr.io/<owner>/akasha:1.5.3` succeeds from a machine
   that has never authenticated.

If the answer to step 3 is "private", the document must also carry the login procedure and say
plainly that the credential then lives on every server that runs this.

### 8. Release notes for v1.5.3

`docs/operations/release-notes-v1.5.3.md`. This release changes how the software is obtained, so the
notes carry the migration for an existing install: how to stop building and start pulling, and that
the data volumes are untouched by the switch.

## Acceptance criteria

1. Pushing a `v*` tag publishes an image; pushing a branch or opening a pull request does not.
2. The published image carries `1.5.3`, `1.5` and `latest`, and its labels include
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
- Auth, the event loop (Sprint 059), and disk housekeeping (Sprint 060).

## Commit checkpoints

1. `[ADD] Publish the image on a version tag`
2. `[CHANGE] Compose pulls; the build moves to its own overlay`
3. `[CHANGE] Pin the base images by digest`
4. `[ADD] Dependency updates arrive as pull requests`
5. `[DOCS] The upgrade is a pull, and how to publish one`
6. `[DOCS] Release notes for v1.5.3`
7. `[DOCS] Close sprint 058 and hand off`

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

**Blocked 2026-09-01, same session that implemented it.** Every deliverable that does not
require the repository owner's GitHub account or a push to `origin` is built and verified.
Acceptance criterion 10 requires the three owner-only steps to be **performed**, not merely
documented, and criteria 1, 2, 4, 5, 6 and 9 depend on a real publish those steps unlock —
see DEC-120. This repository's standing rule that nothing is pushed to `origin` without the
owner asking (unchanged since Sprint 057's close) applies to the tag push named in
deliverable 7 step 2 as much as to anything else.

### Delivered

- **Deliverable 1 — the publish workflow.** `.github/workflows/release.yml`: triggers only
  on `push: tags: v*`; `permissions: packages: write` on the job, no new secret; derives
  `full`/`minor` from `GITHUB_REF_NAME`; `docker/login-action`, `docker/metadata-action` (the
  three tags plus `org.opencontainers.image.source`), `docker/setup-buildx-action`,
  `docker/build-push-action` against the repository's own `Dockerfile` — the same one
  `ci.yml`'s `container` job smoke-tests.
- **Deliverable 2 — compose pulls; the build is an overlay.** `compose.yaml`'s `akasha`
  service carries `image: ghcr.io/mauroibz/akasha:${AKASHA_VERSION:-1.5.3}` and no `build:`
  key. `compose.build.yaml` adds `build: .` back for
  `docker compose -f compose.yaml -f compose.build.yaml up -d --build`.
  `scripts/smoke_container.sh` exports that same two-file `COMPOSE_FILE` and a fixed
  `AKASHA_VERSION=local` (decoupling its assertions from whatever release number
  `compose.yaml` currently defaults to), reads the resolved image reference back from
  `docker compose config` instead of a hardcoded `akasha:local`, and threads the overlay
  through the AC8 backups-host drill and the AC9 version-tag drill.
- **Deliverable 3 — digest-pinned base images.** Both `FROM` lines pin `tag@sha256:…`
  (`node:22-alpine`, `python:3.12-slim`, captured 2026-09-01), with the refresh command as a
  Dockerfile comment and repeated in `publishing-images.md` and the runbook.
- **Deliverable 4 — Dependabot.** `.github/dependabot.yml` covers `npm` (`/frontend`), `uv`
  (`/backend`), `docker` (`/`) and `github-actions` (`/`), weekly, patch updates grouped
  where the ecosystem supports it.
- **Deliverable 5 — the runbook and README are pull-based.** "Upgrading" is
  `docker compose pull && docker compose up -d` with the local-build overlay named as the
  source-build path; "Rolling back" and "Restoring" reference
  `ghcr.io/mauroibz/akasha:<version>` and note that `docker run` pulls what it does not have,
  with the one-time exception for a version predating this sprint. README's Quick start
  fetches `compose.yaml` and `.env.example` directly rather than cloning, and its
  configuration table's `AKASHA_VERSION` default moved from `local` to `1.5.3`.
- **Deliverable 6 — `docs/operations/publishing-images.md`.** What the workflow does, what a
  release looks like end to end, how to verify a published image from a Docker-only machine,
  the digest-refresh procedure, and the three owner actions written out with their expected
  results (deliverable 7's content lives here verbatim). Listed in `docs/README.md`'s
  canonical table.
- **Deliverable 8 — `docs/operations/release-notes-v1.5.3.md`.** Leads with the obtaining-it
  change, the exact upgrade command, and the one-time old-version rollback exception.
- **DEC-120** records the image name (`ghcr.io/mauroibz/akasha`, matching the repository path
  so the workflow never hardcodes it a second time), the `1.5.3` compose default, and the
  decision to leave the three owner actions unperformed rather than taken on the session's
  own authority.

### Not delivered — deliverable 7 / acceptance criteria 1, 2, 4, 5, 6, 9, 10

The three owner actions in `docs/operations/publishing-images.md` have **not been
performed**:

1. Allow the workflow to write packages (repository Settings → Actions → General →
   Workflow permissions) — **not done**.
2. Push a version tag (`git tag v1.5.3 && git push origin v1.5.3`) and watch the run —
   **not done**; no tag exists locally or on `origin`.
3. Decide the package's visibility — **not applicable yet**; no package has been published.

Consequently NOT RUN, each requiring a real `ghcr.io` publish:

- **AC1/AC2** (a tag publishes; a branch push or pull request does not) — the trigger
  configuration was reviewed by inspection (`on: push: tags: ["v*"]`, no `pull_request`
  block), not exercised against a real GitHub Actions run.
- **AC4/AC5** (upgrade and rollback between two published versions, with an entry surviving
  both) — no published version exists yet to move between.
- **AC6** (no secret/PAT/deploy key created) — true by construction of the workflow file;
  not separately provable without a run.
- **AC9** (Dependabot opens pull requests) — `.github/dependabot.yml` is present and
  YAML-valid; GitHub only starts running it once the file reaches `origin`'s default branch.
- **AC10** — the document and its `docs/README.md` listing exist; the owner actions it
  describes are not yet performed.

### Verified

**Narrowed gate declared and paid**, per DEC-118's rule: the diff touches only
`.github/`, `compose*.yaml`, `Dockerfile`, `scripts/smoke_container.sh` and documentation —
nothing under `backend/src/`, `frontend/src/`, `backend/tests/`,
`backend/alembic/versions/`, `uv.lock` or `package-lock.json`
(`git diff --stat 8657c28..HEAD` confirms: `.github/dependabot.yml`,
`.github/workflows/release.yml`, `Dockerfile`, `compose.build.yaml`, `compose.yaml`,
`scripts/smoke_container.sh`, plus documentation).

- `python scripts/validate_project.py` — green after every edit.
- `make check` — green (ruff format/check, mypy, `npm run format:check`/`lint`/`typecheck`,
  OpenAPI drift check, validator).
- `bash scripts/smoke_container.sh` — **exit 0**, twice, on the frozen tree. Confirms the
  compose split builds and runs correctly through the overlay: image built and tagged
  `ghcr.io/mauroibz/akasha:local`, healthcheck, non-root/no-Node, bounded logs, the entry
  round-trip, the AC4/AC5/AC6/AC8/AC9-numbered assertions inherited from Sprint 056/057 all
  still green under the new compose files, the named-volume restore drill now referencing
  the image name read back from `docker compose config` instead of a hardcoded tag, and the
  AKASHA_VERSION-tag drill building and starting `ghcr.io/mauroibz/akasha:smoke-<pid>`
  without a rebuild.
- The two base-image digests were captured directly (`docker inspect --format '{{index
  .RepoDigests 0}}'`) and diffed programmatically against the Dockerfile content before
  committing, rather than hand-copied.
- `.github/workflows/release.yml` and `.github/dependabot.yml` parse as valid YAML
  (`yaml.safe_load`). Neither has run on GitHub — see "Not delivered" above.

### Deviations

- **The sprint is left `blocked`, not `completed`.** Every prior sprint in this deployment
  line (056, 057) closed with a release un-tagged and un-pushed, because tagging was never
  one of their acceptance criteria. Sprint 058's AC10 is explicit that the owner actions must
  be performed and recorded, so this sprint cannot claim completion the same way. Recorded as
  DEC-120 rather than silently narrowing AC10.
- No other deviation. The compose-file split, the digest pins and the workflow match the
  sprint's deliverables as written.

### Impact on future sprints

059 (event loop) and 060 (storage) both depend on 056 only, not on 058, and are unaffected
by 058 remaining blocked. Whoever resumes this sprint after the owner acts needs only to:
run the three steps in `docs/operations/publishing-images.md`, record their results here
(run URL, digest, chosen visibility), flip AC1/AC2/AC4/AC5/AC6/AC9/AC10 from NOT RUN to
verified against the real run, and close the sprint per the normal protocol. No further
code is anticipated.
