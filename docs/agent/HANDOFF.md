# Handoff — Sprint 056 is ready; the deployment line is planned

v1.5.0 is released and tagged. The plan was complete at Sprint 055; the owner then commissioned a
**deployment line of four sprints, one patch release each**, and this session planned it. Plan
revision is **30**, `FINAL_SPRINT` is **59**, and `docs/agent/state.json` reads `ready` with
`056` active. No runtime code changed in this session.

The line ships as **patch releases**, v1.5.1 through v1.5.4 — no new domains, no major features.

The next move is ordinary: execute Sprint 056 with the protocol in `/AGENTS.md`.

## The line, and why it exists

The owner asked what a real deployment of v1.5.0 would meet. The artifact answered well —
`bash scripts/smoke_container.sh` passes end to end from a clean build, and nothing about the image
or its data handling needed defending. Every gap found was one layer out, in the shipped
configuration, the operator documentation, and the paths that write bytes with nothing to collect
them. **DEC-117** records the whole assessment and the four-sprint decision.

| Sprint | Ships | Shape |
|---|---|---|
| [056](../sprints/056-deployment-defaults.md) — deployment defaults | v1.5.1 | Config and docs only. Gate is the container smoke test. **Active, `ready`.** |
| [057](../sprints/057-published-image.md) — a published image | v1.5.2 | CI publishes on a tag; compose pulls. Three steps need the owner's GitHub account. |
| [058](../sprints/058-off-the-event-loop.md) — nothing blocks the loop | v1.5.3 | **Gated.** Phase A measures; Phase B only does what the measurement names. |
| [059](../sprints/059-storage-housekeeping.md) — the disk stops filling | v1.5.4 | Collectors for three growth paths, plus a free-space guard. |

057, 058 and 059 depend on 056 alone and are otherwise independent. Nothing in the line changes what
a person sees in the application, and none of it adds authentication — product spec §9 keeps that a
v2 deferral and the owner reaffirmed it while commissioning these sprints.

## The gates these sprints owe

**DEC-118** added "Gate scope by what changed" to `TESTING.md` and the clause in `AGENTS.md` §3 that
lets a sprint use it. Sprints 056 and 057 **declare a narrowed gate**: `validate_project.py`,
`make check` and `make smoke-container`, with `make test` and `npm run test:e2e` not owed, because
their diffs contain no line those suites execute. Sprint 058 declares it conditionally — Phase A
alone qualifies, Phase B owes the full gate. Sprint 059 owes the full gate outright.

The narrowing is a claim about the diff and is checked against it: `git diff --stat` at the freeze
point goes in the Outcome. **One file under `backend/src/` withdraws it for the whole sprint.** CI's
`checks` and `e2e` jobs still run the full suites on every push either way.

## What Sprint 056 must not get wrong

- **The published port becomes 4441.** The container still listens on 8000 internally; only the host
  side of the mapping moves. This is the one change that breaks an existing install, so the release
  notes lead with it and the remedy is one line of `.env`.
- **Do not use `env_file: .env`** to fix the missing environment passthroughs. It would inject the
  shipped example's `BOOK_TRACKER_ENVIRONMENT=development` into the container and disable the
  production guard that makes `USER_AGENT_CONTACT` mandatory. Acceptance criterion 6 exists to catch
  a session taking that shortcut.
- The sprint's own baseline table carries the measurements this session took, with file and line
  references. Re-confirm them at activation rather than trusting the table — that is the standing
  rule, and the table is dated 2026-09-01.

## Verified this session

- `bash scripts/smoke_container.sh` — passed, exit 0, from a clean build on Docker 29.5.2 /
  Compose v5.1.4. Healthcheck, non-root, no Node in the runtime, API persistence across recreation,
  every emitted chunk served, read-only Calibre, in-container restore, named-volume restore drill,
  graceful SIGTERM in 0 s with exit 143.
- `python scripts/validate_project.py` — green after every planning edit.
- `make test` is **not owed**: no application code changed. This is a plan revision, per the
  post-gate matrix in `TESTING.md`.

## Private data and operational constraints

Unchanged from Sprint 055's handoff. `exports/` is the owner's private source archive, gitignored
whole, read-only walkthrough input, and no fixture may be cut from any of it. Wikidata, TVmaze and
AniList need no key, only `USER_AGENT_CONTACT`. Secrets, databases, uploaded imports and covers are
never committed; v1 has no auth and stays LAN-only; Calibre is opened read-only.
