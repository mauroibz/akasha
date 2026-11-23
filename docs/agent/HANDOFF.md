# Handoff

## Where the project stands

**2026-11-23, Sprint 132 closed.** On branch `home-and-recommendations` (local, not pushed):
Home has every module of the approved design but *More like this* (134), and *Up next* is the
pile ranked locally with a reason each (`application/ranking.py`, `GET /api/pile`, DEC-186).
A goal's picks in the Diary are the same ranking within one library. `/api/home?tz=` makes
today and Lately's days the person's. DEC-183 is the plan (Sprints 130–136, `FINAL_SPRINT`
136). **Sprint 133 is next and `ready`**: recommendation infrastructure with a fake source.

Things to know for 133:

- `Domain.ranking: RankingSpec` exists; `RecommendationSpec` goes beside it, and the
  conformance suite's `test_the_suite_covers_every_field_of_the_contract` demands a check for
  each new `Domain` field.
- A pile reason is `{signal, text}`; `PileReason.signal` in `api/pile.py` is a closed Literal.
- Nothing stores a dismissal of a pile entry (DEC-186 point 5).
- `/api/home` is at about 119 ms median of its 150 ms budget on 10,000 entries.
- Walkthrough: `scripts/walkthrough.py --keep`, then the scratchpad seeder `seed_132.py` (if
  the scratchpad survived), vite on 5180 with `AKASHA_E2E_BACKEND`; give the browser context a
  `timezoneId` to see Lately's local days. e2e stubs `/api/home` by pathname (`isHome` in
  `e2e/console.ts`), since the URL now carries `?tz=`.
- `accessibility.spec.ts` *the add dialog over the library* fails about one run in four on the
  base commit too; rerun alone before suspecting a change.

## Earlier state (release 2.9.0)

**2026-11-22:** Sprints 128–129 are merged to `main` (#38, #40) and **released as v2.9.0**
(tag `v2.9.0`, notes in `docs/operations/release-notes-v2.9.md`). Migrations 0034–0035 are
new. The project state is `complete`; no sprint is planned.

Upgrade notes for the owner: new passwords need 12 characters; the first-run setup asks for
the code in `docker compose logs akasha`; compose runs the container read-only with no
capabilities and resource limits (`AKASHA_MEM_LIMIT`, `AKASHA_CPUS`, `AKASHA_PIDS_LIMIT`).
Take the 2.9.0 `compose.yaml` and image together.

Waiting on the owner (Sprint 128): a Cloudflare account, tunnel token, Access application and
policy on the real server; running the egress firewall script there; an off-host backup copy.

Known from the 2.9.0 review, not fixed: resuming an import install whose item was deleted
meanwhile writes an orphan cover and keeps the batch's staging, retried hourly
(`install_staged` catches only `CoverError`, `set_cover_path` raises `LookupError`); and
`resume_interrupted_installs` has no per-batch guard. Batches committed by 2.8.0 inside their
24 h undo window look interrupted on the first 2.9.0 start, which re-fills a cover removed
after that import.

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

Sprint 132 (see the top). Run checks under `set -o pipefail`. Walkthroughs: `uv run python
../scripts/walkthrough.py` from `backend/`, vite on 5180 with `AKASHA_E2E_BACKEND`; start a
fresh backend after backend changes; stop servers by port (`fuser -k`). Port 8000 may hold the
owner's check server on a copy of their library (`AKASHA_DATA_DIR` in the scratchpad); e2e
stubs `/api/loans?open=true` by default so it cannot leak into specs. The board runs 2.7.0 until the owner upgrades it.
