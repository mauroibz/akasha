# Handoff — Sprint 058 is implemented and gated green; blocked on three owner actions

Sprint 058 (an image you pull, not a build you run) has every deliverable that does not
need the repository owner's GitHub account or a push to `origin`: the publish workflow, the
compose pull/build split, digest-pinned base images, Dependabot, the runbook/README
rewrite, and `docs/operations/publishing-images.md`. `docs/agent/state.json` and the sprint
file both read `blocked` — not `completed` — because acceptance criterion 10 requires the
three owner-only steps to be **performed and their results recorded**, and none of them can
be taken by an agent session. See DEC-120 and the sprint file's Outcome for the full
account.

## What is blocking

Three steps, all in `docs/operations/publishing-images.md` with expected results:

1. **Allow the workflow to write packages** — repository Settings → Actions → General →
   Workflow permissions. GitHub setting; not scriptable from here.
2. **Push a version tag and watch the run** — `git tag v1.5.3 && git push origin v1.5.3`.
   Not done: this repository's standing rule is nothing goes to `origin` — branch or
   tag — without the owner asking, and that has not been asked for this sprint.
3. **Decide the package's visibility** — public (recommended) or private. A judgment call
   only the owner can make; nothing to publish yet either way.

Sixteen local commits from this session sit on top of the sixteen already ahead of
`origin/main` from Sprints 056/057 — thirty-two total, nothing pushed.

## What to do next

Ask the owner: perform the three steps directly, or authorize this session to push `main`
and a `v1.5.3` tag so the owner can then do steps 1 and 3 against a real run. Either way,
once a release run has gone green:

- record the run URL, the pushed digest, and the visibility decision in Sprint 058's
  Outcome;
- flip AC1, AC2, AC4, AC5, AC6, AC9 and AC10 from NOT RUN to verified against that run;
- close the sprint through the normal protocol (`docs/agent/state.json` to `058` completed,
  `059` ready; worklog entry; this file rewritten for Sprint 059).

No further code is anticipated before that. Sprint 059 (event loop, gated, v1.5.4) and
Sprint 060 (storage, v1.5.5) both depend on 056 only and are unaffected by 058 sitting
blocked.

## What Sprint 058 built, concretely

- `.github/workflows/release.yml` — publishes on `v*` tags only, using the workflow's own
  `GITHUB_TOKEN` (`packages: write`), no new secret. Builds the same `Dockerfile` `ci.yml`'s
  `container` job smoke-tests; tags full/minor/`latest`; carries
  `org.opencontainers.image.source`.
- `compose.yaml` now `image: ghcr.io/mauroibz/akasha:${AKASHA_VERSION:-1.5.3}`, no `build:`
  key. `compose.build.yaml` is the new local-build overlay:
  `docker compose -f compose.yaml -f compose.build.yaml up -d --build`.
- Both `Dockerfile` `FROM` lines pinned by digest (captured 2026-09-01), refresh procedure
  as a Dockerfile comment.
- `.github/dependabot.yml`: npm, uv, docker, github-actions, weekly.
- `scripts/smoke_container.sh` updated for the compose split — still the thing that must
  build rather than pull, and still exit-0 twice on the frozen tree.
- `docs/operations/runbook.md`, `README.md`, `docs/operations/publishing-images.md`
  (new), `docs/operations/release-notes-v1.5.3.md` (new).

## Verified at this session's close

`python scripts/validate_project.py` green after every edit; `make check` green;
`bash scripts/smoke_container.sh` exit 0 twice on the frozen tree, through the new compose
split. Narrowed gate (DEC-118's rule): `make test`/`npm run test:e2e` not owed — nothing
under `backend/src/`, `frontend/src/`, either test tree, migrations or lockfiles changed.

## Private data and operational constraints

Unchanged. `exports/` is the owner's private source archive, gitignored whole, read-only
walkthrough input. Secrets, databases, uploaded imports and covers are never committed. v1
has no auth and stays LAN-only; Calibre is opened read-only. **No pushing unless asked** —
this now covers a real published package as well as a branch or tag.
