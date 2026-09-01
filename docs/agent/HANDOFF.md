# Handoff — Sprint 058 is closed; Sprint 059 (event loop) is ready

Sprint 058 (an image you pull, not a build you run) is **completed**. It was implemented and
gated green in one session, then sat `blocked` in the documentation past the point the owner
had actually unblocked it — the owner tagged and pushed `v1.5.3` and the release ran green,
but `main` itself was never pushed and nobody flipped the sprint's bookkeeping. This closing
session verified the real state (`gh run list`, `git ls-remote`, a real `docker pull`) against
the stale documents, reconciled them, pushed `main`, and — with the user's explicit sign-off —
cut an out-of-sprint `v1.5.4` patch release (the already-committed e2e CI fix, no new code) to
supply the second published version AC4/AC5 needed. Full account: the sprint's own Outcome,
and `docs/decisions.md` DEC-120/DEC-121.

## What that changes for the version numbers

DEC-118 had reserved `v1.5.4` for Sprint 059 and `v1.5.5` for Sprint 060. Cutting `v1.5.4`
out-of-sprint consumed that number. **Sprint 059 now ships `v1.5.5`; Sprint 060 ships
`v1.5.6`.** Both sprint files and `docs/sprints/ROADMAP.md` already carry the corrected
numbers — this is not something to redo.

## Current release state

- Published: `v1.5.3` and `v1.5.4`, both on `ghcr.io/mauroibz/akasha`, both public (`docker
  pull` with no login succeeds), both tagged `<full>`, `1.5` and `latest` from
  `docker/metadata-action`.
- `compose.yaml`'s default `AKASHA_VERSION` is `1.5.4`.
- `origin/main` is caught up (pushed this session); `.github/dependabot.yml` is live and has
  already opened 17 pull requests across npm, uv, docker and github-actions, each gated by a
  real CI run.
- No secret, PAT or deploy key exists for any of this — both releases authenticated with the
  workflow's own `GITHUB_TOKEN`.

## What to do next

Execute Sprint 059 — read `docs/sprints/059-off-the-event-loop.md`. It is **[GATED]**: Phase A
measures whether the single-threaded event loop actually blocks under realistic load; Phase B
(moving blocking work off it) only happens if the measurement says so. Read its own `Required
context` section before touching anything. Remember it ships as `v1.5.5`, not the `v1.5.4`
the file's prose was originally written against in a couple of spots that are now corrected.

## Private data and operational constraints

Unchanged. `exports/` is the owner's private source archive, gitignored whole, read-only
walkthrough input. Secrets, databases, uploaded imports and covers are never committed. v1 has
no auth and stays LAN-only; Calibre is opened read-only. **No pushing unless asked** — this
session pushed `main` and two tags only after the owner explicitly approved each one; that
approval does not carry forward to future pushes.
