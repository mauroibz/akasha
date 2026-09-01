# Handoff — Sprint 057 is ready: the published image

Sprint 056 (deployment defaults, v1.5.1) is complete and committed. `docs/agent/state.json`
reads `ready` with `057` active. v1.5.1 is **not tagged and not pushed** — the owner's call,
as with every release before it.

The next move is ordinary: execute Sprint 057 with the protocol in `/AGENTS.md`.

## What Sprint 056 changed (all committed, all verified)

- The published port defaults to **4441**; the container still listens on 8000. The one
  breaking change of the line; `AKASHA_PORT=8000` in `.env` restores the old address, and the
  release notes lead with it.
- Container logs are bounded (json-file, 10 MiB × 5) via a `logging:` block in `compose.yaml`.
- `BOOK_TRACKER_ATTACHMENT_MAX_BYTES`, `BOOK_TRACKER_SQLITE_BUSY_TIMEOUT_MS` and
  `TMDB_READ_TOKEN` are bare list-form pass-throughs: present with the sent value, absent from
  the container when unset. **Never replace them with `env_file:`** — it would inject the
  example's `BOOK_TRACKER_ENVIRONMENT=development` and disable the production guard.
- Healthcheck start period is 60 s (sized by DEC-039's pre-migration backup plus a row-rewrite
  migration, not by a warm restart).
- `image: akasha:${AKASHA_VERSION:-local}` — the shape Sprint 057 builds its registry reference
  on. The runbook's rollback and restore recipes carry the variable.
- `compose.backups-host.yaml` binds only `/backups` to a host path; `/data` stays the named
  volume. The runbook has the tier table (tiers 1/2/3) and the one privileged `chown`.
- Overlay-network sentence present in `SECURITY.md`, the compose header, and the runbook.
- `docs/operations/release-notes-v1.5.1.md` exists and is linked in `docs/README.md`.

## What Sprint 057 must not get wrong

- **A compose service carrying both `image:` and `build:` builds silently when the image is
  absent** — that is the failure the sprint exists to remove. The local build moves to its own
  overlay; compose points at the registry.
- **`scripts/smoke_container.sh` must keep building locally.** It now also carries Sprint 056's
  hermetic `COMPOSE_ENV_FILES` harness and its five new assertions; the sprint file names the
  steps that need adapting for a pulled image.
- **Sprint 057 declares the same narrowed gate** (validator + `make check` + smoke), and its
  diff must stay confined to deployment/CI configuration and docs to keep it. Its three
  owner-only steps (workflow package-write permission, pushing the tag, package visibility)
  are written out with expected results in the sprint file — surface them to the owner, don't
  improvise them.
- The smoke test picks a **random port** and never binds 4441; keep that property when adapting
  it.

## Verified at Sprint 056's close

- `bash scripts/smoke_container.sh` — exit 0 on the final frozen tree, all 20 steps, no
  leftovers, no smoke volumes remaining.
- `make check`, `python scripts/validate_project.py` — green.
- `AKASHA_VERSION=1.5.1 docker compose build` — tags `akasha:1.5.1`.
- `make test` / `npm run test:e2e` — not owed (narrowed gate); CI runs both on every push.

## Private data and operational constraints

Unchanged. `exports/` is the owner's private source archive, gitignored whole, read-only
walkthrough input; no fixture may be cut from it. Secrets, databases, uploaded imports and
covers are never committed. v1 has no auth and stays LAN-only; Calibre is opened read-only.
No pushing unless asked.
