# Handoff

## Where the project stands

On 2026-10-21 the owner accepted `docs/production-grade-proposal.md` (DEC-165). The plan reopened
as Sprints 087–101 and ran autonomously, with per-sprint verification limited to what each sprint
changed (DEC-167). **All fifteen are completed and the project state is `complete`.** Nothing has
been tagged, released or pushed.

Waiting on the owner:

- Trust-stated-status on import (DEC-165 point 3).
- A real Hardcover export and a real Simkl export (Sprint 099).
- A real StoryGraph export, to confirm the connector built in 099.
- The release decision. Sprint 101 added migrations 0024 and 0025, so the next release is a
  minor version.

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

## Verified (final tree)

- Backend: the full suite, 1686 passed, at 852a6ca.
- `make check` is green.
- Vitest and Playwright have not been run in full since DEC-167. Only related tests and
  changed-screen specs ran per sprint.
- smoke-container last ran for v2.3.0.

## Owed before a release (DEC-167)

1. `make test`: the full Vitest run and the full Playwright run.
2. `make smoke-container` on the new image, so migrations 0021–0025 run in the container.
3. Release notes for 2.4 from the Outcomes of Sprints 087–101.
4. The version bump across the five surfaces `validate_project.py` checks.

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

There is no planned sprint. Ask the owner whether to cut the release (the list above) or to plan
more work. The design mock the owner approved is the canvas artifact
https://claude.ai/artifact/KRWdo67P7QfirBsBK4mdRa.
