# Handoff

## Where the project stands

**2026-10-23:** the owner sorted a brainstorm into a new line (DEC-176): Sprints 109–119,
the house (location, loans), the deck for chores and duplicates, the score history, ranks and
tiers, the Diary timeline and suggested shelves. Sprints 109 (undo on cards, fill from provider) 110 (location and loans API, migration 0028) 111 (their screens, `/lent`) 112 (the deck shell, `/deck` chores) 113 (duplicates, migration 0029) 114 (score history, migration 0030) 115 (its screens, *Still an 8?*) 116 (ranks, migration 0031) 117 (the tier board) 118 (the Diary timeline) 119 (suggested shelves, migration 0032) and 120 (the year in review) are completed; **121 is active (ready).** DEC-178 adds 120–121 (year in review, revisit deck) from the mockups. The resurfacing idea
waits on the owner's choice of mockup; homelab sync is GitHub issue #31.

**2026-10-22:** Sprints 107–108 (DEC-171–175: episode and chapter marks, the progress row as
the tracker, the drop question, Started and Finished filled by the first and last light)
shipped as **v2.7.0** (tagged, pushed, GitHub Release). The project state is `complete`; no
sprint is planned. Migration 0027 adds `entries.progress_marks`.

Waiting on the owner:

- Trust-stated-status on import (DEC-165 point 3).
- A real Hardcover export and a real Simkl export (Sprint 099).
- A real StoryGraph export, to confirm the connector built in 099.

## What changed in the last two sprints

- **Sprint 100.**
  - The library's filter chips end in *Save view*, and saved views appear in the command bar.
  - The Detail page has *Move to another library…*, which re-files an entry into another domain
    through that domain's own record (DEC-168).
- **Sprint 101.**
  - Provider health reports `working`, `degraded` or `down` from real calls, and the Add page's
    notice names a provider that has stopped answering.
  - Searches are cached for 24 hours.
  - `AKASHA_METRICS=on` serves `/metrics`.

## Verified (v2.6.0)

- `make test`: backend 1699 passed (90% coverage), Vitest 437 passed.
- Playwright: 158 passed, 2 skipped (the live-metadata specs, by design).
- `make check` and `make smoke-container` pass.

## Known and left

- Triage pre-selects the domain default ("Read") for dropped books; "To read" may suit better.
- ePubLibre files put the original publication year in `dc:date`, which lands as edition year.
- EPUBs without an ISBN are not enriched; edit-and-refresh is the path.
- Only EPUB is read; azw3, mobi and pdf are refused by the member pattern.
- Re-file records no undo effect; moving back is a second re-file (DEC-168).
- `test_events.py::test_the_stream_carries_each_change_to_a_job` failed once in a full run under
  load and passed in the rerun. It is timing-sensitive and recorded, not marked flaky.
- Walkthrough scripts must wait on `load`, not `networkidle`: the events stream never idles.

## Next session

Run Sprint 121. Run checks under `set -o pipefail`: `make check | tail` hides a failure from `&&`. Walkthroughs: `scripts/walkthrough.py` from `backend/` with `uv run`, vite on 5180 with `AKASHA_E2E_BACKEND`; stop servers by port (`fuser -k`), since `pkill -f` matches the calling shell. The board upgrade to 2.7.0 is the owner's unless SSH access is given:
`AKASHA_VERSION=2.7.0` in the board's `.env`, `./render-compose.sh`, then
`docker compose pull && docker compose up -d` (migration 0027 runs with its pre-migration
backup). The 390px sideways scroll on the detail page is fixed (`fca2bb8`).
