# Handoff — every planned sprint is complete; there is no active sprint

`docs/agent/state.json` reads `project_status: "complete"`, with `active_sprint`,
`active_sprint_file` and `active_sprint_status` all `null`. Sprint 060 (storage housekeeping)
was the final sprint in the current roadmap (`FINAL_SPRINT = 60` in
`scripts/validate_project.py`), and it closed clean. **Do not assume there is a sprint to
resume** — read `docs/sprints/ROADMAP.md`'s "Future epics" section and ask the owner what's
next, rather than picking up where this file's previous version left off.

## What shipped in this closing session

Starting from Sprint 058 sitting undocumented-but-actually-unblocked, this session:

1. **Reconciled and closed Sprint 058** (published image) — the owner had already performed
   the three owner-only actions; the documentation just hadn't caught up.
2. **Cut an out-of-sprint `v1.5.4` patch** (the e2e CI flakiness fix, already committed) to
   supply the second published version Sprint 058's AC4/AC5 needed — see DEC-121 for the
   version renumbering this forced (059 → v1.5.5, 060 → v1.5.6).
3. **Executed Sprint 059** (event loop) — Phase A found a real ~10x latency budget breach in
   the import-commit path under CPU constraint; Phase B fixed exactly that with one offload
   seam. See DEC-122.
4. **Found and fixed a real, reproducible e2e CI bug** (unrelated to any sprint): a test
   fixture (`frontend/e2e/fixtures/Calibre Library/metadata.db`) was gitignored by a blanket
   `*.db` rule and had never actually reached any CI checkout. Root-caused with a Docker
   reproduction, fixed with a narrow `.gitignore` negation, confirmed with a real green CI run.
5. **Executed Sprint 060** (storage housekeeping, the final planned sprint) — automatic staging
   cleanup, covers hardlinked in backups, an explicit pre-migration prune, a disk-space guard
   at every bulk-write boundary, and a latent upload-cap gap closed. See DEC-123.
6. **Fixed a real CI inefficiency, requested by the owner**: `ci.yml`'s `push` trigger had no
   branch filter, so every Dependabot branch fired CI twice (`push` + `pull_request` on the
   identical commit) and every version tag fired a third redundant full run on top of the
   dedicated `Release` workflow — both observed directly this session. Now `push:
   branches: [main]`.
7. **Cut and published `v1.5.6`**, owner-requested once the gap was pointed out: Sprint 059 and
   060 had landed on `main` with release notes but no published image, so a fresh install would
   have pulled `v1.5.4` and missed both. `compose.yaml`'s default now points at `1.5.6`.

Everything is pushed to `origin/main`, including the `v1.5.6` tag. The published image is
current — `docker pull ghcr.io/mauroibz/akasha:1.5.6` (and `:1.5`, `:latest`) all resolve to
`sha256:a4853eed90a07cf4770bbe2e636affb07d66b9566fa6ba0e6229b984e849bbf1`, confirmed pullable
with no login (package is public).

## Current state, concretely

- **Backend:** 1,215 tests passing. **Frontend:** 194 tests passing. `make check` green.
  `make smoke-container` green.
- **Backup format is version 2** (covers hardlinked, `/data/imports` no longer archived).
  Version 1 backups still restore — proved against a real fixture, not a hand-edited one.
- **New operator-facing surface:** `AKASHA_MIN_FREE_BYTES` (disk guard, default 500 MB),
  `akasha-backup prune-pre-migration` (explicit, name-based, never automatic).
- **CI is green** on `main`, runs exactly once per push (the branch-filter fix above), and the
  published image is current at `v1.5.6`.
- **`docs/decisions.md`** ends at DEC-123. Read DEC-120 through DEC-123 for the full account
  of this session's decisions, in order. (The `v1.5.6` release and the CI trigger fix were
  owner-requested follow-ups after this session's work, not new architectural decisions, so
  they carry no DEC entry of their own — see the worklog's last entry instead.)

## If you're asked to find the next thing to do

There is no active sprint file to read. Options, roughly in the order the roadmap's "Future
epics" section names them: games, a second series-like domain, the Spotify connector, or
whatever the owner asks for next. Any of these starts the same way Sprint 019 or 025 did —
assess viability and cost before committing to a build, per the `docs/decisions.md` precedent
(DEC-035, DEC-042). Do not invent a sprint number or a deliverable list without the owner's
direction; propose a plan and ask.

## Private data and operational constraints

Unchanged. `exports/` is the owner's private source archive, gitignored whole, read-only
walkthrough input. Secrets, databases, uploaded imports and covers are never committed. v1 has
no auth and stays LAN-only; Calibre is opened read-only. The owner authorized autonomous work
through this session's chain (Sprint 058 → the Calibre fix → Sprint 059 → Sprint 060),
including pushing commits as each stage closed — that authorization does not carry forward to
a new session, and does not extend to force-pushes, history rewrites, or cutting a new release
tag without being asked again.
