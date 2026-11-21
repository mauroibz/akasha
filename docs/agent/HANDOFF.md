# Handoff

## Where the project stands

**2026-11-21 (later):** Sprint 128 is merged to `main` (#38). Sprint 129, *Security
follow-ups* (DEC-181) widened to robustness and performance (DEC-182), is completed on branch
`ccr-61c66a6d-g1wptf` for a pull request. Migrations 0034–0035 are unreleased; the next release
should be 2.9.0 so `compose.yaml`'s hardening and the image that expects it ship together.

**2026-11-21:** Sprint 128, *Public exposure hardening* (DEC-180), is completed on branch
`ccr-61c66a6d-g1wptf` for a pull request to `main`; unreleased on top of 2.8.0. It fixes the
21 findings of a six-way security audit (see the sprint file's table) and adds the public
deployment: `compose.public.yaml` (Cloudflare Tunnel sidecar, no published port),
`scripts/akasha-egress-firewall.sh`, optional Cloudflare Access JWT verification, Docker
secret files, and the runbook's *Publishing on the internet* section. Migration 0034 assigns
attachment owners. The project state is `complete` again.

Upgrade notes for the owner: every device signs in once more (cookie rename when Secure);
new passwords need 12 characters; the first-run setup asks for the code in
`docker compose logs akasha`; compose now runs the container read-only with no capabilities
and resource limits (`AKASHA_MEM_LIMIT`, `AKASHA_CPUS`, `AKASHA_PIDS_LIMIT`).

Waiting on the owner (Sprint 128): a Cloudflare account, tunnel token, Access application and
policy on the real server; running the egress firewall script there; an off-host backup copy.

## Earlier state (2026-10-24)

**2026-10-24:** Sprints 109–127 are completed and **released as v2.8.0** (tag
`v2.8.0`, GitHub release from `docs/operations/release-notes-v2.8.md`). The project state is `complete`; no sprint is planned. 109–121 are the house and the
history (DEC-176, DEC-178); 122–127 are the owner's first look at them in the running app
(DEC-179, mockups *A second look*, approved as recommended). Migrations 0028–0033 are new.

What 122–127 changed, by screen:

- **Shelves:** open loans stand as the first ledge, *Lent out*; `/lent` returns to Shelves.
- **Detail page:** only rows that hold a value; one question at a time about the most useful
  gap (*I don't remember* kept in `entries.unknown_fields`, migration 0033); *Lend…* among
  the actions; *Finished* while under way, opening one sheet (when, score or "Still an 8?",
  format). Starting something dates an empty start.
- **Library:** each *Now* card has *Finished*.
- **Insights:** *Play with your library* at the top: *Five minutes* (`/play/five`), the best
  of a score, an old score, the pile, *Fill in the gaps* (`/play/gaps`, `GET /api/gaps`).
- **`/deck`** is *Tidy up*: the inbox, covers, duplicates (Settings and the command bar).
- **Diary:** the goal leads; without one an invitation with three paces, with one a slot per
  thing aimed at filled by the year's covers (a bar above 24).

Waiting on the owner:

- A look at 122–127, especially Play's weight on a phone's first screen of Insights.
- DEC-178's reading of the 02/03 mockup note (Sprint 121 is one commit, `8b61b07`).
- Upgrading the board to 2.8.0 (`docs/operations/runbook.md`): six migrations (0028–0033)
  run there, with the usual backup first.
- Still open from before: trust-stated-status on import (DEC-165 point 3); real Hardcover,
  Simkl and StoryGraph exports (Sprint 099). Homelab sync is GitHub issue #31; the
  commonplace book is a v3 candidate.

## Verified

- Per sprint, as DEC-167 asks: the tests for the changed code, `make check`, the Playwright
  specs for each changed screen, and a walkthrough on a fresh `scripts/walkthrough.py`
  backend (recorded per sprint in the worklog and each Outcome).
- Once for 122–127, on 2026-10-24: `make test` — backend 1792 passed, Vitest 549 passed;
  full Playwright — 214 passed, 2 skipped (live metadata, by design); `make check`.
- Release gate for 2.8.0, 2026-10-24: the full suites above on the release tree's code, then
  `make check` and `make smoke-container` after the version surfaces moved.

## Known and left

- On a phone, Play's games fill most of Insights' first screen.
- At 390px a long place truncates beside its *Change* button on the detail page.
- After the last light of a reread the status stays *Reading* (DEC-175); *Finished* is the
  way to finish it now.
- The rank page's back link says *Library* even when opened from Insights.
- *Find a cover*: an installed cover is not taken back by *Undo* (no remove-cover endpoint).
- EPUBs without an ISBN are not enriched; only EPUB is read.
- `test_events.py::test_the_stream_carries_each_change_to_a_job` and `rescore.spec.ts` are
  timing-sensitive under full parallel load.

## Next session

No sprint is planned. Run checks under `set -o pipefail`. Walkthroughs: `uv run python
../scripts/walkthrough.py` from `backend/`, vite on 5180 with `AKASHA_E2E_BACKEND`; start a
fresh backend after backend changes; stop servers by port (`fuser -k`). Port 8000 may hold the
owner's check server on a copy of their library (`AKASHA_DATA_DIR` in the scratchpad); e2e
stubs `/api/loans?open=true` by default so it cannot leak into specs. The board runs 2.7.0 until the owner upgrades it.
