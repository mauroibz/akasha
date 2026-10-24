# Handoff

## Where the project stands

**2026-10-24:** Sprints 109–127 are completed and committed on `main`, **unreleased on top of
2.7.0**. The project state is `complete`; no sprint is planned. 109–121 are the house and the
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
- A 2.8 release (version surfaces, release notes, `make smoke-container`, tag) when asked.
  Six migrations (0028–0033) would run on the board, with the usual backup first.
- Still open from before: trust-stated-status on import (DEC-165 point 3); real Hardcover,
  Simkl and StoryGraph exports (Sprint 099). Homelab sync is GitHub issue #31; the
  commonplace book is a v3 candidate.

## Verified

- Per sprint, as DEC-167 asks: the tests for the changed code, `make check`, the Playwright
  specs for each changed screen, and a walkthrough on a fresh `scripts/walkthrough.py`
  backend (recorded per sprint in the worklog and each Outcome).
- Once for 122–127, on 2026-10-24: `make test` — backend 1792 passed, Vitest 549 passed;
  full Playwright — 214 passed, 2 skipped (live metadata, by design); `make check`.
- Not run: `make smoke-container` (owed before a release).

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
stubs `/api/loans?open=true` by default so it cannot leak into specs. The board runs 2.7.0.
