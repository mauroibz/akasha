# Handoff

## Where the project stands

**2026-10-22:** the owner asked for a way through a large inbox one entry at a time on a phone
(DEC-170). Sprint 106 delivered `/inbox/deck` and shipped as **v2.6.0** (tagged, pushed, GitHub
Release). The project state is `complete`; no sprint is planned.

v2.5.0 (Sprints 102–105, DEC-169: Insights redrawn, gentle goals, Shelves redrawn) shipped on
2026-10-22. The 2.5 canvas is https://claude.ai/artifact/6vt1GZ5nBi5zYq67ibZh3c.

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

No sprint is planned. The ZimaBoard (192.168.100.240, port 4441, auth on) refuses this machine's
SSH key (`ibz@comma`) for `ibz` and `root`; the board upgrade to 2.6.0 is the owner's unless
access is given: `AKASHA_VERSION=2.6.0` in the board's `.env`, `./render-compose.sh`, then
`docker compose pull && docker compose up -d`. Walkthroughs can use a copy of the owner's library
from the board's nightly backup, kept in the session scratchpad and never committed.
