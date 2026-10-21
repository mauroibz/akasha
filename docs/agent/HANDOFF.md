# Handoff

## Where the project stands

On 2026-10-21 the owner accepted `docs/production-grade-proposal.md` (DEC-165). The plan reopened
as Sprints 087–101 and ran autonomously, with per-sprint verification limited to what each sprint
changed (DEC-167). **All fifteen are completed and the project state is `complete`.** They
shipped as **v2.4.0**, tagged and pushed on 2026-10-21 after the full release gate.

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

## Verified (v2.4.0)

- `make test`: backend 1686 passed, Vitest 423 passed.
- Playwright: 147 passed, 2 skipped (the live-metadata specs, by design).
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

There is no planned sprint. Ask the owner what to plan next. The design mock the owner approved is the canvas artifact
https://claude.ai/artifact/KRWdo67P7QfirBsBK4mdRa.
